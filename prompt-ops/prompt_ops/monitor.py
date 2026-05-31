import threading
import time
from datetime import datetime, timezone, timedelta
from statistics import mean, stdev
from loguru import logger
from prompt_ops.database.connection import get_session
from prompt_ops.database.models import TelemetryLog, Alert, ModelMetric
from prompt_ops.config import settings


class Monitor:
    def __init__(self, interval_seconds: int = 300):
        self.interval = interval_seconds
        self._thread = None
        self._stop_event = threading.Event()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="prompt-ops-monitor")
        self._thread.start()
        logger.info("Prompt-Ops monitor started (interval={}s)", self.interval)

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("Prompt-Ops monitor stopped")

    def _run_loop(self):
        while not self._stop_event.is_set():
            try:
                self._run_checks()
            except Exception as e:
                logger.error(f"Monitor check failed: {e}")
            self._stop_event.wait(self.interval)

    def _run_checks(self):
        self.check_latency()
        self.check_error_rate()
        self.check_cost()
        self.check_anomalies()

    def check_latency(self, hours: int = 1):
        """Alert if average latency exceeds threshold."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        with get_session() as session:
            logs = session.query(TelemetryLog).filter(
                TelemetryLog.timestamp >= cutoff,
                TelemetryLog.success == True
            ).all()
            if len(logs) < 5:
                return
            avg_latency = mean([l.latency_ms for l in logs])
            if avg_latency > settings.latency_threshold_ms:
                self._fire_alert(
                    session,
                    alert_type="high_latency",
                    severity="WARNING",
                    message=f"Average latency {avg_latency:.0f}ms exceeds threshold {settings.latency_threshold_ms:.0f}ms (last {hours}h, {len(logs)} requests)",
                    threshold=settings.latency_threshold_ms,
                    actual_value=avg_latency
                )

    def check_error_rate(self, hours: int = 1):
        """Alert if error rate exceeds threshold."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        with get_session() as session:
            logs = session.query(TelemetryLog).filter(
                TelemetryLog.timestamp >= cutoff
            ).all()
            if len(logs) < 10:
                return
            error_count = sum(1 for l in logs if not l.success)
            error_rate = error_count / len(logs)
            if error_rate > settings.error_rate_threshold:
                self._fire_alert(
                    session,
                    alert_type="high_error_rate",
                    severity="HIGH",
                    message=f"Error rate {error_rate:.1%} exceeds threshold {settings.error_rate_threshold:.1%} ({error_count}/{len(logs)} requests in last {hours}h)",
                    threshold=settings.error_rate_threshold,
                    actual_value=error_rate
                )

    def check_cost(self, hours: int = 24):
        """Alert if total cost exceeds daily threshold."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        with get_session() as session:
            logs = session.query(TelemetryLog).filter(
                TelemetryLog.timestamp >= cutoff
            ).all()
            if not logs:
                return
            total_cost = sum(l.cost_usd for l in logs)
            if total_cost > settings.cost_threshold_usd:
                self._fire_alert(
                    session,
                    alert_type="cost_exceeded",
                    severity="MEDIUM",
                    message=f"Total cost ${total_cost:.4f} exceeds daily threshold ${settings.cost_threshold_usd:.2f} (last {hours}h)",
                    threshold=settings.cost_threshold_usd,
                    actual_value=total_cost
                )

    def check_anomalies(self, hours: int = 6):
        """Z-score anomaly detection on latency."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        with get_session() as session:
            logs = session.query(TelemetryLog).filter(
                TelemetryLog.timestamp >= cutoff,
                TelemetryLog.success == True
            ).all()
            if len(logs) < 10:
                return
            latencies = [l.latency_ms for l in logs]
            avg = mean(latencies)
            sd = stdev(latencies) if len(latencies) > 1 else 0
            if sd == 0:
                return
            # Check latest entries for anomalies
            recent = sorted(logs, key=lambda l: l.timestamp, reverse=True)[:5]
            for log in recent:
                z = abs((log.latency_ms - avg) / sd)
                if z > settings.anomaly_z_score:
                    self._fire_alert(
                        session,
                        alert_type="anomaly_detected",
                        severity="INFO",
                        message=f"Latency anomaly: {log.latency_ms:.0f}ms (Z-score={z:.1f}) for prompt '{log.prompt_id}' on model '{log.model_used}'",
                        threshold=settings.anomaly_z_score,
                        actual_value=z
                    )
                    break  # One alert per check cycle

    def _fire_alert(self, session, alert_type: str, severity: str, message: str, threshold: float, actual_value: float):
        """Create alert if a similar unresolved alert doesn't already exist."""
        existing = session.query(Alert).filter_by(
            alert_type=alert_type,
            resolved=False
        ).first()
        if existing:
            return  # Don't duplicate
        alert = Alert(
            alert_type=alert_type,
            severity=severity,
            message=message,
            threshold=threshold,
            actual_value=actual_value,
            resolved=False
        )
        session.add(alert)
        session.commit()
        logger.warning(f"[ALERT] {severity} — {message}")


monitor = Monitor()
