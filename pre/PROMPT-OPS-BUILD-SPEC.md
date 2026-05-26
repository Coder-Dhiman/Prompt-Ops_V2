# PROMPT-OPS Build Specification
> Feed this file to an agentic AI to build the PROMPT-OPS middleware SDK from scratch.

---

## What you are building

A lightweight, open-source Python middleware SDK called `prompt-ops`. It wraps any LLM function via a decorator and adds closed-loop optimization: quality scoring, prompt A/B testing, temperature optimization, cost-aware model routing, telemetry, and a dashboard. The host app requires zero structural changes beyond adding the decorator.

---

## Constraints

- Python 3.9+ compatible
- No heavy ML dependencies (no torch, no transformers)
- SQLite by default, SQLAlchemy ORM so Postgres works as a drop-in
- All optimization runs async in background threads — never block the decorated function's return
- If anything inside the SDK fails, the original function's response must still be returned — no exceptions propagate to the host app
- Total install size under 15 MB (core, no dashboard)
- Dashboard is an optional extra: `pip install prompt-ops[dashboard]`

---

## Repository structure to create

```
prompt-ops/
├── prompt_ops/
│   ├── __init__.py              # public API exports
│   ├── decorator.py             # @optimize implementation
│   ├── orchestrator.py          # pipeline: select → call → log → evaluate
│   ├── evaluator.py             # LLM-as-Judge, 5 dimensions
│   ├── optimizer.py             # prompt versioning, A/B testing, auto-promote
│   ├── temperature.py           # temperature sweep experiments
│   ├── router.py                # cost-aware tier cascade
│   ├── telemetry.py             # request logging, monitor, alerts
│   ├── config.py                # pydantic-settings, env vars, model tiers
│   └── database/
│       ├── __init__.py
│       ├── models.py            # 8 SQLAlchemy table definitions
│       └── connection.py        # session management, auto-init on import
├── dashboard/
│   └── app.py                   # Streamlit dashboard, 8 pages
├── examples/
│   └── quickstart.py            # minimal working example
├── tests/
│   ├── test_decorator.py
│   ├── test_evaluator.py
│   └── test_router.py
├── pyproject.toml
├── README.md
└── .env.example
```

---

## Layer 1 — Decorator (`prompt_ops/decorator.py`)

This is the most critical piece. Build it first and get it right.

### Signature

```python
def optimize(
    prompt_id: str,
    ab_testing: bool = True,
    enable_cost_routing: bool = False,
):
    ...
```

### Behaviour

1. Wraps the decorated function using `functools.wraps` — preserve signature, docstring, return type.
2. On each call:
   a. Extract the prompt string — check for a `prompt` kwarg first, then fall back to the first positional arg.
   b. If `ab_testing=True`, ask the optimizer to pick a prompt version and inject it as the `prompt` kwarg.
   c. If `enable_cost_routing=True`, ask the router which model to use and pass it as a `model` kwarg if the function accepts one.
   d. Record `start_time = time.monotonic()`.
   e. Call the original function with the (possibly modified) arguments.
   f. Record `latency_ms = (time.monotonic() - start_time) * 1000`.
   g. Submit evaluation + telemetry logging to a `ThreadPoolExecutor` — do not await.
   h. Return an `OptimizeResult` wrapping the original response.
3. Wrap steps 2a–2h in a broad `try/except`. On any exception, log the error and return the original function's result directly.

### OptimizeResult

```python
@dataclass
class OptimizeResult:
    content: Any           # original return value from the decorated function
    quality_score: float | None = None   # filled in async after evaluation
    prompt_version: str | None = None
    model_used: str | None = None
    cost_saved_usd: float = 0.0
    latency_ms: float = 0.0
```

### Example of correct usage after building

```python
from prompt_ops import optimize

@optimize(prompt_id="summarize", ab_testing=True, enable_cost_routing=True)
def summarize(prompt: str) -> str:
    return openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    ).choices[0].message.content

result = summarize("Explain quantum computing")
print(result.content)        # the actual summary
print(result.quality_score)  # scored async, may be None immediately
```

---

## Layer 2 — Evaluator (`prompt_ops/evaluator.py`)

### Purpose

Uses a judge LLM to score every response on 5 dimensions. Runs after the call in a background thread.

### Judge model

Default: `google/gemini-2.0-flash-001` via OpenRouter. Configurable via `PROMPT_OPS_JUDGE_MODEL` env var.

### Evaluation prompt to send to the judge

```
You are a strict quality evaluator for LLM responses.

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
{
  "relevance": 0.0,
  "accuracy": 0.0,
  "completeness": 0.0,
  "format_compliance": 0.0,
  "safety": 0.0,
  "composite": 0.0
}

Compute composite as: (relevance * 0.3) + (accuracy * 0.25) + (completeness * 0.2) + (format_compliance * 0.15) + (safety * 0.1)
```

