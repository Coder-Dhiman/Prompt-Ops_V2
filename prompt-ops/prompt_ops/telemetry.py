import threading
from typing import Optional
from datetime import datetime, timezone, timedelta
from loguru import logger
from prompt_ops.database.connection import get_session
from prompt_ops.database.models import TelemetryLog, Alert, ModelMetric

class TelemetryTracker:
    def log_request(self, prompt_id: str, version: Optional[str], model: Optional[str], latency_ms: float, tokens_in: int, tokens_out: int, cost: float, success: bool, error: Optional[str] = None) -> int:
        with get_session() as session:
            log = TelemetryLog(
                prompt_id=prompt_id,
                prompt_version=version,
                model_used=model,
                latency_ms=latency_ms,
                input_tokens=tokens_in,
                output_tokens=tokens_out,
                cost_usd=cost,
                success=success,
                error_message=error
            )
            session.add(log)
            session.commit()
            session.refresh(log)
            return log.id

    def update_quality(self, log_id: int, quality_score: float) -> None:
        with get_session() as session:
            log = session.query(TelemetryLog).filter_by(id=log_id).first()
            if log:
                log.quality_score = quality_score
                session.commit()

    def get_stats(self, prompt_id: Optional[str] = None, hours: int = 24) -> dict:
        """Query TelemetryLog for the last N hours, optionally filtered by prompt_id."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        with get_session() as session:
            query = session.query(TelemetryLog).filter(TelemetryLog.timestamp >= cutoff)
            if prompt_id:
                query = query.filter(TelemetryLog.prompt_id == prompt_id)
            logs = query.all()

            if not logs:
                return {
                    "total_requests": 0,
                    "successful_requests": 0,
                    "failed_requests": 0,
                    "avg_latency_ms": 0.0,
                    "total_tokens": 0,
                    "total_cost_usd": 0.0,
                    "avg_quality_score": None,
                }

            successful = [l for l in logs if l.success]
            failed = [l for l in logs if not l.success]
            quality_scores = [l.quality_score for l in logs if l.quality_score is not None]

            return {
                "total_requests": len(logs),
                "successful_requests": len(successful),
                "failed_requests": len(failed),
                "avg_latency_ms": sum(l.latency_ms for l in logs) / len(logs),
                "total_tokens": sum((l.input_tokens or 0) + (l.output_tokens or 0) for l in logs),
                "total_cost_usd": sum(l.cost_usd for l in logs),
                "avg_quality_score": sum(quality_scores) / len(quality_scores) if quality_scores else None,
            }

    def get_model_comparison(self, hours: int = 24) -> list[dict]:
        """Group telemetry by model_used and return per-model statistics."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        with get_session() as session:
            logs = session.query(TelemetryLog).filter(
                TelemetryLog.timestamp >= cutoff
            ).all()

            models: dict[str, list] = {}
            for log in logs:
                model = log.model_used or "unknown"
                models.setdefault(model, []).append(log)

            results = []
            for model, model_logs in models.items():
                quality_scores = [l.quality_score for l in model_logs if l.quality_score is not None]
                results.append({
                    "model": model,
                    "request_count": len(model_logs),
                    "avg_latency_ms": sum(l.latency_ms for l in model_logs) / len(model_logs),
                    "avg_quality": sum(quality_scores) / len(quality_scores) if quality_scores else None,
                    "total_cost_usd": sum(l.cost_usd for l in model_logs),
                    "error_count": sum(1 for l in model_logs if not l.success),
                })
            return results

    def update_model_metrics(self, model: str, latency_ms: float, quality: Optional[float], cost: float, success: bool) -> None:
        """Upsert into ModelMetric table for the current hour bucket."""
        now = datetime.now(timezone.utc)
        hour_bucket = now.replace(minute=0, second=0, microsecond=0)

        with get_session() as session:
            metric = session.query(ModelMetric).filter_by(
                model=model,
                hour_bucket=hour_bucket
            ).first()

            if metric:
                # Recompute running average for latency
                total_latency = metric.avg_latency_ms * metric.request_count + latency_ms
                if quality is not None and metric.avg_quality is not None:
                    total_quality = metric.avg_quality * metric.request_count + quality
                elif quality is not None:
                    total_quality = quality
                else:
                    total_quality = None

                metric.request_count += 1
                metric.avg_latency_ms = total_latency / metric.request_count
                if total_quality is not None:
                    metric.avg_quality = total_quality / metric.request_count
                metric.total_cost_usd += cost
                if not success:
                    metric.error_count += 1
            else:
                metric = ModelMetric(
                    model=model,
                    hour_bucket=hour_bucket,
                    request_count=1,
                    avg_latency_ms=latency_ms,
                    avg_quality=quality,
                    total_cost_usd=cost,
                    error_count=0 if success else 1,
                )
                session.add(metric)

            session.commit()

telemetry_tracker = TelemetryTracker()
