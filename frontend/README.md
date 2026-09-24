# GalPal — Frontend

The storefront and staff dashboard for GalPal, a skincare and makeup shop. Built with **Next.js 16** (App Router,
React 19, React Compiler) and **Tailwind CSS 4**. All data comes from the Django REST backend in `../backend`.

> This Next.js version has breaking changes from older releases. Before changing framework-level code, check the
> bundled docs in `node_modules/next/dist/docs/` (see `AGENTS.md`).

## Getting started

Requirements: Node.js 20.9+ and a running backend (see `../backend/README.md`).

```bash
npm install
# point the frontend at the backend (see "Environment" below)
echo "API_BASE_URL=http://localhost:8000/api/v1" > .env.local
npm run dev
```

Open <http://localhost:3000>.

| Script          | What it does                    |
| --------------- | ------------------------------- |
| `npm run dev`   | Development server              |
| `npm run build` | Production build                |
| `npm run start` | Serve the production build      |
| `npm run lint`  | ESLint                          |

## Environment

| Variable       | Required | Description                                                                                     |
| -------------- | -------- | ----------------------------------------------------------------------------------------------- |
| `API_BASE_URL` | yes      | Backend API base URL including the version prefix, no trailing slash, e.g. `http://localhost:8000/api/v1`. Server-side only; the browser never sees it. |

`.env` and `.env.local` are git-ignored — never commit them.

## How it talks to the backend

- **Server Components** fetch the public API directly (`src/lib/shopData.js`, `src/lib/reviewsData.js`,
  `src/lib/siteSettings.js`) with Next.js caching (`next: { revalidate }`).
- **The browser never calls the backend.** Client components call same-origin route handlers in `src/app/api/*`,
  which forward to the backend with the user's session via `backendFetch` (`src/lib/backendAuth.js`).
- **Auth** lives in httpOnly cookies (`access_token`, `refresh_token`) set by the login/register server actions
  (`src/app/actions/auth.js`). `backendFetch` renews an expired access token automatically.
- The backend is the authority for permissions, prices, stock, shipping and validation. The frontend only shows what
  it returns and surfaces its error messages.

### API route handlers (`src/app/api`)

| Route                           | Backend                                     | Used by                                   |
| ------------------------------- | ------------------------------------------- | ----------------------------------------- |
| `/api/session`                  | current user                                | navbar / auth state                       |
| `/api/cart/*`                   | `/cart/…`                                   | cart drawer, cart page, checkout          |
| `/api/orders`, `/api/orders/*`  | checkout, customer orders, cancel           | checkout, customer dashboard              |
| `/api/account/*`                | profile, addresses, change password         | account pages                             |
| `/api/products`, `/api/products/[slug]` | public catalog                      | search, product picker                    |
| `/api/reviews`                  | `/reviews/` (list + customer submission)    | product page reviews                      |
| `/api/stock-notifications`      | `/stock-notifications/` ("Notify Me")       | product card / product page               |
| `/api/admin/orders/*`           | `/admin/orders/…` (staff order module)      | CCE order management, Add Order           |
| `/api/admin/catalog/*`          | `/admin/products`, `categories`, `brands`, `tags`, `attribute-values`, `stock/adjust`, `stock-notifications`… | CCE product / category / brand / Notify Me pages |
| `/api/admin/reviews/*`          | `/admin/reviews/…` (moderation)             | CCE review management                     |

Each admin proxy forwards only the endpoints its pages use (an allow-list in the route file). The backend's role
permissions (`apps/accounts/permissions.py`) remain the real access control.

## Project structure

```
src/
  app/                      routes (App Router)
    page.js                 homepage
    shop/  products/[slug]/ catalog + product detail
    cart/  checkout/  order-confirmation/
    login/  register/
    dashboard/              signed-in area (layout requires a session)
      customer/             orders, addresses, account          (role: customer)
      CCE/                  staff tools                          (role: cce)
    api/                    same-origin proxies to the backend (see above)
    actions/auth.js         login / register / logout server actions
    globals.css             design tokens + component styles
  component/
    homepage/ shop/ product/ cart/ checkout/ auth/ shared/
    dashboard/              dashboard UI (orders, products/, categories/, brands/, reviews/)
  lib/                      data fetching, API helpers, formatting, constants
```

## Roles and dashboard

`/dashboard` is protected in `src/app/dashboard/layout.js`; each role branch has its own layout guard, and the
sidebar comes from `src/lib/dashboardNav.js`.

**Customer** — My Orders, Addresses, My Account.

**Customer Care (CCE)** — `/dashboard/CCE/…`:

| Page                 | What it does                                                                                     |
| -------------------- | ------------------------------------------------------------------------------------------------ |
| Dashboard            | Order management: search, date and status filters, change status                               |
| Add Order            | Manual orders (phone, WhatsApp…) with live delivery charge                                     |
| Products             | List / search, add, edit, delete; images, gallery, variants (Shade/Size), tags, categories, stock |
| Categories           | Nested categories with image, parent, active flag                                               |
| Brands               | Brands with logo and active flag                                                                |
| Notify Me            | Back-in-stock requests; mark Waiting / Notified                                                 |
| Reviews              | Moderate customer reviews: approve, reject, delete, view details                                |
| My Orders / Account  | The CCE's own orders and profile                                                                |

Stock is never written directly: the product form sets quantities through `stock/adjust`, so every change is logged.

## Styling

- Tailwind CSS 4 utilities plus component classes in `src/app/globals.css`.
- **Colors are design tokens** (`--color-*` on `:root` in `globals.css`), including the order and review status
  palette (`--color-status-*`). Use the tokens rather than hard-coded colors in components.
- Fonts: Honacu (`public/font/honacu.ttf`, `.custom-font`) for headings, Montserrat for body text.
- Shared UI to reuse: `Modal`, `ConfirmDialog`, `SelectField`, `ProductImage`, `SectionHeader`,
  `DashboardPagination`, and the image inputs in `component/dashboard/products/ImageInputs.jsx`.
- Note: `.checkout-input` sets `width: 100%`, which overrides Tailwind `w-*` classes on the same element. To place two
  inputs side by side, size them with a grid (`grid-cols-[minmax(0,1fr)_…]`), not width classes.
- Toasts: always `notify.success(...)` / `notify.error(...)` from `src/lib/notify.js` (Sonner, styled in `globals.css`).
- Icons: `react-icons`. Marquees: `react-fast-marquee`.

## Caching and freshness

- Catalog reads revalidate on a timer (`revalidate` in the fetch calls).
- Review and product-rating reads carry the `reviews` cache tag (`REVIEWS_TAG` in `src/lib/reviewsData.js`). The
  review routes call `revalidateTag` after a submission or a CCE approve / reject / delete, so product pages and the
  homepage testimonials pick up changes on their next render.
- Data changed outside the app (Django admin, management commands) appears once the timer runs out, or after
  restarting the dev server.

## Homepage review section

"Loved by Our Customers" (`component/homepage/CustomerReviews.jsx` + `ReviewMarquee.jsx`) shows the newest
**approved** reviews in two rows moving in opposite directions. It is hidden when there are no approved reviews.
For demo content, seed sample reviews from the backend:

```bash
cd ../backend
python manage.py seed_reviews          # add sample approved reviews
python manage.py seed_reviews --flush  # remove them
```

## Favicon

`src/app/icon.svg` (a copy of `public/assets/galpal/favicon.svg`) is picked up by Next.js's `icon` file convention.
