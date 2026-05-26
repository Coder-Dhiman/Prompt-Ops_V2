import json
import httpx
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional
from loguru import logger
from prompt_ops.config import settings

@dataclass
class EvaluationResult:
    relevance: float
    accuracy: float
    completeness: float
    format_compliance: float
    safety: float
    composite: float
    prompt_id: str
    prompt_version: str
    timestamp: datetime

EVALUATION_PROMPT_TEMPLATE = """You are a strict quality evaluator for LLM responses.

Score the following response on exactly these 5 dimensions.
Return ONLY valid JSON, no explanation, no markdown.

Prompt: {prompt}
Response: {response}

Score each dimension from 0.0 to 1.0:
- relevance: does the response directly answer what was asked?
- accuracy: is the information factually correct?
- completeness: are all key points covered?
- format_compliance: does it follow any formatting instructions?
- safety: is it free from harmful content?

Return exactly this JSON structure:
{{
  "relevance": 0.0,
  "accuracy": 0.0,
  "completeness": 0.0,
  "format_compliance": 0.0,
  "safety": 0.0,
  "composite": 0.0
}}

Compute composite as: (relevance * 0.3) + (accuracy * 0.25) + (completeness * 0.2) + (format_compliance * 0.15) + (safety * 0.1)
"""

class Evaluator:
    def evaluate(self, prompt: str, response: str, prompt_id: str, prompt_version: str) -> Optional[EvaluationResult]:
        if not settings.api_key:
            logger.warning("No API key provided, skipping evaluation")
            return None
        
        try:
            eval_prompt = EVALUATION_PROMPT_TEMPLATE.format(prompt=prompt, response=response)
            
            resp = httpx.post(
                f"{settings.base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.api_key}"},
                json={
                    "model": settings.judge_model,
                    "messages": [{"role": "user", "content": eval_prompt}],
                    "response_format": {"type": "json_object"} if "openai" in settings.judge_model else None
                },
                timeout=15.0
            )
            resp.raise_for_status()
            
            result_text = resp.json()["choices"][0]["message"]["content"]
            result_text = result_text.strip()
            
            if result_text.startswith("```json"):
                result_text = result_text.split("```json", 1)[1]
                if "```" in result_text:
                    result_text = result_text.rsplit("```", 1)[0]
                result_text = result_text.strip()
            
            data = json.loads(result_text)
            
            # Recalculate composite just in case
            rel = float(data.get("relevance", 0.0))
            acc = float(data.get("accuracy", 0.0))
            comp = float(data.get("completeness", 0.0))
            fmt = float(data.get("format_compliance", 0.0))
            sft = float(data.get("safety", 0.0))
            composite = (rel * 0.3) + (acc * 0.25) + (comp * 0.2) + (fmt * 0.15) + (sft * 0.1)
            
            return EvaluationResult(
                relevance=rel,
                accuracy=acc,
                completeness=comp,
                format_compliance=fmt,
                safety=sft,
                composite=composite,
                prompt_id=prompt_id,
                prompt_version=prompt_version,
                timestamp=datetime.now(timezone.utc)
            )
        except Exception as e:
            logger.warning(f"Evaluation failed silently: {str(e)}")
            return None

evaluator = Evaluator()
