# PROMPT-OPS

🚀 **Lightweight LLM middleware for automatic prompt optimization, routing, and telemetry.**

Prompt-Ops is an open-source tool designed to wrap around your existing LLM calls, providing instant observability, cost-saving cascades, A/B testing, dynamic temperature scaling, and background LLM-as-a-judge evaluations—all without blocking your main application thread.

---

## 🎯 Key Features

- **Non-blocking Telemetry & Logging:** Logs prompt execution, metrics, and metadata transparently without introducing latency.
- **Model Routing Cascade:** Automatically route requests to cheaper or faster models based on complexity and fallback limits to save costs (configurable tier cascades).
- **Background Async Evaluations:** Run automated LLM-as-a-judge evaluations to measure response quality and adherence to guidelines offline.
- **Automatic Prompt A/B Testing:** Evaluate variations of prompts and automatically promote the best string based on defined metrics.
- **Dynamic Temperature Scaling:** Automatically adjust `temperature` based on the context length or prompt entropy to prevent hallucinations on complex requests.
- **Streamlit Dashboard:** A built-in graphical interface for monitoring metrics, viewing traces, and comparing prompt version history.

---

## 📦 Install

**Core SDK** (Lightweight, no UI dependencies):
```bash
pip install prompt-ops
```

**With Streamlit Dashboard:**
```bash
pip install prompt-ops[dashboard]
```

---

## ⚡ Quickstart

Getting started is as easy as wrapping your function with the `@optimize` decorator!

```python
from prompt_ops import optimize

@optimize(prompt_id="greet_user", ab_testing=True)
def generate_greeting(prompt: str) -> str:
    # Your LLM execution logic here
    # E.g., client.chat.completions.create(...)
    return "Hello " + prompt

# Execute normally; telemetry and optimization run in the background
response = generate_greeting("world")
print(response)
```

### Advanced Usage: Custom Constraints

You can specify detailed constraints, routing rules, and thresholds:

```python
from prompt_ops import optimize

@optimize(
    prompt_id="complex_extraction",
    ab_testing=True,
    route_on_cost=True,
    eval_rules=["No JSON syntax errors", "Must be polite"],
    dynamic_temperature=True
)
def extract_data(text: str) -> dict:
    pass
```

---

## ⚙️ Configuration

Prompt-Ops relies on environment variables for configuration. You can also specify these in a `.env` file at your project root.

| Environment Variable | Description | Default |
|---|---|---|
| `PROMPT_OPS_API_KEY` | Your OpenRouter or AI provider API key | `None` *Required* |
| `PROMPT_OPS_DB_URL` | SQLAlchemy connection string (SQLite, Postgres) | `sqlite:///prompt_ops.db` |
| `PROMPT_OPS_JUDGE_MODEL` | The LLM to use for background evaluation | `gpt-4o-mini` |
| `PROMPT_OPS_COST_ROUTING_ENABLED` | Toggle the model cost fallback cascade | `false` |
| `PROMPT_OPS_LATENCY_THRESHOLD_MS` | Alert threshold limit for response delay | `2000` |
| `PROMPT_OPS_LOG_LEVEL` | Logging verbosity (INFO, DEBUG, ERROR) | `INFO` |

---

## 📊 Dashboard

Prompt-Ops comes with a ready-to-use Streamlit dashboard to visualize your data locally.

```bash
streamlit run dashboard/app.py
```

**Dashboard Features:**
- Trace browser: View inputs, outputs, tokens, and latency.
- Prompts Leaderboard: See which A/B testing variant is winning.
- Cost Analysis: Monitor savings achieved via the routing cascade.
- Evaluation metrics: View pass/fail rates from your LLM judge.

---

## 🧠 How It Works Under the Hood

1. **Decoration:** When you decorate a function, it replaces the call with a proxy from the `Orchestrator`.
2. **Execution:** The original call logic runs securely. Before returning, the output is captured.
3. **Background Threading:** Telemetry payload (latency, tokens, rules) is offloaded to a background thread.
4. **Evaluation (`evaluator.py`):** The background thread asks the `Judge` model to score the interaction.
5. **Database Storage:** The `database` module commits the execution record and evaluation result to your local SQLite or Postgres instance.
6. **Optimization (`optimizer.py`):** If enough A/B testing data is gathered, it promotes the winning prompt formulation to production status automatically.

---

## 🛠️ Architecture

Overview of the package components:
- `decorator.py`: Provides the user-facing `@optimize` wrapper.
- `orchestrator.py`: Manages the lifecycle, threads, and data flow.
- `router.py`: Handles model tier cascading for cost and speed tuning.
- `evaluator.py`: Async LLM-as-a-judge execution logic.
- `optimizer.py`: Analyzes historical evaluation scores to mutate or promote prompts.
- `temperature.py`: Dynamically computes model parameters based on input entropy.
- `telemetry.py`: Traces latency and token consumption.
- `database/`: Extensible SQLAlchemy models and connection pooling.

---

## 🤝 Contributing

We welcome contributions! 

1. Fork the repo and create your feature branch.
2. Ensure you add tests in the `tests/` directory for any new logic.
3. Run `pytest tests/` before submitting.
4. Open a lightweight PR!

---

## 📝 License  
MIT License - See LICENSE for details.