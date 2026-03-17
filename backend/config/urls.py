from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "ДГТУ — администрирование backend"
admin.site.site_title = "ДГТУ Admin"
admin.site.index_title = "Управление backend-проектом"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
    path("api/", include("documents.urls")),
    path("api/v1/", include(("documents.urls", "documents"), namespace="documents-v1")),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
