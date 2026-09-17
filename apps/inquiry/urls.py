from django.urls import path

from . import views

app_name = "inquiry"
urlpatterns = [
    path("", views.workbench, name="workbench"),
    path("history/", views.history, name="history"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/lines/<int:line_id>/select/", views.select, name="select"),
    path("<int:pk>/lines/<int:line_id>/feedback/", views.feedback, name="feedback"),
    path("<int:pk>/quote/summary/", views.quote_summary, name="quote_summary"),
    path("<int:pk>/quote/email/", views.quote_email, name="quote_email"),
    path("<int:pk>/quote.pdf", views.quote_pdf, name="quote_pdf"),
]
