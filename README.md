# QuickBites

QuickBites is a demo project.

## Getting started

Clone the repository:

```bash
git clone https://github.com/Jacob-Joshy-Indnord/QuickBites.git
cd QuickBites
```

## Running

```bash
pip install -e ".[test]"
psql "$DATABASE_URL" -f migrations/0001_create_zones.sql   # needs PostGIS
DATABASE_URL=postgresql+psycopg://user@host/db uvicorn app.main:create_app --factory
```

## Tests

```bash
python -m pytest                                   # in-memory repository
TEST_DATABASE_URL=postgresql+psycopg://... python -m pytest   # also runs PostGIS contract tests
```

## Structure

- `app/main.py` — FastAPI application factory
- `app/core/auth.py` — ops principal and RBAC dependencies (`require_ops_admin`)
- `app/zones/` — delivery zones: GeoJSON validation, repositories (PostGIS + in-memory), service, admin router
- `migrations/` — SQL migrations (PostGIS `zones` table)
- `tests/` — pytest suite

## Admin zone API

All routes require the ops admin role (agents get 403).

| Method | Path | Purpose |
|---|---|---|
| POST | `/admin/zones` | Create a zone (`name`, GeoJSON `boundary`) |
| GET | `/admin/zones?is_active=` | List zones |
| GET | `/admin/zones/{id}` | Get a zone |
| PATCH | `/admin/zones/{id}` | Edit name and/or boundary |
| POST | `/admin/zones/{id}/deactivate` | Deactivate (idempotent); points inside become non-serviceable |

Active zones may share edges but not area (409 on overlap or duplicate name).

## License

TBD
