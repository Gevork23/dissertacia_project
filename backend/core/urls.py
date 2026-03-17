from django.urls import path

from .views import api_root, health, live

urlpatterns = [
    path("", api_root, name="api-root"),
    path("health", health, name="health"),
    path("health/", health),
    path("health/live", live, name="live"),
    path("health/live/", live),
]
