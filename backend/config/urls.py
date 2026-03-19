from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path

admin.site.site_header = "ДГТУ — администрирование backend"
admin.site.site_title = "ДГТУ Admin"
admin.site.index_title = "Управление backend-проектом"


def root_redirect(request):
    return redirect("demo-dashboard")


urlpatterns = [
    path("", root_redirect, name="root-redirect"),
    path("demo/", include("documents.demo.urls")),
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
    path("api/", include("documents.api.urls")),
    path(
        "api/v1/",
        include(("documents.api.urls", "documents"), namespace="documents-v1"),
    ),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
