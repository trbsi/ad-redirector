from django.urls import path

from . import views

app_name = "redirect"

urlpatterns = [
    path("", views.home, name="home"),
    path("go/<str:code>/", views.go, name="go"),
]
