from django.urls import path

from . import views

app_name = "quality"
urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("scan/", views.scan, name="scan"),
    path("fix/units/", views.fix_units, name="fix_units"),
    path("fix/numbers/", views.fix_numbers, name="fix_numbers"),
    path("merge/<int:pk>/<int:other_pk>/", views.merge, name="merge"),
    path("fill/<int:pk>/", views.fill, name="fill"),
]
