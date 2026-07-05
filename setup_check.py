"""
Setup Check Script — OpportunityOS AI
Diagnoses setup, env file, database status, and API credentials.
Useful for auto-graders and judges.
"""
import os
import sys
from pathlib import Path

def print_status(label: str, success: bool, info: str = ""):
    icon = "[OK]" if success else "[FAIL]"
    info_str = f" ({info})" if info else ""
    print(f"{icon} {label}{info_str}")

def run_checks():
    print("== OpportunityOS AI - Environment Diagnostics ==\n")
    
    # 1. Check Python version
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print_status("Python Version", True, py_version)
    
    # 2. Check workspace files
    required_dirs = ["core", "agents", "ui", "assets"]
    missing_dirs = [d for d in required_dirs if not Path(d).exists()]
    print_status("Core Directories Check", len(missing_dirs) == 0, f"Missing: {missing_dirs}" if missing_dirs else "All present")
    
    # 3. Check environment file
    env_path = Path(".env")
    print_status(".env File Exists", env_path.exists())
    
    # 4. Check dependencies imports
    try:
        import streamlit
        import langgraph
        import google.generativeai
        print_status("Core Dependencies Installed", True)
    except ImportError as e:
        print_status("Core Dependencies Installed", False, f"Missing module: {e.name}")
        
    # 5. Check API keys
    from dotenv import load_dotenv
    load_dotenv()
    
    gemini_key = os.getenv("GOOGLE_API_KEY", "")
    print_status("GOOGLE_API_KEY Set", len(gemini_key) > 5, "Free tier/Pro supported")
    
    firecrawl_key = os.getenv("FIRECRAWL_API_KEY", "")
    print_status("FIRECRAWL_API_KEY Set (Optional)", len(firecrawl_key) > 5, "Required for scouts & deep resolver")
    
    tavily_key = os.getenv("TAVILY_API_KEY", "")
    print_status("TAVILY_API_KEY Set (Optional)", len(tavily_key) > 5, "Required for web query discovery")
    
    # 6. Check database init
    try:
        from core.memory import get_db, init_db
        init_db()
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cursor.fetchall()]
        print_status("Database Verification", True, f"Tables: {tables}")
        conn.close()
    except Exception as e:
        print_status("Database Verification", False, str(e))
        
    print("\n------------------------------------------------")

if __name__ == "__main__":
    run_checks()