### EvaluationResult dataclass

```python
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
```

### Error handling

If the judge call fails or returns invalid JSON, return `None` silently. Never raise.

---

## Layer 3 — Prompt versioning & A/B testing (`prompt_ops/optimizer.py`)

### PromptVersion model (stored in DB)

```
id, prompt_id, version_name, template, traffic_weight, 
request_count, avg_quality_score, is_active, created_at
```

### Key methods

```python
class PromptManager:
    def create_version(self, prompt_id: str, template: str, name: str, traffic_weight: float = 1.0) -> PromptVersion
    def select_version(self, prompt_id: str) -> PromptVersion   # weighted random selection
    def update_metrics(self, version_id: int, quality_score: float) -> None
    def maybe_promote(self, prompt_id: str) -> None             # check and auto-promote
```

### Traffic splitting

Use `random.choices(versions, weights=[v.traffic_weight for v in versions])`.

### Auto-promote logic

After every `update_metrics` call, check:
- If any version has `request_count >= 20` and `avg_quality_score >= AUTO_PROMOTE_THRESHOLD` (default 0.85)
- And it is strictly better than all other active versions
- Then set its `traffic_weight = 1.0` and all others to `0.0`
- Log the promotion event

### Template injection

When a version is selected, inject its template by replacing `{input}` with the actual prompt:
```python
injected = version.template.replace("{input}", original_prompt)
```

---

## Layer 4 — Temperature optimizer (`prompt_ops/temperature.py`)

### Purpose

Run a controlled sweep to find the optimal temperature for a given prompt, then store and reuse it.

### Method signature

```python
def run_experiment(
    prompt_id: str,
    prompt_text: str,
    temp_min: float = 0.0,
    temp_max: float = 1.5,
    temp_step: float = 0.3,
    trials_per_step: int = 3,
) -> TemperatureResult
```

### Algorithm

```
for temp in range(temp_min, temp_max, temp_step):
    scores = []
    for _ in range(trials_per_step):
        response = call_llm(prompt_text, temperature=temp)
        score = evaluator.evaluate(prompt_text, response)
        scores.append(score.composite)
    avg_quality = mean(scores)
    consistency = 1 - stdev(scores)   # higher = more consistent
    composite = avg_quality * (0.7 + 0.3 * consistency)

best_temp = temp with highest composite
store best_temp in DB for this prompt_id
```

### TemperatureResult dataclass

```python
@dataclass
class TemperatureResult:
    prompt_id: str
    best_temperature: float
    best_composite_score: float
    all_results: list[dict]   # [{temp, avg_quality, consistency, composite}]
```

### Usage after experiment

Every subsequent decorated call with this `prompt_id` automatically uses `best_temperature` if available in DB.

---

## Layer 5 — Cost router (`prompt_ops/router.py`)

### Model tiers (default, all configurable)

```python
MODEL_TIERS = {
    "free":    ["meta-llama/llama-3.3-8b-instruct:free", "google/gemma-3-4b-it:free"],
    "cheap":   ["google/gemini-2.0-flash-001", "openai/gpt-4o-mini"],
    "mid":     ["anthropic/claude-3.5-haiku", "google/gemini-2.0-flash-thinking-exp"],
    "premium": ["openai/gpt-4o", "anthropic/claude-sonnet-4", "google/gemini-2.5-pro-preview"],
}
```

### Cascade logic

```
requested_model = "openai/gpt-4o"  # whatever the host passed

for tier in ["free", "cheap", "mid", "premium"]:
    try_model = first model in tier
    response = call_llm(prompt, model=try_model)
    score = evaluator.evaluate(prompt, response)
    
    if score.composite >= QUALITY_THRESHOLD (default 0.7):
        log routing decision: {original, used, tier, score, cost_saved}
        return response, try_model
    else:
        continue to next tier

# fallback: use the originally requested model
return call_llm(prompt, model=requested_model), requested_model
```

### Cost saved calculation

Estimate based on a static price table ($/1M tokens). Cost saved = price(requested) - price(used). Store in routing log.

---

## Layer 6 — Database (`prompt_ops/database/`)

### Auto-init

On `from prompt_ops import optimize`, call `init_database()` which creates all tables if they don't exist. DB path defaults to `~/.prompt-ops/data.db`. Override with `PROMPT_OPS_DB_URL` env var.

### 8 tables to create (SQLAlchemy models)

**telemetry_logs**
```
id, prompt_id, prompt_version, model_used, input_tokens, output_tokens,
latency_ms, cost_usd, success, error_message, quality_score, timestamp
```

**prompt_versions**
```
id, prompt_id, version_name, template, traffic_weight,
request_count, avg_quality_score, is_active, created_at
```

**evaluation_results**
```
id, telemetry_log_id, relevance, accuracy, completeness,
format_compliance, safety, composite, timestamp
```

