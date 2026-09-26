# GalPal

An online store for skincare, makeup and beauty products in Bangladesh: a customer storefront, plus dashboards for
Customer Care (CCE) staff and administrators.

| Part | Stack | Details |
| --- | --- | --- |
| [`backend/`](backend/) | Django 5 + Django REST Framework, PostgreSQL, Redis/Celery (optional in dev), Cloudflare R2 for media | [backend/README.md](backend/README.md) |
| [`frontend/`](frontend/) | Next.js 16 (App Router, React 19), Tailwind CSS 4 | [frontend/README.md](frontend/README.md) |

The backend is an API only (`/api/v1/…`, docs at `/api/docs/`). The frontend renders every page and talks to the API
from the server, so the browser never calls the backend directly.

## What's in it

**Storefront (customers and guests)**

- Catalog: categories (nested), brands, tags, products with variants (e.g. shade / size), search and filters
- Cart, coupons, and checkout with cash on delivery. Delivery charges depend on the area (Inside Dhaka, Dhaka outer
  zones, Outside Dhaka), and guests who check out get an account created for them.
- Order tracking and the customer dashboard: orders, saved addresses, account
- Product reviews with photos. They are moderated, so only approved reviews are shown or counted in the rating.
- "Notify Me" back-in-stock requests, and a homepage with banners, product showcases, shoppable videos and customer
  reviews

**Customer Care dashboard (`/dashboard`, role `cce`)**

- Overview: inventory, sales and order charts for a chosen period
- Orders: search, filter by date and status, change status (stock is put back on cancel or return), add manual orders
- Products (with gallery, variants and stock), categories, brands, Notify Me requests, review moderation

**Admin dashboard (`/dashboard`, role `admin`)**

- Store overview with one date filter for the whole page: revenue, orders, products sold, new customers, inventory
  value, comparison with the previous period, top products, sales by category, recent orders and stock alerts
- Everything CCE has (at `/dashboard/admin/…`), plus **Users** (every role; create, edit, deactivate, reset password)
  and **Delivery Charges** (each zone's charge and the Dhaka outer areas)

Roles come from the backend (`User.role`: `admin`, `cce`, `customer`). The backend enforces every permission, and the
frontend's route guards only add a second layer.

## Quick start (local)

Requirements: Python 3.12, PostgreSQL 14+, Node.js 20.9+. Redis is optional in development.

**1. Backend** (full guide: [backend/README.md](backend/README.md))

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                 # set SECRET_KEY and DATABASE_URL

python manage.py migrate             # also seeds districts, delivery zones and delivery methods
python manage.py createsuperuser     # phone + full name + password, creates an "admin" account
python manage.py runserver           # http://localhost:8000/api/docs/
```

Optional demo data:

```bash
python manage.py seed_catalog        # categories, brands, tags and products   (--flush removes them)
python manage.py seed_reviews        # sample approved reviews                  (--flush removes them)
```

**2. Frontend** (full guide: [frontend/README.md](frontend/README.md))

```bash
cd frontend
npm install
echo "API_BASE_URL=http://localhost:8000/api/v1" > .env.local
npm run dev                          # http://localhost:3000
```

Log in with the superuser's phone number to reach the admin dashboard. Create CCE and customer accounts from
**Dashboard → Users**.

## Tests and checks

```bash
cd backend && pytest                 # uses a LOCAL test database (TEST_DATABASE_URL), never DATABASE_URL
cd frontend && npm run lint && npm run build
```

## Repository layout

```
GalPal/
├── backend/            Django API
│   ├── apps/           accounts, catalog, cart, coupons, shipping, orders, payments, reviews,
│   │                   site_settings, banners, videos, marketing, core
│   └── config/         settings (dev / prod / test), urls, celery
└── frontend/           Next.js app
    └── src/
        ├── app/        routes, including app/api/* proxies to the backend and app/dashboard/*
        ├── component/  UI, by area (homepage, shop, product, cart, checkout, dashboard, shared)
        └── lib/        data fetching, API helpers, formatting
```

## Things to know

- **Shared database.** If `backend/.env` points `DATABASE_URL` at a shared cloud Postgres (the team setup in the backend
  README), `migrate` and the seed commands change everyone's data. Run them deliberately.
- **Single sources of truth.** Delivery charges and Dhaka zones live in the backend's shipping zones, stock only changes
  through logged stock adjustments, and ratings are computed from approved reviews. Don't hardcode copies of these in
  the frontend.
- **SMS.** "Notify Me" and password-reset messages go through `SMS_BACKEND`, which drops messages until a provider is
  configured (see `apps/core/messaging.py`).
- **Secrets.** `.env` and `.env.local` are git-ignored. Never commit them.

## Contributors

- **Md. Fazlah Karim Alvee** (`Alvee3120`)
- **Nusrat Jahan** (`nusratjahan7`)

