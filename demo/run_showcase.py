import os
import sys
import time
from colorama import init, Fore, Style

# Ensure the prompt_ops package is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "prompt-ops")))

from prompt_ops import optimize, init_database
from prompt_ops.client import llm_client
from prompt_ops.config import settings
from prompt_ops.optimizer import prompt_manager
from prompt_ops.temperature import temperature_optimizer

init(autoreset=True)

def check_setup():
    # Database is automatically initialized via prompt_ops/__init__.py, 
    # but we can call it explicitly per requirements
    init_database()
    
    # Check for API Key
    if not settings.api_key:
        print(f"{Fore.RED}Error: OpenRouter API key not set.")
        print(f"{Fore.YELLOW}Please set the PROMPT_OPS_API_KEY environment variable before running.")
        sys.exit(1)

def print_header(title):
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'='*60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  {title}")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'='*60}\n")

# ---------------------------------------------------------------------------
# Feature 1: Basic Telemetry
# ---------------------------------------------------------------------------
@optimize(prompt_id="demo_basic", ab_testing=False, enable_cost_routing=False)
def simple_chat(prompt: str, model: str = "google/gemini-2.0-flash-001"):
    response = llm_client.chat(prompt=prompt, model=model)
    return response.content

def demo_basic_telemetry():
    print_header("Feature 1: Basic Telemetry")
    print(f"{Fore.YELLOW}Calling simple_chat decorated with @optimize...{Style.RESET_ALL}")
    
    result = simple_chat("What is 2+2?")
    
    print(f"\n{Fore.GREEN}Response Content:{Style.RESET_ALL} {result.content}")
    print(f"{Fore.GREEN}Latency:{Style.RESET_ALL} {result.latency_ms:.2f} ms")
    print(f"{Fore.GREEN}Model Used:{Style.RESET_ALL} {result.model_used}")
    print(f"{Fore.MAGENTA}Note: Telemetry was logged to local SQLite DB automatically.{Style.RESET_ALL}")

# ---------------------------------------------------------------------------
# Feature 2: A/B Testing & Traffic Splitting
# ---------------------------------------------------------------------------
@optimize(prompt_id="ab_demo", ab_testing=True, enable_cost_routing=False)
def ab_chat(prompt: str):
    response = llm_client.chat(prompt=prompt)
    return response.content

def demo_ab_testing():
    print_header("Feature 2: A/B Testing & Traffic Splitting")
    print(f"{Fore.YELLOW}Registering 2 prompt versions for 'ab_demo'...{Style.RESET_ALL}")
    
    prompt_manager.create_version("ab_demo", "Answer concisely: {input}", "concise", traffic_weight=0.5)
    prompt_manager.create_version("ab_demo", "Answer like a pirate: {input}", "pirate", traffic_weight=0.5)
    
    print(f"\n{Fore.YELLOW}Looping 5 times to show traffic routing...{Style.RESET_ALL}")
    for i in range(5):
        result = ab_chat("Why is the ocean salty?")
        content_preview = result.content.replace('\n', ' ')[:70]
        print(f"{Fore.WHITE}Call {i+1}: Routed to version {Fore.CYAN}'{result.prompt_version}'{Style.RESET_ALL}")
        print(f"{Style.DIM}  -> {content_preview}...{Style.RESET_ALL}")
        time.sleep(0.5)  # slight pause to avoid rate limits

# ---------------------------------------------------------------------------
# Feature 3: Cost Routing (Cascade)
# ---------------------------------------------------------------------------
@optimize(prompt_id="routing_demo", ab_testing=False, enable_cost_routing=True)
def premium_chat(prompt: str, model: str = "openai/gpt-4o"):
    response = llm_client.chat(prompt=prompt, model=model)
    return response.content

