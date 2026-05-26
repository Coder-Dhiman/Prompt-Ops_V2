import functools
from dataclasses import dataclass
from typing import Any

from prompt_ops.orchestrator import orchestrator

@dataclass
class OptimizeResult:
    content: Any           # original return value from the decorated function
    quality_score: float | None = None   # filled in async after evaluation
    prompt_version: str | None = None
    model_used: str | None = None
    cost_saved_usd: float = 0.0
    latency_ms: float = 0.0

def optimize(
    prompt_id: str,
    ab_testing: bool = True,
    enable_cost_routing: bool = False,
):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return orchestrator.execute_and_log(
                func,
                prompt_id,
                ab_testing,
                enable_cost_routing,
                *args,
                **kwargs
            )
        return wrapper
    return decorator
