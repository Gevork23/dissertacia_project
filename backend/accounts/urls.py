from django.urls import path

from .views import AccountsLoginView, AccountsLogoutView, profile_page, register_page

urlpatterns = [
    path("login/", AccountsLoginView.as_view(), name="accounts-login"),
    path("logout/", AccountsLogoutView.as_view(), name="accounts-logout"),
    path("register/", register_page, name="accounts-register"),
    path("profile/", profile_page, name="accounts-profile"),
]
