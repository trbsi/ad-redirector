from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .services.filtering import ChallengeService
from .services.redirect import RedirectService


@require_GET
def home(request):
    return render(request, "redirect/home.html")


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
