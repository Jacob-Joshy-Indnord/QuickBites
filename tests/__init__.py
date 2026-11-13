"""Test package for the QuickBites backend.

This file marks ``tests`` as a package so that pytest can import shared
helpers consistently and so that test module names never collide with
application modules. The suite is organised by capability: ``test_zones_api``
exercises the admin zone CRUD endpoints end to end through FastAPI's
TestClient, ``test_zone_geometry`` covers GeoJSON validation rules in
isolation, and ``test_postgis_repository`` checks the SQL emitted for
PostGIS. Fixtures shared across modules live in ``conftest.py``. No functions
or classes are defined in this file; it exists purely as a package marker and
as a short map of the test layout for new contributors reading the suite.
"""
