from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    path("products/", include("apps.catalog.urls")),
    path("suppliers/", include("apps.suppliers.urls")),
    path("inquiry/", include("apps.inquiry.urls")),
    path("ingest/", include("apps.ingest.urls")),
    path("quality/", include("apps.quality.urls")),
    path("listing/", include("apps.listing.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = "卡车配件 AI 数据中心"
admin.site.site_title = "数据中心后台"
