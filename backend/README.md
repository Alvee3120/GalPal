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

# PostgreSQL: a dedicated role + database matching DATABASE_URL in .env
psql -d postgres -c "CREATE ROLE galpal LOGIN PASSWORD 'galpal' CREATEDB;"
createdb -O galpal galpal

python manage.py migrate
python manage.py createsuperuser        # asks for phone, full name, password -> role "admin"
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

## Redis (optional in dev, required in production)

Set `REDIS_URL=redis://localhost:6379/0` in `.env` to use Redis for the cache (and, from Module 13/16, Celery).
Leave it empty to use the in-memory cache.

```bash
brew install redis && brew services start redis     # macOS with a native (Apple Silicon or Intel) Homebrew
# or, without Homebrew, via conda:
conda create -y -n galpal-redis -c conda-forge redis-server
~/anaconda3/envs/galpal-redis/bin/redis-server --bind 127.0.0.1 --daemonize yes   # stop: redis-cli shutdown nosave
# or: docker compose up   (starts Redis for you)
redis-cli ping    # PONG
```

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
│       ├── validators.py    image upload validation, Bangladesh phone normalisation
│       ├── utils.py         UploadPath, unique_slugify
│       ├── messaging.py     pluggable SMS backend (email uses Django's EMAIL_BACKEND)
│       └── views.py         health check, JSON 400/403/404/500 handlers
│   ├── accounts/      users, auth (JWT), RBAC permissions, address book, staff/customer admin API
│   ├── site_settings/ global site settings singleton (branding, contact, tracking, commerce, SEO)
│   └── catalog/       categories (tree), brands, tags (Module 4 adds products here)
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

## Authentication & roles (Module 1)

- Login with **phone or email + password**: `POST /api/v1/auth/login/` with `{"identifier", "password"}`.
  Phones are accepted as `01712345678`, `+8801712345678` or `8801712345678` and stored as `01712345678`.
- Send `Authorization: Bearer <access>`. Access tokens last 15 min, refresh tokens 7 days (`JWT_*` env vars);
  refresh tokens rotate and the old one is blacklisted. Logout blacklists the refresh token.
- Roles: `admin`, `cce`, `customer` (+ anonymous guest). The whole matrix lives in
  `apps/accounts/permissions.py`. CCE may only use `/api/v1/admin/orders/**`; everything else under
  `/api/v1/admin/` is Admin-only. `apps/accounts/tests/test_permissions.py` sweeps **every** admin route
  and fails if a CCE gets anything but 403 outside the order module, so new modules are covered automatically.
- Users created by `createsuperuser` get the `admin` role.
- Password reset sends a 6-digit code (SMS for a phone identifier, email for an email identifier). In dev the
  message is **printed in the `runserver` console**. In production configure `EMAIL_*` and an `SMS_BACKEND`.
- `apps.accounts.services.create_customer_account(...)` creates accounts with a generated password; used by
  checkout in Module 10. The plain password is returned once and never stored, logged or exposed by the API.

## Site settings (Module 2)

- One row (`id=1`, enforced by a DB constraint), created by a migration. Read it from code with
  `apps.site_settings.services.get_site_settings()` (cached); never query the model in request paths.
- `GET /api/v1/site-settings/` is public and returns an **allow-listed** subset. Secrets (Meta CAPI token,
  GA4 API secret) and internal flags can never appear there; a test fails if a new field isn't classified.
- `GET/PATCH /api/v1/admin/site-settings/` is Admin-only. Secrets come back masked (`••••••••1234`); send a new
  value to replace, the masked value back to keep, `""` to clear.
- Caching: `REDIS_URL` enables Redis (**required in production with multiple workers**). Without it a per-process
  cache is used with a short TTL (30s) since other workers can't be invalidated. A cache outage falls back to the DB.

## Catalog: categories, brands, tags (Module 3)

- **Categories** nest without a depth limit. A category is public only if it *and every ancestor* is active.
  `GET /categories/tree/` returns the whole visible tree as a plain nested array (no pagination);
  `GET /categories/` is the flat, filterable, paginated list; `GET /categories/{slug}/` adds SEO fields,
  breadcrumb and visible children.
- **Slugs** (shared by categories, brands, tags; reuse for products/pages via `SlugModel` +
  `SlugSerializerMixin`): auto-generated from the name (`-2`, `-3` on collision), editable by an admin.
  Renaming regenerates only slugs the admin never set by hand; sending `slug: ""` switches back to automatic.
  A hand-typed slug that is already taken is a 400, never silently changed.
- **Circular parents** are rejected on create/update (400 on `parent`) and rechecked under a table lock at save time.
- **Deleting a category** is blocked with a 409 if it has products (`category_has_products`) or sub-categories
  (`category_has_children`). `DELETE ...?move_children_to=root|<id>` re-parents the sub-categories first.
  Module 4: `Product.categories` must use `related_name="products"` so the product check works.
