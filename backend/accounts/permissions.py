from __future__ import annotations

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def get_user_role(user) -> str:
    if not getattr(user, "is_authenticated", False):
        return ""
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return "admin"
    profile = getattr(user, "profile", None)
    return getattr(profile, "role", "") or "employee"


def is_admin(user) -> bool:
    return get_user_role(user) == "admin"


def is_employee(user) -> bool:
    return bool(getattr(user, "is_authenticated", False)) and not is_admin(user)


def get_user_display_name(user) -> str:
    full_name = " ".join(
        part.strip() for part in [getattr(user, "first_name", ""), getattr(user, "last_name", "")] if part.strip()
    )
    return full_name or getattr(user, "username", "")


def admin_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not is_admin(request.user):
            raise PermissionDenied("Admin access required.")
        return view_func(request, *args, **kwargs)

    return wrapped

