import sys
import subprocess
from pathlib import Path
from loguru import logger

def main():
    if len(sys.argv) < 2:
        print("Usage: prompt-ops [dashboard|test|info]")
        sys.exit(1)
        
    command = sys.argv[1]
    
    if command == "dashboard":
        # Launch streamlit dashboard
        dashboard_path = Path(__file__).parent.parent / "dashboard" / "app.py"
        if not dashboard_path.exists():
            print(f"Error: Dashboard file not found at {dashboard_path}")
            sys.exit(1)
            
        subprocess.run([sys.executable, "-m", "streamlit", "run", str(dashboard_path)])
        
    elif command == "test":
        print("Prompt-Ops installed successfully!")
        print("Run the demo with: python demo/run_showcase.py")
        
    elif command == "info":
        from prompt_ops.config import settings
        from prompt_ops.database.connection import db_manager
        print("Prompt-Ops Configuration Info")
        print("=============================")
        print(f"Database Path: {settings.db_url}")
        print(f"API Key Set: {'Yes' if settings.api_key else 'No'}")
        print(f"Default Model: {settings.default_model}")
        print(f"Auto-Evaluate: {settings.auto_evaluate}")
        
    else:
        print(f"Unknown command: {command}")
        print("Usage: prompt-ops [dashboard|test|info]")
        sys.exit(1)

if __name__ == "__main__":
    main()
