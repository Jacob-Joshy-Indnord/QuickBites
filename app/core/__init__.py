"""Cross-cutting core utilities for the QuickBites backend.

The ``app.core`` package holds concerns shared by every capability module
rather than owned by one of them. Today it contains ``app.core.auth``, which
defines the authenticated ``Principal`` model, the ``OpsRole`` enumeration and
the FastAPI dependencies used to enforce ops role-based access control (for
example ``require_ops_admin``). Future additions such as settings loading,
database engine construction, structured logging, PII masking and rate
limiting are expected to live here as well, keeping capability packages like
``app.zones`` free of infrastructure plumbing. This module defines no
functions or classes of its own; it only marks the directory as a package and
explains its purpose to readers.
"""
