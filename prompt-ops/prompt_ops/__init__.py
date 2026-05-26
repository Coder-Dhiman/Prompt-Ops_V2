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
