#!/usr/bin/env python3
"""
Create ICAROS tables in Supabase.

Requires DATABASE_URL in .env.local, for example:
  DATABASE_URL=postgresql://postgres.ngoqpsmonhhjeyqgggzj:YOUR_PASSWORD@aws-0-us-east-1.pooler.supabase.com:6543/postgres

Find your password in Supabase Dashboard → Project Settings → Database → Connection string
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env.local"))

DATABASE_URL = os.environ.get("DATABASE_URL", "")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL is not set in .env.local")
    print()
    print("Add this line to .env.local (replace YOUR_PASSWORD):")
    print(
        "DATABASE_URL=postgresql://postgres.ngoqpsmonhhjeyqgggzj:YOUR_PASSWORD"
        "@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
    )
    sys.exit(1)

schema_path = os.path.join(os.path.dirname(__file__), "..", "supabase", "schema.sql")
with open(schema_path, "r") as f:
    schema_sql = f.read()

grants_sql = """
GRANT SELECT, INSERT, UPDATE, DELETE ON public.rovers TO anon, authenticated, service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.route_runs TO anon, authenticated, service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated, service_role;
"""

try:
    import psycopg2
except ImportError:
    print("Installing psycopg2-binary...")
    os.system(f"{sys.executable} -m pip install psycopg2-binary -q")
    import psycopg2

print("Connecting to Supabase Postgres...")
conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True
cur = conn.cursor()

print("Running schema.sql...")
cur.execute(schema_sql)

print("Applying API grants...")
cur.execute(grants_sql)

cur.execute("SELECT name FROM rovers ORDER BY name;")
rovers = cur.fetchall()
print(f"Done! Rovers in database: {[r[0] for r in rovers]}")

cur.close()
conn.close()
