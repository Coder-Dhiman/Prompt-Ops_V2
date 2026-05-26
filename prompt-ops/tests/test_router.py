import pytest
from prompt_ops.router import route_with_cascade
from prompt_ops.evaluator import EvaluationResult
from prompt_ops.database import init_database
from prompt_ops.config import settings

@pytest.fixture(autouse=True)
def init_db():
    settings.db_url = "sqlite:///:memory:"
    init_database()

def test_router_falls_back():
    def failing_caller(*args, **kwargs):
        raise ValueError("Model down")
    
    with pytest.raises(Exception):
        route_with_cascade("id", "prompt", failing_caller, "requested")
    
    # Wait, the spec says "fallback: use the originally requested model"
    # But if the originally requested model also fails, it will raise!
    # Let's mock it to succeed on fallback.
    
    def picky_caller(prompt, model=None, **kwargs):
        if model == "requested":
            return "fallback success"
        raise ValueError("All tier models fail")
    
    res, used = route_with_cascade("id", "prompt", picky_caller, "requested")
    assert res == "fallback success"
    assert used == "requested"

def test_router_uses_tier_when_quality_high(monkeypatch):
    from unittest.mock import MagicMock
    mock_eval = MagicMock(return_value=EvaluationResult(1,1,1,1,1,0.9,"id","v",None))
    monkeypatch.setattr("prompt_ops.router.evaluator.evaluate", mock_eval)

    def good_caller(prompt, model=None, **kwargs):
        return f"success from {model}"

    res, used = route_with_cascade("id", "prompt", good_caller, "openai/gpt-4o")
    # Will hit the free tier first and succeed
    assert res.startswith("success from meta-llama")
    assert used == "meta-llama/llama-3.3-8b-instruct:free"

def test_router_escalates_when_quality_low(monkeypatch):
    from unittest.mock import MagicMock
    
    def dynamic_eval(prompt, response, prompt_id, version):
        if "meta-llama" in response or "gemma-3-4b-it" in response:
            return EvaluationResult(1,1,1,1,1,0.4,"id","v",None) # low quality
        if "gemini-2.0-flash-001" in response:
            return EvaluationResult(1,1,1,1,1,0.8,"id","v",None) # high enough
        return EvaluationResult(1,1,1,1,1,1.0,"id","v",None)

    monkeypatch.setattr("prompt_ops.router.evaluator.evaluate", dynamic_eval)

    def caller(prompt, model=None, **kwargs):
        return f"resp from {model}"

    res, used = route_with_cascade("id", "prompt", caller, "requested")
    assert used == "google/gemini-2.0-flash-001"
