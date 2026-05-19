from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver

from .models import UserProfile


@receiver(post_save, sender=get_user_model())
def ensure_user_profile(sender, instance, created, **kwargs):
    if created:
        role = UserProfile.Role.ADMIN if (instance.is_superuser or instance.is_staff) else UserProfile.Role.EMPLOYEE
        UserProfile.objects.get_or_create(user=instance, defaults={"role": role})
    else:
        profile, _ = UserProfile.objects.get_or_create(
            user=instance,
            defaults={
                "role": (
                    UserProfile.Role.ADMIN
                    if (instance.is_superuser or instance.is_staff)
                    else UserProfile.Role.EMPLOYEE
                )
            },
        )
        desired_role = (
            UserProfile.Role.ADMIN
            if (instance.is_superuser or instance.is_staff)
            else profile.role
        )
        if profile.role != desired_role:
            profile.role = desired_role
            profile.save(update_fields=["role", "updated_at"])


@receiver(post_migrate)
def create_bootstrap_users(sender, app_config=None, **kwargs):
    if sender.name != "accounts":
        return

    user_model = get_user_model()

    admin_user, created_admin = user_model.objects.get_or_create(
        username="admin",
        defaults={
            "is_staff": True,
            "is_superuser": True,
            "is_active": True,
            "first_name": "System",
            "last_name": "Admin",
        },
    )
    if created_admin:
        admin_user.set_password("admin")
        admin_user.save()
    else:
        changed = False
        if not admin_user.is_staff:
            admin_user.is_staff = True
            changed = True
        if not admin_user.is_superuser:
            admin_user.is_superuser = True
            changed = True
        if not admin_user.is_active:
            admin_user.is_active = True
            changed = True
        if changed:
            admin_user.save(update_fields=["is_staff", "is_superuser", "is_active"])
    UserProfile.objects.update_or_create(
        user=admin_user,
        defaults={"role": UserProfile.Role.ADMIN},
    )

    employee_user, created_employee = user_model.objects.get_or_create(
        username="user",
        defaults={
            "is_active": True,
            "first_name": "Demo",
            "last_name": "Employee",
        },
    )
    if created_employee:
        employee_user.set_password("user")
        employee_user.save()
    elif not employee_user.is_active:
        employee_user.is_active = True
        employee_user.save(update_fields=["is_active"])
    UserProfile.objects.update_or_create(
        user=employee_user,
        defaults={"role": UserProfile.Role.EMPLOYEE},
    )

