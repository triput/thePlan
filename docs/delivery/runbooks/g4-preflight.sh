#!/bin/sh
# G4 household migrate preflight + 043 + 044.
# Mounted read-only into migrate container as /g4/preflight.sh.
# Expects: DATABASE_URL, HOUSEHOLD_EXPECT_DB=theplan, SEED_DEMO_USER=false, ASSIST_ENABLED=false.
# Never prints URLs or passwords. Exits non-zero on any gate failure (set -e).
set -e
python - <<'PY'
import os, sys
from urllib.parse import urlparse
from app.config import get_settings

settings = get_settings()
resolved = settings.database_url
env_url = os.environ.get("DATABASE_URL", "")

def db_name(url: str) -> str:
    u = url.replace("postgresql+psycopg://", "postgresql://").replace("postgresql+psycopg2://", "postgresql://")
    return urlparse(u).path.lstrip("/")

want = os.environ["HOUSEHOLD_EXPECT_DB"]
if want != "theplan":
    sys.stderr.write("household_expect_db_refused\n")
    sys.exit(3)
got = db_name(resolved)
if got != want:
    sys.stderr.write("settings_db_mismatch\n")
    sys.exit(3)
if db_name(env_url) != want:
    sys.stderr.write("env_db_mismatch\n")
    sys.exit(3)

from sqlalchemy import create_engine, text
e = create_engine(resolved)
with e.connect() as c:
    db = c.execute(text("select current_database()")).scalar()
    ver = c.execute(text("select version_num from alembic_version")).scalar()
if db != want:
    sys.stderr.write("preflight_db_mismatch\n")
    sys.exit(3)
if ver != "042_task_occurrence_dispositions":
    sys.stderr.write("preflight_alembic_mismatch\n")
    sys.exit(4)
print("preflight_ok_via_get_settings", db, ver)
PY
test -f /app/alembic/env.py
test -f /app/alembic/versions/043_recovery_epoch.py
test -f /app/alembic/versions/044_agent_cli_access.py
alembic upgrade 043_recovery_epoch
alembic upgrade 044_agent_cli_access
python - <<'PY'
import os, sys
from app.config import get_settings
from sqlalchemy import create_engine, text
resolved = get_settings().database_url
e = create_engine(resolved)
with e.connect() as c:
    ver = c.execute(text("select version_num from alembic_version")).scalar()
    db = c.execute(text("select current_database()")).scalar()
want = os.environ["HOUSEHOLD_EXPECT_DB"]
if db != want or ver != "044_agent_cli_access":
    sys.stderr.write("postcheck_mismatch\n")
    sys.exit(5)
print("postcheck_ok_via_get_settings", db, ver)
PY
