import json
from loguru import logger
from prompt_ops.database.connection import get_session
from prompt_ops.database.models import CostRoutingLog
from prompt_ops.config import settings, MODEL_TIERS
from prompt_ops.evaluator import evaluator

def _estimate_cost_per_million(model: str) -> float:
    # A crude mock table to simulate costs
    if "free" in model.lower():
        return 0.0
    if "mini" in model.lower() or "flash" in model.lower() and "exp" not in model.lower():
        return 0.15
    if "haiku" in model.lower():
        return 0.25
    if "sonnet" in model.lower() or "gpt-4o" in model.lower():
        return 3.0
    return 1.0

def route_with_cascade(prompt_id: str, prompt_text: str, call_llm_func, requested_model: str):
    cost_requested = _estimate_cost_per_million(requested_model)
    
    for tier in ["free", "cheap", "mid", "premium"]:
        tier_models = MODEL_TIERS.get(tier, [])
        if not tier_models:
            continue
            
        try_model = tier_models[0]
        
        try:
            response = call_llm_func(prompt_text, model=try_model)
        except Exception as e:
            logger.warning(f"Tier {tier} model {try_model} failed: {e}")
            continue
        
        score_res = evaluator.evaluate(prompt_text, response, prompt_id, "routing")
        score = score_res.composite if score_res else 0.0
        
        if score >= settings.quality_threshold:
            cost_used = _estimate_cost_per_million(try_model)
            cost_saved = max(0.0, cost_requested - cost_used)
            
            _log_routing_decision(prompt_id, requested_model, try_model, tier, score, cost_saved)
            return response, try_model
            
    # Fallback to originally requested
    response = call_llm_func(prompt_text, model=requested_model)
    return response, requested_model

def _log_routing_decision(prompt_id: str, requested_model: str, used_model: str, tier_used: str, quality_score: float, cost_saved: float):
    with get_session() as session:
        log = CostRoutingLog(
            prompt_id=prompt_id,
            requested_model=requested_model,
            used_model=used_model,
            tier_used=tier_used,
            quality_score=quality_score,
            cost_saved_usd=cost_saved
        )
        session.add(log)
        session.commit()
