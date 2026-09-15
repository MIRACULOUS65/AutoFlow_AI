# Migrations

Alembic migrations for the production (PostgreSQL) path.

The dev default (SQLite) creates tables directly via `create_all` on startup, so
migrations are not required for local demos. For PostgreSQL:

```bash
# generate a migration after model changes
alembic revision --autogenerate -m "describe change"

# apply
alembic upgrade head
```

`migrations/env.py` reads the sync form of `DATABASE_URL` from settings.
