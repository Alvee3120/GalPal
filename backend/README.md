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
│   ├── catalog/       categories (tree), brands, tags, products, variants, inventory
│   ├── banners/       hero slider: slider-wide config singleton + banner CRUD/reorder
│   ├── videos/        video cards: upload or external link, linked shoppable products
│   ├── cart/          storefront cart: guest (header token) and logged-in customer
│   └── coupons/       discount codes: rules, cart application, row-locked redemption
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

## Products, variants & inventory (Module 4)

- **Product**: required feature image, optional gallery (`images/`), categories (one marked
  primary), brand, tags, price + optional sale window, cosmetics fields (skin type, ingredients,
  size, expiry...), SEO. Soft-deleted on `DELETE` (`Product.objects` hides it, `.all_objects` sees it).
- **Variants**: `ProductAttribute`/`AttributeValue` are reusable across products (e.g. Shade, Size).
  A `ProductVariant` picks a combination of values; the database rejects two variants of the same
  product sharing a combination. A variant without its own price/stock falls back to the product's.
- **Stock** is never edited directly: `POST /admin/stock/adjust/` (single) or
  `POST /admin/products/bulk/stock/` (batch, all-or-nothing) go through `services.adjust_stock`,
  which locks the row, refuses to go negative, and writes an immutable `StockMovement`
  (`GET /admin/stock-movements/`, filterable).
- **Public catalog**: `GET /products/` (filters: `category` [includes sub-categories], `brand`,
  `tag`, `skin_type`, `gender`, `price_min`/`price_max`, `in_stock`, `on_sale`,
  `is_featured`/`is_new_arrival`/`is_bestseller`; `ordering=price|newest|popularity|rating`;
  `search=`) and `GET /products/{slug}/` (gallery, active variants, breadcrumb, related products).
  Only `status=published` products are public.
- **Admin**: `/admin/products/` CRUD, `.../duplicate/` (deep copy as a draft with independent image
  files and a fresh SKU), `.../bulk/activate|deactivate/`, nested `.../images/` and `.../variants/`.
- **A DRF gotcha, fixed project-wide**: `BooleanField` on a multipart request treats an absent key
  as unchecked (`False`), silently overriding a model's `default=True`. Patched once in
  `apps/core/apps.py` (`CoreConfig.ready`) for every `ModelSerializer`, present and future.

## Hero banners (Module 5)

- `GET /api/v1/hero-banners/` is public and returns `{"config": {...}, "banners": [...]}` in one
  call: the slider-wide config (`slide_delay_seconds`, `autoplay`, `loop`, cached like Module 2's
  site settings) plus active, in-schedule banners in display order. A banner's `slide_delay_override`
  wins over the config's default when the frontend renders that slide.
- A banner needs only `desktop_image`; `tablet_image`/`mobile_image` are optional and fall back to
  the desktop image in the public response (both raw and admin views expose the actual stored value).
- Visible = `is_active` and within `[start_at, end_at]` (either may be blank). The database itself
  rejects `end_at <= start_at`.
- Admin: `/admin/hero-slider-config/` (singleton, GET/PATCH) and `/admin/hero-banners/` (CRUD +
  `POST .../reorder/` with the full ordered list of ids).

## Video cards (Module 6)

- A `VideoCard` needs exactly one of `video_file` (mp4/webm, validated by extension, size and a
  magic-byte header check) or `external_url` (e.g. a YouTube link) — enforced in the serializer
  (friendly 400) and by a DB `CheckConstraint` (belt-and-braces against a direct ORM write).
- `GET /api/v1/videos/` (public, list only) returns active cards with `video_url` (always an
  absolute URL, whichever source it came from) and their linked products as shoppable cards
  (`id, name, slug, image, price`) — draft/archived products are filtered out automatically.
- Admin picks which products to link via `GET /api/v1/admin/products/picker/` — a small,
  searchable `{id, name, sku, feature_image}` list (published only, capped at 20), reusable by any
  future admin screen that needs a product search box.
- Admin CRUD at `/admin/videos/`. Deleting a video removes its file(s) from storage; it never
  touches the products it was linked to.

## Cart (Module 7 — no wishlist, by request)

- **Guests** identify their cart with an `X-Cart-Token` header, not a cookie: the first
  `POST /api/v1/cart/items/` a guest makes creates the cart and returns the token both in the
  response body (`cart_token`) and in the same response header — store it and resend it on every
  later cart request. **Logged-in customers** need no token; their JWT identifies their cart.
  A stale/expired/garbage bearer token never blocks a guest from using the cart (see
  `apps.core.authentication.OptionalJWTAuthentication`).
