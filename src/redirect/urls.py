from django.urls import path

from . import views

app_name = "redirect"

urlpatterns = [
    path("go/<str:code>/", views.go, name="go"),
]
