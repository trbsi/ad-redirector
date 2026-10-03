from django.conf import settings
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .services.filtering import ChallengeService
from .services.redirect import RedirectService


@require_GET
def home(request):
    return render(request, "redirect/home.html")


@require_GET
def privacy(request):
    return render(
        request,
        "redirect/privacy.html",
        {
            "operator_name": settings.PRIVACY_OPERATOR_NAME,
            "contact_email": settings.PRIVACY_CONTACT_EMAIL,
            "ip_retention_days": settings.CLICK_IP_RETENTION_DAYS,
            "blocked_retention_days": settings.BLOCKED_CLICK_RETENTION_DAYS,
            "retention_days": settings.CLICK_RETENTION_DAYS,
            "cookie_name": ChallengeService.cookie_name,
            "cookie_days": ChallengeService.cookie_max_age // (24 * 60 * 60),
        },
    )


@never_cache
@require_GET
def go(request, code):
    result = RedirectService(request).execute(code)
    if result.challenge_token:
        return render(
            request,
            "redirect/challenge.html",
            {
                "token": result.challenge_token,
                "cookie_name": ChallengeService.cookie_name,
                "cookie_max_age": ChallengeService.cookie_max_age,
            },
        )
    return HttpResponseRedirect(result.url)
