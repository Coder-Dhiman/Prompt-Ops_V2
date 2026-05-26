# Prompt-Ops Showcase Demo

This directory contains a demonstration script (`showcase.py`) to illustrate the power and simplicity of the `prompt-ops` middleware. It features a complete side-by-side comparison of a standard LLM function execution versus an optimized execution leveraging the `prompt-ops` framework.

## Overview

Prompt-Ops is a lightweight middleware layer that automatically optimizes Large Language Model (LLM) prompts, regulates temperatures based on historical performance, saves costs by transparently routing to cheaper models when possible, and provides comprehensive telemetry and background evaluation without adding any latency to the critical path of your code.

The showcase creates a mock LLM engine and executes a standard text generation request. It compares two approaches:

1. **Without Prompt-Ops**: A traditional function call pointing to an expensive model with hardcoded parameters.
2. **With Prompt-Ops**: The exact same function call wrapped with the `@optimize` decorator, enabling A/B prompt testing, optimal temperature injection, cost-based model routing, and asynchronous response evaluations.

## Deep Dive: How It Works Internally

### The `@optimize` Decorator
The entire framework operates through a single decorator applied to your existing LLM invocation functions. 
```python
@optimize(prompt_id="demo_prompt", ab_testing=True, enable_cost_routing=True)
def my_llm_call(prompt, model, temperature):
    ...
```
When this function is called, the execution is intercepted by the `Orchestrator`. The Orchestrator applies safety and optimization transformations to the passed arguments dynamically.

### Scenario A: Without Prompt-Ops (Standard Developer Flow)
A developer creates a function that sends a prompt to an LLM. In this scenario, they request `openai/gpt-4o` with a temperature of `0.9` and pass a raw user prompt. 
- **Execution Mechanism:** The Python code immediately invokes the LLM API.
- **Result:** The execution strictly obeys the parameters. It goes to the expensive model, blindly applies the unoptimized temperature, and uses the raw input prompt, doing no telemetry, tracking, or assessment of the output. 

### Scenario B: With Prompt-Ops (Managed Flow)

In the optimized flow, the middleware catches the request and performs a series of intercept operations dynamically:

#### 1. A/B Testing (Dynamic Prompt Versioning)
Instead of using the raw user input, the Orchestrator accesses the `PromptManager` and queries the SQLite database for active templates tied to the `prompt_id` `"demo_prompt"`. 
- **The Process:** It discovers multiple prompt versions. Based on the tracked `traffic_weight`, it probabilistically selects a template (e.g., `"You are a super friendly AI, say hello to the user: {input}"`).
- **The Result:** The developer's original string is injected into this template, and the `{input}` placeholder is replaced, giving a much richer and more contextual prompt dynamically.

#### 2. Adaptive Temperature Tuning
LLM temperature heavily affects consistency and quality, but finding the exact right temperature is difficult.
- **The Process:** The `TemperatureOptimizer` queries previous experimental metrics. It sees that earlier evaluations have scored a temperature of `0.33` higher in `composite` quality (which factors in consistency and average quality) compared to `0.9`.
- **The Result:** It forcibly overwrites the developer's requested `0.9` with `0.33` in the arguments list before calling the LLM.

#### 3. Cost Routing (Model Cascading)
To minimize costs, developers can toggle `enable_cost_routing=True`. 
- **The Process:** The original function requested an expensive model (`openai/gpt-4o`). Prompt-ops realizes this belongs to the `"premium"` tier. Instead of blindly passing it, the router intercepts it and tests the prompt against a cheaper tier model first (like `google/gemini-2.0-flash-001` or `meta-llama/llama-3.3-8b-instruct:free`). 
- **The Evaluation Phase:** The response from the cheaper model is quickly evaluated by the internal framework's threshold limit. If the cheaper model provides a satisfactory response (e.g., quality > `0.7`), the router permanently substitutes the model. 
- **The Result:** Thousands of dollars in API credits are saved without sacrificing end-user output quality.

#### 4. Asynchronous Quality Evaluation & Telemetry
Once a valid response is generated, it immediately yields the response object back to the main thread—acting with zero perceptible latency overhead.
- **The Process:** In a non-blocking `ThreadPoolExecutor`, the Orchestrator triggers an `Evaluator`. The Evaluator sends both the initial prompt and the generated response to an "LLM-as-a-Judge". 
- **The Metrics:** The Judge strictly scores exactly 5 dimensions in pure JSON format:
  - **Relevance** (30% weight)
  - **Accuracy** (25% weight)
  - **Completeness** (20% weight)
  - **Format Compliance** (15% weight)
  - **Safety** (10% weight)
- **The Result:** These dimensions form a final `Composite Score`. This score is instantly written to the local SQLite database. The PromptManager absorbs this score to constantly promote or demote A/B testing prompt versions, heavily favoring those that produce higher aggregate composite metrics.

## Demo Code Architecture

The demo script (`demo/showcase.py`) handles all of the above via Python standard setups.
Because it's a showcase designed to run rapidly without making external LLM API calls, we apply some local "mocks":
- **Database Initialized In-Memory / Local file**: `init_database()` constructs local tables.
- **Mocked Evaluator**: The evaluator is patched locally in the script to return `0.95` without hitting an OpenAI endpoint, purely to show how the telemetry consumes it.
- **Mocked Temperature Trials**: The script simulates a pre-existing optimal database state for temperature routing.
- **Mock LLM Driver**: We emulate `python requests` taking time and returning generated text.

## How to Run the Demo

### 1. Install Dependencies
Ensure you have installed the `prompt-ops` package in editable mode from the root of the workspace so your environment resolves the decorator properly:

```bash
pip install -e ./prompt-ops
```

### 2. Run the Script
From the root of the workspace, simply execute the script:

```bash
python demo/showcase.py
```

### Output Expectations
When you run the script, you will see a console output dividing the execution into two blocks. 

In **Block 1**, you will see standard execution logic mimicking a regular bare LLM application. It outputs straight from the mocked remote host.

In **Block 2**, you will see rich intercept telemetry indicating precisely how Prompt-Ops hijacked parameters to optimize the run. It will display the overridden temperature, the newly selected cheaper model, the applied dynamic template, and the background execution trace of the evaluator grading the returned message.