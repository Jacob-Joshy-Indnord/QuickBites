"""QuickBites backend application package.

Hosts the FastAPI service. app/addresses.py provides the customer saved
address book (create, list, update, delete, set-default) and app/main.py
builds the FastAPI application via create_app. All endpoints identify the
caller with the X-Customer-Id header until the token session work lands.
Storage is currently in-memory behind a repository class so a PostgreSQL and
PostGIS implementation can replace it without touching the API layer. Other
domains such as cart, orders and payments will be added as sibling modules and
should follow the same conventions for validation, errors and testing.
"""