**temperature_experiments**
```
id, prompt_id, best_temperature, best_composite_score, results_json, created_at
```

**cost_routing_logs**
```
id, prompt_id, requested_model, used_model, tier_used,
quality_score, cost_saved_usd, timestamp
```

**model_metrics**
```
id, model, hour_bucket, request_count, avg_latency_ms,
avg_quality, total_cost_usd, error_count
```

**alerts**
```
id, alert_type, severity, message, threshold, actual_value, resolved, created_at
```

**optimization_runs**
```
id, prompt_id, run_type, from_version, to_version, quality_before,
quality_after, notes, created_at
```

---

## Layer 7 — Telemetry & monitoring (`prompt_ops/telemetry.py`)

### TelemetryTracker

```python
class TelemetryTracker:
    def log_request(self, prompt_id, version, model, latency_ms, tokens_in, tokens_out, cost, success, error=None) -> int  # returns log id
    def update_quality(self, log_id: int, quality_score: float) -> None
    def get_stats(self, prompt_id: str = None, hours: int = 24) -> dict
```

### Monitor (runs on a background thread, checks every 5 minutes)

Alert conditions (all configurable via env vars):
- Average latency > 2000ms → severity WARNING
- Error rate > 5% → severity HIGH  
- Total cost today > $10 → severity MEDIUM
- Z-score of any metric > 2.0 → severity INFO (anomaly)

Z-score anomaly detection:
```python
z = (current_value - rolling_mean) / rolling_std
if abs(z) > ANOMALY_THRESHOLD (default 2.0):
    fire_alert("anomaly", ...)
```

---

## Layer 8 — Config (`prompt_ops/config.py`)

Use `pydantic-settings`. Read from environment variables with `PROMPT_OPS_` prefix.

```python
class Settings(BaseSettings):
    # API
    api_key: str = ""                          # PROMPT_OPS_API_KEY or OPENROUTER_API_KEY
    base_url: str = "https://openrouter.ai/api/v1"
    default_model: str = "meta-llama/llama-3.3-8b-instruct:free"
    judge_model: str = "google/gemini-2.0-flash-001"

    # Database
    db_url: str = f"sqlite:///{Path.home()}/.prompt-ops/data.db"

    # Evaluation
    auto_evaluate: bool = True
    evaluation_sample_rate: float = 1.0       # 0.1 = evaluate 10% of calls

    # Optimization
    auto_promote_threshold: float = 0.85
    auto_retire_threshold: float = 0.40

    # Temperature
    temp_min: float = 0.0
    temp_max: float = 1.5
    temp_step: float = 0.3
    temp_trials: int = 3

    # Cost routing
    cost_routing_enabled: bool = False
    quality_threshold: float = 0.7

    # Alerting
    latency_threshold_ms: float = 2000.0
    error_rate_threshold: float = 0.05
    cost_threshold_usd: float = 10.0
    anomaly_z_score: float = 2.0

    class Config:
        env_prefix = "PROMPT_OPS_"
        env_file = ".env"
```

---

## Layer 9 — Dashboard (`dashboard/app.py`)

Streamlit app. Launch with `streamlit run dashboard/app.py` or `python -m prompt_ops.dashboard`.

### 8 pages

```
1. Overview          — total requests, avg quality, active prompts, cost today (KPI cards)
2. Model monitoring  — latency over time, token usage, error rate (line charts)
3. Prompt A/B        — version comparison table, quality bar chart, traffic split pie
4. Quality scores    — score distribution histogram, per-dimension radar chart
5. Temperature       — quality vs temperature line chart, consistency overlay
6. Cost routing      — tier distribution pie, routing log table, total saved $
7. Alerts            — active alerts table, alert history, severity breakdown
8. Settings          — show current config values, allow editing DB path and thresholds
```

Use `plotly` for all charts. Read directly from the SQLite DB using SQLAlchemy sessions.

---

## Public API (`prompt_ops/__init__.py`)

This is what developers import. Keep it minimal.

```python
from prompt_ops.decorator import optimize, OptimizeResult
from prompt_ops.optimizer import prompt_manager
from prompt_ops.temperature import temperature_optimizer
from prompt_ops.database.connection import init_database

# auto-init on import
init_database()

__all__ = [
    "optimize",
    "OptimizeResult", 
    "prompt_manager",
    "temperature_optimizer",
    "init_database",
]

__version__ = "0.1.0"
```

---

## pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "prompt-ops"
version = "0.1.0"
description = "Lightweight LLM middleware for automatic prompt optimization"
requires-python = ">=3.9"
license = { text = "MIT" }
dependencies = [
    "httpx>=0.27.0",
    "tenacity>=8.2.0",
    "sqlalchemy>=2.0.0",
    "pydantic-settings>=2.0.0",
    "loguru>=0.7.0",
]

