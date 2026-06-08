import os
import sys
import tomli
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

CONFIG_PATH = os.path.expanduser("~/.config/apeiron_bridge/db.toml")

def ensure_db_config():
    """Generates the database config file with defaults if missing."""
    config_dir = os.path.dirname(CONFIG_PATH)
    if not os.path.exists(config_dir):
        os.makedirs(config_dir, exist_ok=True)
    
    if not os.path.exists(CONFIG_PATH):
        default_config = """[database]
url = "postgresql+psycopg://apeiron:apeiron_local@localhost:5432/apeiron_bridge"
"""
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(default_config)

def get_db_url() -> str:
    """Reads database URL from config."""
    ensure_db_config()
    try:
        with open(CONFIG_PATH, "rb") as f:
            config = tomli.load(f)
            return config["database"]["url"]
    except Exception as e:
        print(f"Error reading DB config: {e}", file=sys.stderr)
        # Fallback default
        return "postgresql+psycopg://apeiron:apeiron_local@localhost:5432/apeiron_bridge"

def get_engine():
    """Creates and returns the SQLAlchemy engine."""
    url = get_db_url()
    return create_engine(url, pool_pre_ping=True)

class DatabaseConnectionError(Exception):
    """Custom exception raised when database connectivity check fails."""
    pass

class DatabaseSecurityError(Exception):
    """Custom exception raised when database security check fails (not localhost)."""
    pass

def run_startup_checks():
    """
    Validates database connectivity and security requirements:
    1. Connection must succeed.
    2. Connection host must be localhost or 127.0.0.1.
    """
    url = get_db_url()
    
    # 1. Security check: parse URL and verify host is localhost or 127.0.0.1
    # Simple check for safety:
    import urllib.parse
    parsed = urllib.parse.urlparse(url)
    # The netloc can be 'username:password@host:port' or 'host:port'
    host_part = parsed.hostname
    if not host_part or host_part.lower() not in ("localhost", "127.0.0.1"):
         raise DatabaseSecurityError(
             f"Security Violation: Database host is configured to '{host_part}'. "
             "The application must only connect to a local PostgreSQL instance (localhost or 127.0.0.1) "
             "to ensure data privacy."
         )

    # 2. Connectivity check
    engine = get_engine()
    try:
        with engine.connect() as conn:
            # Ping
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError as e:
        raise DatabaseConnectionError(
            f"Failed to connect to the database. Ensure PostgreSQL is running on localhost:5432 "
            f"and the 'apeiron_bridge' database exists.\nDetails: {e}"
        )

_db_available: bool = False

def check_db_connection() -> bool:
    """Attempt a lightweight connection check. Returns True if reachable."""
    global _db_available
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        _db_available = True
    except Exception:
        _db_available = False
    return _db_available

def is_db_available() -> bool:
    return _db_available

