import threading
from typing import Optional
from loguru import logger
from prompt_ops.database.connection import get_session
from prompt_ops.database.models import TelemetryLog, Alert

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

telemetry_tracker = TelemetryTracker()
