"""QuickBites backend application package.

This package hosts the FastAPI service. The cart module (app/cart.py) provides
the single-outlet cart API and minimum order value check; app/main.py builds
the application; app/catalogue.py supplies menu and outlet lookups; and
app/billing.py computes the payable total used by the minimum order check.
All monetary values are integers in paise to avoid rounding drift. Other
modules (orders, payments) will be added alongside these as later stories
are built, and they are expected to reuse the same conventions and helpers.
"""
