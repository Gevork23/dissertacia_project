from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.models import User
from django.db.models import Prefetch
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from documents.models import QuizAssignment, QuizAttempt

from .forms import RegistrationForm, StyledAuthenticationForm
from .models import UserProfile
from .permissions import get_user_display_name, is_admin


class AccountsLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = StyledAuthenticationForm
    redirect_authenticated_user = True


class AccountsLogoutView(LogoutView):
    next_page = "accounts-login"


@require_http_methods(["GET", "POST"])
def register_page(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("accounts-profile")

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, "Учётная запись создана.")
            login(request, user)
            return redirect("accounts-profile")
    else:
        form = RegistrationForm()

    return render(request, "accounts/register.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def profile_page(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        if not is_admin(request.user):
            return redirect("accounts-profile")

        target = get_object_or_404(User, pk=request.POST.get("user_id"))
        role = (request.POST.get("role") or UserProfile.Role.EMPLOYEE).strip()
        is_active = request.POST.get("is_active") == "on"
        if role not in {UserProfile.Role.ADMIN, UserProfile.Role.EMPLOYEE}:
            role = UserProfile.Role.EMPLOYEE

        target.is_active = is_active
        target.is_staff = role == UserProfile.Role.ADMIN
        target.is_superuser = role == UserProfile.Role.ADMIN
        target.save(update_fields=["is_active", "is_staff", "is_superuser"])
        UserProfile.objects.update_or_create(
            user=target,
            defaults={"role": role},
        )
        messages.success(request, f"Права пользователя {target.username} обновлены.")
        return redirect("accounts-profile")

    assignments = (
        QuizAssignment.objects.select_related(
            "quiz",
            "quiz__from_version__document",
            "quiz__to_version__document",
        )
        .filter(user=request.user)
        .order_by("-assigned_at")
    )
    attempts = (
        QuizAttempt.objects.select_related("quiz")
        .filter(participant_name__in=[get_user_display_name(request.user), request.user.username])
        .order_by("-created_at")[:10]
    )
    managed_users = []
    if is_admin(request.user):
        managed_users = (
            User.objects.select_related("profile")
            .prefetch_related(
                Prefetch(
                    "quiz_assignments",
                    queryset=QuizAssignment.objects.select_related("quiz").order_by("-assigned_at"),
                )
            )
            .order_by("username")
        )

    return render(
        request,
        "accounts/profile.html",
        {
            "assignments": assignments,
            "attempts": attempts,
            "managed_users": managed_users,
            "is_admin": is_admin(request.user),
        },
    )