[project.optional-dependencies]
dashboard = [
    "streamlit>=1.35.0",
    "plotly>=5.20.0",
]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "black>=24.0.0",
    "ruff>=0.4.0",
    "mypy>=1.9.0",
]

[project.scripts]
prompt-ops = "prompt_ops.__main__:main"
```

---

## .env.example

```bash
# Required — get a free key at https://openrouter.ai/keys
PROMPT_OPS_API_KEY=sk-or-v1-your-key-here

# Optional overrides
PROMPT_OPS_JUDGE_MODEL=google/gemini-2.0-flash-001
PROMPT_OPS_DB_URL=sqlite:///~/.prompt-ops/data.db
PROMPT_OPS_AUTO_EVALUATE=true
PROMPT_OPS_EVALUATION_SAMPLE_RATE=1.0
PROMPT_OPS_QUALITY_THRESHOLD=0.7
PROMPT_OPS_COST_ROUTING_ENABLED=false
PROMPT_OPS_LATENCY_THRESHOLD_MS=2000
```

---

## examples/quickstart.py

Generate this file as a working minimal example:

```python
"""
PROMPT-OPS quickstart — runs with a free OpenRouter key.
pip install prompt-ops
export PROMPT_OPS_API_KEY=sk-or-v1-...
python quickstart.py
"""
import os
from prompt_ops import optimize, prompt_manager
from prompt_ops.database import init_database

init_database()

# Register two prompt versions to A/B test
prompt_manager.create_version(
    prompt_id="explain",
    template="Explain this simply: {input}",
    name="simple",
    traffic_weight=0.5,
)
prompt_manager.create_version(
    prompt_id="explain",
    template="You are an expert teacher. Explain this concept clearly with an example: {input}",
    name="expert",
    traffic_weight=0.5,
)

# Decorate any LLM function — this one uses httpx directly
import httpx, json

@optimize(prompt_id="explain", ab_testing=True)
def explain(prompt: str) -> str:
    resp = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['PROMPT_OPS_API_KEY']}"},
        json={
            "model": "meta-llama/llama-3.3-8b-instruct:free",
            "messages": [{"role": "user", "content": prompt}]
        },
        timeout=30,
    )
    return resp.json()["choices"][0]["message"]["content"]

# Make some calls
for topic in ["quantum computing", "how TCP works", "what is gradient descent"]:
    result = explain(topic)
    print(f"\nTopic: {topic}")
    print(f"Response: {result.content[:200]}...")
    print(f"Version used: {result.prompt_version}")
    print(f"Quality: {result.quality_score}")

print("\nDone. Run: streamlit run dashboard/app.py")
```

---

## Tests to write

### test_decorator.py
- Decorator returns `OptimizeResult` with `.content` matching original function return
- Decorator does not raise when inner function raises — returns original exception result
- Decorator does not raise when evaluator fails
- `functools.wraps` preserves `__name__`, `__doc__`, `__annotations__`

### test_evaluator.py
- Returns `None` on network failure (mocked)
- Returns `None` on invalid JSON from judge
- Composite score matches formula: `r*0.3 + a*0.25 + c*0.2 + f*0.15 + s*0.1`

### test_router.py
- Uses free tier model when quality >= threshold
- Escalates to next tier when quality < threshold
- Falls back to requested model after all tiers fail
- Logs routing decision to DB

---

## README.md sections to write

1. One-line description
2. Install (`pip install prompt-ops` and `pip install prompt-ops[dashboard]`)
3. Quickstart (5 lines of code — import, decorate, call, print result)
4. What you get out of the box (bullet list of 5 features)
5. Configuration (table of env vars)
6. Dashboard (one command to launch)
7. How it works (brief paragraph on the closed loop)
8. Contributing
9. License (MIT)

---

## Build order for the agent

Execute in this exact order. Do not proceed to the next step until the current one is working and tested.

1. Create repo structure and `pyproject.toml`
2. Build `config.py` — settings load from env vars
3. Build `database/models.py` and `database/connection.py` — tables create on import
4. Build `evaluator.py` — can evaluate a prompt/response pair, returns None on failure
5. Build `decorator.py` and `OptimizeResult` — wraps any function, fallback is rock solid
6. Build `optimizer.py` — create versions, select by weight, update metrics, auto-promote
7. Build `temperature.py` — sweep experiment, store best temp, use on future calls
8. Build `router.py` — tier cascade with quality gate
9. Build `telemetry.py` — log every call, monitor runs in background
10. Build `orchestrator.py` — wire all layers together into the pipeline the decorator calls
11. Build `dashboard/app.py` — 8 Streamlit pages reading from DB
12. Write `examples/quickstart.py` and verify it works end-to-end
13. Write tests
14. Write README
15. Verify `pip install -e .` works cleanly
