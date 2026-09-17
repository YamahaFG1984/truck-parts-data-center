from django.urls import path

from . import views

app_name = "listing"
urlpatterns = [
    path("", views.listing_list, name="list"),
    path("generate/<int:product_pk>/<str:platform>/", views.generate_view, name="generate"),
    path("<int:pk>/", views.edit, name="edit"),
    path("export/shopify.csv", views.export_shopify, name="export_shopify"),
]
