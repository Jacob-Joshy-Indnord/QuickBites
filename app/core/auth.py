"""Ops authentication principal and role-based access control dependencies.

This module provides the minimal RBAC seam required by admin-only endpoints
(task-tphOBokN7Z0: only ops admins may manage zones, fees, commission,
promotions and onboarding approvals). It defines ``OpsRole`` (ops_admin or
ops_agent), the immutable ``Principal`` dataclass carrying the IdP subject id
and role, and three functions: ``get_current_principal`` — the dependency that
resolves the caller; it deliberately fails closed with 401 until the OIDC
session layer overrides it — ``require_ops_admin``, which returns the
principal only when it holds the admin role and otherwise raises 403, and
``require_ops_staff``, which admits any ops role. No credentials are parsed
here.
"""

from dataclasses import dataclass
from enum import StrEnum

from fastapi import Depends, HTTPException, status


class OpsRole(StrEnum):
    OPS_ADMIN = "ops_admin"
    OPS_AGENT = "ops_agent"


@dataclass(frozen=True)
class Principal:
    """An authenticated ops staff member, identified by their IdP subject."""

    subject: str
    role: OpsRole


def get_current_principal() -> Principal:
    """Resolve the authenticated caller.

    Fails closed: the OIDC session layer replaces this dependency via
    ``app.dependency_overrides`` (or by wiring its own resolver) once it lands.
    """
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )


def require_ops_staff(principal: Principal = Depends(get_current_principal)) -> Principal:
    """Admit any ops role (agent or admin)."""
    return principal


def require_ops_admin(principal: Principal = Depends(get_current_principal)) -> Principal:
    """Admit only ops admins; agents receive 403."""
    if principal.role is not OpsRole.OPS_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ops admin role required",
        )
    return principal
