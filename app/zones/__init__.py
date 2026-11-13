"""Zones and Serviceability capability package.

This package owns delivery-zone polygons and answers the question "is this
point serviceable, and by which zone?". Its modules are: ``geometry`` (GeoJSON
to Shapely conversion, validation and overlap rules), ``models`` (the ``Zone``
domain record), ``errors`` (``ZoneNotFoundError`` and ``ZoneConflictError``),
``repository`` (the ``ZoneRepository`` protocol plus ``InMemoryZoneRepository``),
``postgis_repository`` (the production ``PostgisZoneRepository``), ``service``
(``ZoneService`` orchestrating create, edit, deactivate and point resolution),
``schemas`` (Pydantic request/response models) and ``router`` (the admin REST
endpoints under ``/admin/zones``). Only active zones ever participate in
serviceability, so deactivating a zone immediately makes it non-serviceable.
"""
