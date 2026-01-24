from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import DocumentViewSet, DocumentVersionViewSet
from .api import search

router = DefaultRouter()
router.register("documents", DocumentViewSet, basename="documents")
router.register("versions", DocumentVersionViewSet, basename="versions")

urlpatterns = [
    path("search/", search, name="search"),
] + router.urls
