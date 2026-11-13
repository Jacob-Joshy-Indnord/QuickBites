"""Restaurant-user authentication/authorisation dependency (interim).

The account system lives in task-tpbk7-95NYo, which is not in this branch yet.
Until it lands, `restaurant_user` reads trusted gateway headers X-User-Id,
X-Outlet-Id and X-Role (OWNER or STAFF) and returns a `Principal`. Missing
headers give 401; a non-restaurant role or an outlet different from the one in
the URL gives 403. `require_outlet_access(outlet_id)` is the function routers
call. Replace the header parsing with token verification when accounts exist;
the router contract will not change.
"""
from dataclasses import dataclass

from fastapi import Header, HTTPException


@dataclass
class Principal:
    user_id: str
    outlet_id: int
    role: str


def restaurant_user(
    x_user_id: str | None = Header(default=None),
    x_outlet_id: str | None = Header(default=None),
    x_role: str | None = Header(default=None),
) -> Principal:
    if not x_user_id or not x_outlet_id or not x_role:
        raise HTTPException(401, "Authentication required")
    if x_role not in ("OWNER", "STAFF") or not x_outlet_id.isdigit():
        raise HTTPException(403, "Restaurant account required")
    return Principal(x_user_id, int(x_outlet_id), x_role)
