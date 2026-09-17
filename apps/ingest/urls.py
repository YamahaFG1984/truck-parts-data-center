from django.urls import path

from . import views

app_name = "ingest"
urlpatterns = [
    path("", views.batch_list, name="list"),
    path("<int:pk>/", views.batch_detail, name="detail"),
    path("<int:pk>/stats/", views.stats, name="stats"),
    path("<int:pk>/reprocess/", views.reprocess, name="reprocess"),
    path("<int:pk>/bulk-approve/", views.bulk_approve, name="bulk_approve"),
    path("rows/<int:pk>/action/", views.row_action, name="row_action"),
]
