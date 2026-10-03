from urllib.parse import quote

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import salted_hmac


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


def hash_ip(ip):
    """Keyed hash of an IP: recognizes a returning visitor without storing the address."""
    if not ip:
        return ""
    return salted_hmac("redirect.click.ip", ip, algorithm="sha256").hexdigest()


class Click(models.Model):
    """One visit to a link, logged before redirecting."""

    link = models.ForeignKey(Link, on_delete=models.CASCADE, related_name="clicks")
    # Cleared after CLICK_IP_RETENTION_DAYS; ip_hash stays for the repeat-click check.
    ip = models.GenericIPAddressField(null=True, blank=True)
    ip_hash = models.CharField(max_length=64, blank=True, default="", editable=False)
    target_url = models.URLField(max_length=500)
    # Empty when the visit was sent to the link's target; otherwise the filter that blocked it.
    blocked_reason = models.CharField(max_length=32, blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["link", "ip_hash", "created_at"])]

    def __str__(self):
        return f"{self.link} from {self.ip or 'unknown'}"

    def save(self, *args, **kwargs):
        if self.ip and not self.ip_hash:
            self.ip_hash = hash_ip(self.ip)
        super().save(*args, **kwargs)