def demo_cost_routing():
    print_header("Feature 3: Cost Routing (Cascade Fallback)")
    print(f"{Fore.YELLOW}Requesting expensive model: 'openai/gpt-4o' with cost_routing_enabled=True.")
    print(f"{Style.DIM}(The router evaluates cheaper models first and uses them if quality is acceptable.){Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}Routing in progress (this may take a few seconds as it evaluates)...{Style.RESET_ALL}")
    result = premium_chat("List 3 key principles of writing good code.")
    
    print(f"\n{Fore.GREEN}Requested Model:{Style.RESET_ALL} openai/gpt-4o")
    print(f"{Fore.GREEN}Actual Model Used:{Style.RESET_ALL} {result.model_used}")
    content_preview = result.content.replace('\n', ' ')[:80]
    print(f"{Style.DIM}  -> {content_preview}...{Style.RESET_ALL}")

# ---------------------------------------------------------------------------
# Feature 4: Temperature Optimization
# ---------------------------------------------------------------------------
def temp_chat_func(prompt_text: str, temperature: float):
    # A simple wrapper for the sweep
    response = llm_client.chat(prompt=prompt_text, temperature=temperature, model="google/gemini-2.0-flash-001")
    return response.content

def demo_temperature_sweep():
    print_header("Feature 4: Temperature Optimization")
    print(f"{Fore.YELLOW}Running temperature sweep to find the optimal temp for a specific task...")
    print(f"{Style.DIM}Sweep parameters: min=0.0, max=1.0, step=0.5, trials=1 (fast mode){Style.RESET_ALL}\n")
    
    result = temperature_optimizer.run_experiment(
        prompt_id="temp_demo",
        prompt_text="Write a 2-line poem about artificial intelligence.",
        call_llm_func=temp_chat_func,
        temp_min=0.0,
        temp_max=1.0,
        temp_step=0.5,
        trials_per_step=1
    )
    
    print(f"{Fore.GREEN}Sweep Complete!{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Optimal Temperature Found:{Style.RESET_ALL} {result.best_temperature}")
    print(f"{Fore.CYAN}Best Composite Score:{Style.RESET_ALL} {result.best_composite_score:.2f}\n")
    
    print(f"{Fore.WHITE}Sweep Results Detail:{Style.RESET_ALL}")
    for r in result.all_results:
        print(f"  - Temp {r['temp']:.1f}: Quality Score = {r['avg_quality']:.2f} | Composite = {r['composite']:.2f}")

# ---------------------------------------------------------------------------
# Feature 5: Evaluation
# ---------------------------------------------------------------------------
def demo_evaluation():
    print_header("Feature 5: Background Evaluation")
    print(f"{Fore.YELLOW}Calling simple_chat again...{Style.RESET_ALL}")
    
    result = simple_chat("Is the Earth flat? Answer in one sentence.")
    
    print(f"\n{Fore.WHITE}Result at Return Time:{Style.RESET_ALL}")
    print(f"  {Style.DIM}Content: {result.content[:60]}...{Style.RESET_ALL}")
    print(f"  {Style.DIM}Quality Score: {result.quality_score} (Evaluator is running async in the background){Style.RESET_ALL}")
    
    print(f"\n{Fore.YELLOW}Waiting 4 seconds for background evaluation to finish...{Style.RESET_ALL}")
    time.sleep(4)
    
    print(f"{Fore.GREEN}Updated Result Object:{Style.RESET_ALL}")
    if result.quality_score is not None:
        print(f"  {Fore.CYAN}Quality Score:{Style.RESET_ALL} {result.quality_score:.3f}")
    else:
        print(f"  {Fore.RED}Quality Score: None (Evaluation failed or timed out){Style.RESET_ALL}")

def main():
    check_setup()
    
    print(f"\n{Fore.MAGENTA}{Style.BRIGHT}🚀 PROMPT-OPS V2 SHOWCASE DEMO 🚀{Style.RESET_ALL}")
    
    try:
        demo_basic_telemetry()
        demo_ab_testing()
        demo_cost_routing()
        demo_temperature_sweep()
        demo_evaluation()
    except Exception as e:
        print(f"\n{Fore.RED}An error occurred during the demo: {e}{Style.RESET_ALL}")
        
    print(f"\n{Fore.MAGENTA}{Style.BRIGHT}✅ Showcase Complete! ✅{Style.RESET_ALL}")

if __name__ == "__main__":
    main()
