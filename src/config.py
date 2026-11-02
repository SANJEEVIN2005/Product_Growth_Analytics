"""
Module: config.py
Description: Configuration and environment variable loader for Oracle database connectivity.
Reads from .env file (gitignored) or system environment variables to prevent hardcoding credentials.
"""

import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(ROOT_DIR, ".env")

def load_env_file(filepath: str = ENV_FILE) -> None:
    """Loads key-value pairs from .env into os.environ if not already set."""
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key not in os.environ:
                        os.environ[key] = val

# Load environment variables from .env
load_env_file()

# Database Connection Parameters
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "1521")
DB_SERVICE = os.getenv("DB_SERVICE", "XEPDB1")
DB_DSN = f"{DB_HOST}:{DB_PORT}/{DB_SERVICE}"

# Schema Credentials (Read via environment variables)
DB_USER = os.getenv("DB_USER", "growth_user")
DB_PASS = os.getenv("DB_PASSWORD", "")

READONLY_USER = os.getenv("READONLY_USER", "growth_readonly")
READONLY_PASS = os.getenv("READONLY_PASSWORD", "")
