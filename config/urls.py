from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Ad Redirector"
admin.site.site_title = "Ad Redirector"

urlpatterns = [
    path("privateplace/", admin.site.urls),
    path("", include("src.redirect.urls")),
]
