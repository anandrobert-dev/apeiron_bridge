import os
import sys
from alembic.config import Config
from alembic import command
from app.rate_analysis_comparison.db.engine import run_startup_checks, ensure_db_config
from app.rate_analysis_comparison.db.seed import seed_db

def run_db_setup():
    """
    Main database deployment runner.
    1. Ensures db.toml is present.
    2. Runs startup checks (connectivity and localhost security).
    3. Runs Alembic schema migrations to HEAD.
    4. Seeds the tables with required reference data.
    """
    print("🚀 Initializing Apeiron Bridge database...")
    try:
        # 1. Prepare db.toml
        ensure_db_config()
        
        # 2. Run connectivity & security checks
        run_startup_checks()
        print("  - Connection and safety checks passed.")
        
        # 3. Execute Alembic Migrations to HEAD programmatically
        # Locating alembic.ini relative to this file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        alembic_ini_path = os.path.join(current_dir, "alembic.ini")
        
        if not os.path.exists(alembic_ini_path):
             raise FileNotFoundError(f"Alembic configuration not found at {alembic_ini_path}")
             
        print("  - Applying database migrations...")
        alembic_cfg = Config(alembic_ini_path)
        command.upgrade(alembic_cfg, "head")
        print("  - Database migrations applied successfully.")
        
        # 4. Seed the tables
        seed_db()
        
        print("🎉 Database setup completed successfully!")
        return True
    except Exception as e:
        print(f"❌ Error during database setup: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_db_setup()
    sys.exit(0 if success else 1)