- Nothing is stored twice: `unit_price` and `is_available` are computed **live** from the
  product/variant's current price and stock on every read, never snapshotted, so a price or stock
  change is reflected immediately. An unavailable line (discontinued, out of stock, deactivated)
  stays in the response so the frontend can show it, but never counts toward the totals.
- **On login or registration**, a guest's cart is folded into the account's own cart automatically
  (quantities combined, capped at whatever stock still allows) and the guest cart is deleted. A
  merge problem never blocks login — see `apps.accounts.views._merge_guest_cart`.
- `discount` is always `"0.00"` until Module 8 (coupons); `shipping` is a placeholder shape
  (`{"amount": null, "note": "Calculated at checkout"}`); Module 9 added the calculator
  (`POST /shipping/calculate/`) but the cart response keeps this shape — both field names are stable.
- Endpoints: `GET /cart/`, `POST /cart/items/` (add — increases an existing line, doesn't replace
  it), `PATCH /cart/items/{id}/` (set an absolute quantity), `DELETE /cart/items/{id}/`.

## Coupons (Module 8)

- **Rules**: flat or percentage (optional currency cap), minimum order, start/expiry window, total
  and per-customer usage limits, restrict to products/categories/brands (a **union**; a chosen
  category covers its sub-categories), exclude sale items, free shipping. Codes are stored
  upper-case and matched case-insensitively.
- **Customer flow**: `POST /api/v1/cart/coupon/ {"code"}` validates against the cart's *current*
  contents and attaches it; `DELETE` detaches. The discount is recomputed live on every cart read,
  so a coupon that stops working (cart dips below the minimum, admin deactivates it) reports
  `discount: "0.00"` and `coupon.is_valid: false` with the reason, and **resumes on its own** if the
  cart changes back. A guest's coupon is carried over when they log in.
- **Minimum order** is checked against the whole cart, not just the discountable lines.
- **Redemption** is a separate step: `services.redeem_coupon(coupon, phone=, order_reference=,
  discount_amount=, user=)` is what Module 10's checkout must call once, when an order is placed.
  It re-checks everything against the live row under `SELECT ... FOR UPDATE`, so concurrent orders
  cannot exceed a usage limit (tested with real concurrent DB connections).
- **Not yet enforceable** (need Orders, Module 10): `first_order_only`, and per-*phone* limits for a
  guest at cart time (a cart has no phone until checkout). Both are stored/configurable now.
- Admin: `/admin/coupons/` CRUD (a coupon that has been used can't be deleted, only deactivated)
  and `/admin/coupon-usages/` (filter `?coupon=<id>`).

## Shipping & delivery (Module 9)

- **Zones**: each `DeliveryZone` has a `charge` (Admin-editable, `0`–`SHIPPING_MAX_CHARGE`, default
  ৳5000, a typo guard), a delivery estimate (`estimated_days_min/max` or a text label), an optional
  **free-shipping threshold override** (blank = use the global one from Site Settings, `0` = never
  free), `is_active`, `sort_order` and `is_default`. Seeded (data migration, and re-runnable with
  `python manage.py seed_shipping`): **Inside Dhaka ৳70** (the Dhaka district) and **Outside Dhaka ৳120**
  (the default: every district nobody else covers), plus the 64 districts and the Standard/Express
  methods. Re-running never overwrites an edited charge; `seed_shipping --reset-charges` restores
  ৳70/৳120 on purpose (and logs it).
- **Matching**: a zone covers districts wholly (`areas: []`) or only listed areas/thanas of one, which is
  how Dhaka is split into city and outer Dhaka without a new model. Area rule beats whole-district
  beats default; matching ignores case, punctuation and "District", and knows common spellings
  (Chittagong/Chattogram, Comilla/Cumilla...). An unknown district gets the default zone.
- **Calculation** (`services.calculate_shipping(address, cart_subtotal, coupon, delivery_method=)`),
  always on the server: zone charge (+ method extra) → free if the subtotal **reaches** the zone/global
  threshold → free if the cart's coupon grants free shipping. Free means the whole charge is `0`,
  method extra included. The subtotal is the pre-discount item total.
- **Storefront**: `GET /shipping/zones/`, `/shipping/methods/`, `/shipping/districts/` (short lists,
  unpaginated) and `POST /shipping/calculate/ {district, area?, subtotal?, delivery_method?}`; leave
  `subtotal` out to use the caller's cart, whose valid coupon is then considered. The cart's own
  `shipping` field is still the placeholder; checkout is where the real charge is stored.
- **Admin only** (CCE gets 403): `/admin/shipping/zones/` CRUD, `PATCH .../{id}/charge/` (the quick
  "change delivery fee" edit), `GET .../{id}/history/`, and `/admin/shipping/methods/` CRUD. The default
  zone can't be deleted, deactivated or un-defaulted (make another zone the default; the swap is
  atomic), and a zone or method that orders used can't be deleted, only deactivated.
