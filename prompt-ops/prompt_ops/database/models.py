import json
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Engine
from sqlalchemy.orm import declarative_base, sessionmaker, Mapped, mapped_column
from typing import Any, Optional

Base = declarative_base()

class TelemetryLog(Base):
    __tablename__ = "telemetry_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    prompt_id: Mapped[str] = mapped_column(String, index=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    model_used: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class PromptVersion(Base):
    __tablename__ = "prompt_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    prompt_id: Mapped[str] = mapped_column(String, index=True)
    version_name: Mapped[str] = mapped_column(String)
    template: Mapped[str] = mapped_column(Text)
    traffic_weight: Mapped[float] = mapped_column(Float, default=1.0)
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class EvaluationResult(Base):
    __tablename__ = "evaluation_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    telemetry_log_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("telemetry_logs.id"), nullable=True)
    relevance: Mapped[float] = mapped_column(Float)
    accuracy: Mapped[float] = mapped_column(Float)
    completeness: Mapped[float] = mapped_column(Float)
    format_compliance: Mapped[float] = mapped_column(Float)
    safety: Mapped[float] = mapped_column(Float)
    composite: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class TemperatureExperiment(Base):
    __tablename__ = "temperature_experiments"
    id: Mapped[int] = mapped_column(primary_key=True)
    prompt_id: Mapped[str] = mapped_column(String, index=True, unique=True)
    best_temperature: Mapped[float] = mapped_column(Float)
    best_composite_score: Mapped[float] = mapped_column(Float)
    results_json: Mapped[str] = mapped_column(Text) # JSON string of list[dict]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class CostRoutingLog(Base):
    __tablename__ = "cost_routing_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    prompt_id: Mapped[str] = mapped_column(String, index=True)
    requested_model: Mapped[str] = mapped_column(String)
    used_model: Mapped[str] = mapped_column(String)
    tier_used: Mapped[str] = mapped_column(String)
    quality_score: Mapped[float] = mapped_column(Float)
    cost_saved_usd: Mapped[float] = mapped_column(Float, default=0.0)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class ModelMetric(Base):
    __tablename__ = "model_metrics"
    id: Mapped[int] = mapped_column(primary_key=True)
    model: Mapped[str] = mapped_column(String, index=True)
    hour_bucket: Mapped[datetime] = mapped_column(DateTime, index=True)
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    avg_quality: Mapped[float] = mapped_column(Float, default=0.0)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)

class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    alert_type: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(Text)
    threshold: Mapped[float] = mapped_column(Float)
    actual_value: Mapped[float] = mapped_column(Float)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class OptimizationRun(Base):
    __tablename__ = "optimization_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    prompt_id: Mapped[str] = mapped_column(String, index=True)
    run_type: Mapped[str] = mapped_column(String)
    from_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    to_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    quality_before: Mapped[float] = mapped_column(Float)
    quality_after: Mapped[float] = mapped_column(Float)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
