"""
Prompt-Ops V2: A lightweight, decorator-based SDK for LLM prompt optimization,
cost routing, and telemetry.
"""

from .decorator import optimize
from .config import settings
from .database.connection import init_database, get_session as get_db
from .client import llm_client, LLMClient, LLMResponse
from .monitor import monitor

__version__ = "2.0.0"

__all__ = [
    "optimize",
    "settings",
    "init_database",
    "get_db",
    "llm_client",
    "LLMClient",
    "LLMResponse"
]

# Start the background monitoring daemon automatically when the package is imported
monitor.start()
