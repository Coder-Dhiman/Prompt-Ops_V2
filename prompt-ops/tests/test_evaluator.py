import pytest
from unittest.mock import patch
from prompt_ops.evaluator import Evaluator

def test_composite_score_calculation():
    ev = Evaluator()
    with patch("prompt_ops.evaluator.httpx.post") as mock_post:
        # mock missing key bypass
        from prompt_ops.evaluator import settings
        settings.api_key = "fake_key"
        
        mock_response = mock_post.return_value
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": '{"relevance": 1.0, "accuracy": 1.0, "completeness": 0.5, "format_compliance": 0.0, "safety": 1.0}'
                }
            }]
        }
        res = ev.evaluate("prompt", "response", "id", "version")
        
        assert res is not None
        # r*0.3 + a*0.25 + c*0.2 + f*0.15 + s*0.1
        # 1*0.3 + 1*0.25 + 0.5*0.2 + 0*0.15 + 1*0.1
        # 0.3 + 0.25 + 0.1 + 0 + 0.1 = 0.75
        assert res.composite == pytest.approx(0.75)

def test_evaluator_returns_none_on_failure():
    ev = Evaluator()
    with patch("prompt_ops.evaluator.httpx.post", side_effect=Exception("Network down")):
        from prompt_ops.evaluator import settings
        settings.api_key = "fake_key"
        
        res = ev.evaluate("prompt", "response", "id", "version")
        assert res is None
