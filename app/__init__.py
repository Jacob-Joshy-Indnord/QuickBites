"""QuickBites backend application package.

This package is the root of the QuickBites food-delivery backend, a modular
monolith built on FastAPI. Each business capability lives in its own
sub-package (for example ``app.zones`` for delivery zones and serviceability)
and cross-cutting concerns such as authentication and role-based access
control live in ``app.core``. The FastAPI application object itself is built
by ``app.main.create_app``, which wires routers and dependencies together so
tests and deployments can construct isolated instances. This module defines
no functions or classes; it only marks the directory as a Python package and
documents the overall layout for readers navigating the codebase for the
first time.
"""