- **History**: every charge change (and a zone's starting charge) is a `ShippingChargeHistory` row
  with who/old/new/when; it outlives a deleted zone. Module 18's audit log can read it.
- **Caching**: the active zones/districts/methods are cached (Redis) and dropped by signals on any
  save/delete, including Django-admin and shell edits, so a new charge applies to the very next
  calculation. A cache outage falls back to the database.
- **For Module 10 (Orders)**: call `calculate_shipping` at checkout and store the result as the order's
  snapshot (`shipping_zone` FK **SET_NULL** with `related_name="orders"`, `shipping_zone_name`,
  `shipping_charge`); the "has orders" delete guard finds the orders through that `related_name`. Ignore
  any shipping charge the client sends. A delivery-method FK needs `related_name="orders"` too.

## Shared cloud setup (team development)

So everyone works against the same data and images instead of re-seeding locally. **Cloudflare has
no hosted PostgreSQL** (its D1 is SQLite-based, and Hyperdrive only accelerates a Postgres you
already run elsewhere), so the database and the file storage come from two different places:

| Need | Use | Why |
|---|---|---|
| Shared Postgres | **Neon** (free tier), Supabase, Railway, Render... any Postgres | Django only needs a `DATABASE_URL` |
| Shared images/videos | **Cloudflare R2** | S3-compatible, free tier, no egress fees |

**Do both together.** Database rows store a file *path*; if the database is shared but each person
keeps files on their own disk, everyone else sees broken images.

### 1. Shared Postgres (example: Neon)

1. One person creates a project at neon.tech, then copies the **direct** connection string (not the
   `-pooler` one: Django keeps its own connections) and adds `?sslmode=require`.
2. Every developer puts it in their own `backend/.env` (never commit it):
   `DATABASE_URL=postgres://USER:PASSWORD@ep-xxxx.REGION.aws.neon.tech/DBNAME?sslmode=require`
3. **One person, once:** `python manage.py migrate`, `python manage.py createsuperuser`,
   `python manage.py seed_catalog`.
4. Free-tier databases sleep when idle, so the first request after a pause is slow; connections are
   health-checked so it doesn't error (`CONN_HEALTH_CHECKS`).

Rules that keep a shared database from biting you:
- **Migrations:** the database has one schema. Whoever adds a migration applies it, and everyone else
  pulls before running. Don't run `migrate` from a branch that's behind, or one that has migrations
  the others don't.
- **Never** `dropdb`, `migrate <app> zero`, or `seed_catalog --flush` against the shared database
  without telling the team.
- `pytest` **never** uses the shared database or bucket, whatever `.env` says: it uses a local
  Postgres (`TEST_DATABASE_URL`, default `postgres://galpal:galpal@localhost:5432/galpal`) and temp files.

### 2. Cloudflare R2

1. Cloudflare dashboard, then **R2 Object Storage**. Enable it (Cloudflare may ask for a payment
   method; the free tier is 10 GB).
2. **Create bucket**, e.g. `galpal-media`.
3. Bucket, then **Settings**, then **Public access**: enable the **r2.dev subdomain**. Copy the host,
   e.g. `pub-1a2b3c.r2.dev` (fine for development; use a custom domain in production).
4. R2 overview, then **Manage API Tokens**, then **Create API token**: permission **Object Read & Write**,
   scoped to just this bucket. Copy the *Access Key ID*, *Secret Access Key*, and your *Account ID*.
5. Every developer adds to `backend/.env`:
   ```
   USE_S3=True
   AWS_ACCESS_KEY_ID=...
   AWS_SECRET_ACCESS_KEY=...
   AWS_STORAGE_BUCKET_NAME=galpal-media
   AWS_S3_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
   AWS_S3_CUSTOM_DOMAIN=pub-1a2b3c.r2.dev
   ```
   The app refuses to start if the R2 endpoint is set without `AWS_S3_CUSTOM_DOMAIN`.
6. Upload something via the admin API and open the returned image URL in a browser.

**Sharing the secrets:** send `.env` values through a password manager or a private message, never
through git, an issue, or a public chat. Give the token only Object Read & Write on this one bucket.

### Moving your existing local data
Simplest is a fresh start on the shared setup (step 3 above with R2 on): local rows point at files
on your disk, which the team can't see. Your local `media/` folder and local database are unaffected.
