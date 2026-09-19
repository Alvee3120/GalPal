# GalPal API

Django + Django REST Framework backend for the GalPal cosmetics & skincare store.
API only: the storefront and the admin panel are separate Next.js apps that consume it.

- Storefront API: `/api/v1/...`
- Admin / CCE API: `/api/v1/admin/...`
- Swagger UI: `/api/docs/` · ReDoc: `/api/redoc/` · OpenAPI schema: `/api/schema/`
- Health check: `/api/v1/health/`
- Django admin (fallback only): `/django-admin/`

## Requirements

- Python 3.12
- PostgreSQL 14+ (developed on 16)
- Redis (only from the modules that need it: Celery, caching)

## Setup (local)

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env            # then edit DATABASE_URL / SECRET_KEY

createdb galpal                 # or create the role + database your DATABASE_URL points to
python manage.py migrate
python manage.py runserver
```

Open http://localhost:8000/api/docs/ and http://localhost:8000/api/v1/health/.

`DATABASE_URL` examples:

```
postgres://galpal:galpal@localhost:5432/galpal     # TCP with user/password
postgres:///galpal                                  # local Unix socket, current OS user
```

## Setup (Docker)

```bash
cd backend
docker compose up --build
```

Starts Django (dev settings, auto-migrate), PostgreSQL 16 and Redis 7.

## Tests

```bash
pytest                    # whole suite
pytest apps/core          # one app
pytest -k health -v
```

pytest-django creates and destroys its own `test_<dbname>` database, so your dev data
is never touched. The DB user needs the `CREATEDB` privilege.

## Settings

| Module | Use |
|---|---|
| `config.settings.base` | Shared. Everything is read from environment variables / `.env`. |
| `config.settings.dev` | Local dev. Default for `manage.py`. Insecure fallback `SECRET_KEY`, CORS for `localhost:3000`. |
| `config.settings.prod` | Default for `wsgi.py` / `asgi.py`. Refuses to boot without `SECRET_KEY` and `ALLOWED_HOSTS`. HTTPS, HSTS, secure cookies, WhiteNoise static. |
| `config.settings.test` | Used by pytest. Fast password hasher, temp media dir. |

Set the module with `DJANGO_SETTINGS_MODULE`. See `.env.example` for every variable.

Media uploads go to `media/` locally; set `USE_S3=True` (+ `AWS_*`) for S3-compatible storage.

## Project layout

```
backend/
├── config/            settings/{base,dev,prod,test}.py, urls.py, wsgi.py, asgi.py
├── apps/
│   └── core/          shared foundation (no business logic)
│       ├── models.py        TimeStampedModel, SoftDeleteModel
│       ├── pagination.py    StandardPagination (default 20, max 100)
│       ├── exceptions.py    API error envelope
│       ├── validators.py    image upload validation (jpg/png/webp + size)
│       ├── utils.py         UploadPath, unique_slugify
│       └── views.py         health check, JSON 400/403/404/500 handlers
├── pytest.ini · conftest.py
├── requirements.txt · requirements-dev.txt
└── Dockerfile · docker-compose.yml · .env.example
```

Each future app follows `apps/<name>/{models,serializers,views,urls,permissions,filters,services}.py`
plus `tests/`. Business logic lives in `services.py`, never in views or serializers.

## Conventions

**Errors** always use one envelope (see `apps/core/exceptions.py`):

```json
{"error": {"status": 400, "code": "validation_error", "message": "Validation failed.",
           "details": {"phone": ["This field is required."]}}}
```

**Lists** are paginated: `{"count", "next", "previous", "results"}`; `?page=2&page_size=50` (max 100).

**Permissions** are secure by default: DRF's default is `IsAuthenticated`, so a public
endpoint must declare `permission_classes = [AllowAny]` explicitly.

**Money** is `DecimalField(max_digits=12, decimal_places=2)`, never float. Default currency BDT.

**Soft delete**: `SoftDeleteModel.objects` hides deleted rows, `.all_objects` shows everything.

**Slugs**: generate with `apps.core.utils.unique_slugify` (handles `-2`, `-3` collisions and Bangla text).

**Images**: attach `validate_image_file` and `upload_to=UploadPath("products")` to image fields.
