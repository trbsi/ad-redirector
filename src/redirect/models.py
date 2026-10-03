from urllib.parse import quote

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Link(models.Model):
    """A JuicyAds code ID that can be shared as a direct link."""

    code = models.CharField(
        "JuicyAds code ID",
        max_length=255,
        unique=True,
        validators=[
            RegexValidator(
                r"^[0-9a-z]+$",
                "Code IDs contain only lowercase letters and digits, "
                "e.g. 3484x2z2w2a4u4q2r28463o5111.",
            )
        ],
    )
    visits = models.PositiveBigIntegerField(default=0, editable=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.code

    def get_absolute_url(self):
        return reverse("redirect:go", args=[self.code])

    @property
    def target_url(self):
        return settings.JUICYADS_REDIRECT_URL.format(code=quote(self.code, safe=""))


class Click(models.Model):
    """One visit to a link, logged before redirecting."""

    link = models.ForeignKey(Link, on_delete=models.CASCADE, related_name="clicks")
    ip = models.GenericIPAddressField(null=True, blank=True)
    target_url = models.URLField(max_length=500)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.link} from {self.ip or 'unknown'}"
