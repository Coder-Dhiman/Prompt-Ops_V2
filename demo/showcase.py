import sys
import os
import time
from datetime import datetime, timezone

# Ensure prompt_ops is accessible
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "prompt-ops")))

from prompt_ops.decorator import optimize, OptimizeResult
from prompt_ops.optimizer import prompt_manager
from prompt_ops.database.connection import init_database
from prompt_ops.evaluator import evaluator, EvaluationResult

# 1. Setup mock data and mock the evaluator
init_database()

# Mock the evaluator so we get dummy scores without requiring an API key
original_evaluate = evaluator.evaluate
def mock_evaluate(prompt: str, response: str, prompt_id: str, prompt_version: str):
    # This mock allows both the router and the async evaluator to pass without internet
    score = 0.95 if "Mock response" in response else 0.5
    return EvaluationResult(
        relevance=0.9,
        accuracy=1.0,
        completeness=1.0,
        format_compliance=0.9,
        safety=1.0,
        composite=score,
        prompt_id=prompt_id,
        prompt_version=prompt_version,
        timestamp=datetime.now(timezone.utc)
    )
evaluator.evaluate = mock_evaluate

# Add a mock prompt version for A/B testing
try:
    prompt_manager.create_version(
        prompt_id="demo_prompt",
        name="v2_friendly",
        template="You are a super friendly AI, say hello to the user: {input}",
        traffic_weight=1.0 # Guarantee we use this one instead of bare input
    )
except Exception as e:
    pass

# Mock best temperature in db
try:
    from prompt_ops.database.connection import get_session
    from prompt_ops.database.models import TemperatureExperiment
    import json
    with get_session() as session:
        exp = session.query(TemperatureExperiment).filter_by(prompt_id="demo_prompt").first()
        if not exp:
            exp = TemperatureExperiment(
                prompt_id="demo_prompt",
                best_temperature=0.33,
                best_composite_score=0.92,
                results_json=json.dumps([])
            )
            session.add(exp)
        else:
            exp.best_temperature = 0.33
        session.commit()
except Exception as e:
    pass

# 2. Mock LLM Callable
def mock_llm_call(prompt: str, model: str = "meta-llama/llama-3.3-8b-instruct:free", temperature: float = 0.7):
    print(f"\n      > [LLM EXECUTION ENGINE]")
    print(f"      > Model Used: {model}")
    print(f"      > Temperature: {temperature}")
    print(f"      > Prompt Received:\n      > '{prompt}'")
    time.sleep(0.5) 
    response_text = f"Mock response generated successfully! (Model: {model})"
    print(f"      > Finished text generation.\n")
    return response_text


# ===============================================
# Scenario A: Standard execution WITHOUT PromptOps
# ===============================================
def generate_response_without_prompt_ops(prompt: str, model: str = "openai/gpt-4o", temperature: float = 0.9):
    return mock_llm_call(prompt, model, temperature)


# ===============================================
# Scenario B: Managed execution WITH PromptOps
# ===============================================
@optimize(prompt_id="demo_prompt", ab_testing=True, enable_cost_routing=True)
def generate_response_with_prompt_ops(prompt: str, model: str = "openai/gpt-4o", temperature: float = 0.9):
    return mock_llm_call(prompt, model, temperature)


def run_demo():
    user_input = "Hi there, could you explain quantum computing simply?"

    print("\n" + "=" * 70)
    print(" SCENARIO 1: WITHOUT PROMPT-OPS (Standard Developer Flow)")
    print("=" * 70)
    print("\nDeveloper writes a standard LLM function to call an expensive model ('openai/gpt-4o') with temperature 0.9.")
    
    # Called normally
    res_default = generate_response_without_prompt_ops(prompt=user_input, model="openai/gpt-4o", temperature=0.9)
    
    print(f"[Final App Output] -> '{res_default}'")
    
    print("\n" + "=" * 70)
    print(" SCENARIO 2: WITH PROMPT-OPS (Managed Flow)")
    print("=" * 70)
    print("\nDeveloper adds just one line: `@optimize(prompt_id='demo_prompt', ab_testing=True, enable_cost_routing=True)`")
    print("The code runs with exactly the same arguments as before...")
    
    # Called through decorator
    res_ops = generate_response_with_prompt_ops(prompt=user_input, model="openai/gpt-4o", temperature=0.9)
    
    # Unpack the OptimizeResult
    if isinstance(res_ops, OptimizeResult):
        print(f"[Final App Output] -> '{res_ops.content}'")
        print("\n" + "-" * 70)
        print(" [PROMPT-OPS TELEMETRY & DECISIONS INTERCEPTED]")
        print("-" * 70)
        print("Notice how the prompt was dynamically altered and the model changed to save routing costs and improve quality:")
        print(f" - Prompt Version Applied: '{res_ops.prompt_version}' (A/B testing injected a new template)")
        print(f" - Optimized Temperature Applied: 0.33 (Overridden from user's 0.9 based on past trials)")
        print(f" - Optimal Model Selected: '{res_ops.model_used}' (Cost Routing dynamically downgraded from expensive gpt-4o)")
        
        print("Waiting a moment for background operations (async eval and DB logging...)")
        time.sleep(1)
        print(f" - Background Quality Score: {res_ops.quality_score} (Continuous async grading on relevance/safety)")
        print(f" - Execution Latency: {res_ops.latency_ms:.2f} ms")
    else:
         print(f"[Final App Output] -> {res_ops}")

if __name__ == "__main__":
    run_demo()