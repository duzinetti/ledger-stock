# LedgerStock

LedgerStock is a stock management system for small local businesses (hardware stores, small wholesalers) — it tracks inventory, not sales. It is explicitly not a point-of-sale system and not a full ERP; see [PRD.md](PRD.md) §3 for the full list of goals and non-goals.

🚧 **Status: active MVP development.** Not deployed, not production-ready yet — see below for what's done and what's left.

## Status

Core application logic for the MVP is done; what remains is mostly infrastructure, not business rules.

**Done:**
- Product CRUD (soft delete on removal, movement history preserved)
- Stock movement tracking (entry/exit) with insufficient-stock validation
- Server-side validation via Django `ModelForm`s
- Login required for every read/write action
- N+1 query prevention on the product listing
- Race-safe concurrent stock movements (`select_for_update`)
- Low-stock visual alert

**Not yet done:**
- Production database (still SQLite)
- Environment-based configuration (secrets are currently hardcoded in `settings.py`)
- HTTPS / public deployment

Full backlog and current work: [GitHub Project board](https://github.com/users/duzinetti/projects/1).

## Tech Stack

- Python 3
- Django 5.x
- SQLite (development) — a production-grade relational database (PostgreSQL/MySQL) is not configured yet, see [ROADMAP.md](ROADMAP.md)

## Architecture Highlights

### Service layer (`inventory/services.py`)
Business logic — most notably stock movement registration — lives in a dedicated service layer instead of being scattered across views, the admin, and a future API. Every write path is meant to call the same function, so a business rule (like "never let stock go negative") is enforced once, not reimplemented per entry point.

### Append-only ledger for stock movements
`StockMovement` is treated as an audit ledger, not a regular editable table: the Django admin is read-only for it (add/change/delete are all disabled), and `quantity`/`type` are enforced by database-level `CheckConstraint`s — not just form validation — so no write path (admin, shell, future API) can silently corrupt the history.

### N+1 prevention
`Product.objects.with_current_quantity()` aggregates each product's current stock via `annotate()` in a single query, instead of issuing one query per product on the listing page. `select_related()` is used on product/user lookups elsewhere (movement history, admin).

### Concurrency-safe stock movements
`services.register_movement()` wraps the read-validate-write sequence in `transaction.atomic()` + `select_for_update()`, so two concurrent movements on the same product can't both pass the insufficient-stock check and push the quantity negative.

## Getting Started

```bash
git clone https://github.com/duzinetti/ledger-stock.git
cd ledger-stock

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser  # optional, for /admin access
python manage.py runserver
```

The app runs at `http://127.0.0.1:8000/`.

## Running Tests

```bash
python manage.py test
```

## Documentation

- [PRD.md](PRD.md) — problem statement, personas, MVP/V2/Later scope, open product questions
- [ROADMAP.md](ROADMAP.md) — technical roadmap, what's shipped, what's left

## Architectural Decisions

Two decisions from [PRD.md §10](PRD.md) are called out explicitly rather than glossed over:

- **Multi-tenancy** — resolved (2026-08-21): multi-tenant from the start, not deferred. A new `Company` model owns `Product.company` (the sole FK carrier; `StockMovement` reaches the company via `movement.product.company`, not a duplicated FK), a `Membership` model links `User` to `Company` without swapping `AUTH_USER_MODEL`, object-level access checks are mandatory on every lookup (not just listings), roles (Gestor/Operador) use Django's built-in `Group`, and the Django admin becomes dev/superuser-only. Implementation is sequenced after the audit-priority-0 fixes that touch the same code, as a regression safety net.
- **Soft delete vs. hard delete** — resolved (2026-08-19). Products are soft-deleted (`active=False`) rather than physically removed, so movement history is never orphaned.

## Development Process

This project was built through active pair programming with Claude Code
(Anthropic), used deliberately as a learning tool — not as a black box that
writes code unsupervised.

Every feature followed the same workflow: understand the existing codebase →
discuss the concept and trade-offs → plan the implementation → implement
incrementally → review and test. Architectural decisions — the service-layer
pattern, the append-only ledger design for stock movements, concurrency
handling via `select_for_update()` — were explained, questioned, and
validated before being committed, not accepted at face value.

Commits are transparently co-authored (`Co-Authored-By: Claude Sonnet 5`)
wherever AI assistance was involved, in line with this project's approach to
using AI deliberately to accelerate real technical understanding, not to
bypass it.

---

Eduardo Zinetti — [GitHub](https://github.com/duzinetti) · [LinkedIn](https://www.linkedin.com/in/eduardozinetti)
