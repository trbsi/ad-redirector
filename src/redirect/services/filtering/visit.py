from dataclasses import dataclass

from django.http import HttpRequest

from ...models import Link


@dataclass(frozen=True)
class Visit:
    """What the filters know about one request to a link."""

    request: HttpRequest
    link: Link
    ip: str | None

    @property
    def user_agent(self):
        return self.request.META.get("HTTP_USER_AGENT", "")
