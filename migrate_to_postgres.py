"""
One-time migration script: clears PostgreSQL and re-copies all data from SQLite.
Set DATABASE_URL in .env before running.

Usage:
    venv\\Scripts\\python migrate_to_postgres.py
"""
import os
from dotenv import load_dotenv
from sqlmodel import SQLModel, create_engine, Session, select, text
from app.models import Team, Question, Admin, Feedback

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit("ERROR: DATABASE_URL is not set in .env")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Source: local SQLite
sqlite_engine = create_engine("sqlite:///puzzlemania.db", connect_args={"check_same_thread": False})

# Destination: PostgreSQL
pg_engine = create_engine(DATABASE_URL)
SQLModel.metadata.create_all(pg_engine)

# --- Step 1: Clear all PostgreSQL tables ---
print("Clearing existing PostgreSQL data...")
with pg_engine.connect() as conn:
    conn.execute(text("DELETE FROM feedback"))
    conn.execute(text("DELETE FROM team"))
    conn.execute(text("DELETE FROM question"))
    conn.execute(text("DELETE FROM admin"))
    conn.commit()
print("  ✅ All tables cleared.\n")

# --- Step 2: Migrate per model ---
def migrate_model(model_cls):
    with Session(sqlite_engine) as src, Session(pg_engine) as dst:
        items = src.exec(select(model_cls)).all()
        count = 0
        for item in items:
            dst.add(model_cls.model_validate(item))
            count += 1
        dst.commit()
        print(f"  ✅ {model_cls.__name__}: migrated {count} row(s)")

print("Migrating data: SQLite → PostgreSQL...")
migrate_model(Admin)
migrate_model(Question)
migrate_model(Team)
migrate_model(Feedback)
print("\nMigration complete! 🎉")
