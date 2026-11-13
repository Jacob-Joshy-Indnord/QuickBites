"""GeoJSON parsing, validation and spatial rules for zone polygons.

Zone boundaries arrive as GeoJSON Polygon or MultiPolygon objects in
[longitude, latitude] order (WGS 84). This module turns them into Shapely
geometry and enforces the rules PostGIS will also enforce. Functions:
``to_multipolygon`` validates structure (closed rings with at least four
positions, coordinates within longitude/latitude bounds), topology (no
self-intersection, non-zero area) and always returns a MultiPolygon, raising
``ValueError`` with a readable message otherwise; ``to_geojson`` converts a
MultiPolygon back to a JSON-serialisable GeoJSON dict; ``interiors_overlap``
implements the zone no-overlap rule — shared edges are allowed, shared area
is not; and ``covers_point`` tests whether a zone covers a point, edges included.
"""

from shapely.geometry import MultiPolygon, Point, Polygon, mapping, shape
from shapely.validation import explain_validity


def _check_ring(ring: list) -> None:
    if len(ring) < 4:
        raise ValueError("each linear ring needs at least 4 positions")
    if list(ring[0]) != list(ring[-1]):
        raise ValueError("each linear ring must be closed (first position == last)")
    for position in ring:
        if len(position) not in (2, 3):
            raise ValueError("positions must be [lng, lat] or [lng, lat, alt]")
        lng, lat = position[0], position[1]
        if not (-180 <= lng <= 180) or not (-90 <= lat <= 90):
            raise ValueError(f"position {list(position)} is outside lng/lat bounds")


def to_multipolygon(geojson: dict) -> MultiPolygon:
    """Validate a GeoJSON Polygon/MultiPolygon and return a 2-D MultiPolygon."""
    geo_type = geojson.get("type")
    coordinates = geojson.get("coordinates")
    if geo_type == "Polygon":
        polygons = [coordinates]
    elif geo_type == "MultiPolygon":
        polygons = coordinates
    else:
        raise ValueError("boundary must be a GeoJSON Polygon or MultiPolygon")
    if not polygons:
        raise ValueError("boundary has no polygons")
    for rings in polygons:
        if not rings:
            raise ValueError("polygon has no rings")
        for ring in rings:
            _check_ring(ring)

    geometry = shape(geojson)
    if isinstance(geometry, Polygon):
        geometry = MultiPolygon([geometry])
    geometry = MultiPolygon(
        [Polygon([p[:2] for p in poly.exterior.coords],
                 [[p[:2] for p in hole.coords] for hole in poly.interiors])
         for poly in geometry.geoms]
    )
    if not geometry.is_valid:
        raise ValueError(f"invalid polygon: {explain_validity(geometry)}")
    if geometry.area == 0:
        raise ValueError("polygon must enclose a non-zero area")
    return geometry


def to_geojson(boundary: MultiPolygon) -> dict:
    geojson = mapping(boundary)
    return {
        "type": geojson["type"],
        "coordinates": [
            [[list(position) for position in ring] for ring in polygon]
            for polygon in geojson["coordinates"]
        ],
    }


def interiors_overlap(a: MultiPolygon, b: MultiPolygon) -> bool:
    """True when the zones share area; touching along an edge is allowed."""
    return a.intersects(b) and not a.touches(b)


def covers_point(boundary: MultiPolygon, lng: float, lat: float) -> bool:
    return boundary.covers(Point(lng, lat))
