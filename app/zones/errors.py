"""Domain errors raised by the zones capability.

The zone service and its repositories signal business-rule failures with the
exceptions defined here instead of HTTP errors, keeping the domain layer
independent of FastAPI. ``ZoneError`` is the common base class.
``ZoneNotFoundError`` is raised when an operation targets a zone id that does
not exist; the router maps it to HTTP 404. ``ZoneConflictError`` is raised
when a create or edit would violate a uniqueness invariant — another zone
already uses the same case-insensitive name, or the new boundary overlaps the
interior of another active zone (which would make address resolution
ambiguous); the router maps it to HTTP 409. The module defines no functions,
only these three exception classes and their docstrings.
"""


class ZoneError(Exception):
    """Base class for zone domain errors."""


class ZoneNotFoundError(ZoneError):
    """The requested zone does not exist."""


class ZoneConflictError(ZoneError):
    """The change would break name uniqueness or the no-overlap rule."""
