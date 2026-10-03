from django.http import HttpResponseRedirect
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .services.go import GoService


@never_cache
@require_GET
def go(request, code):
    return HttpResponseRedirect(GoService(request).execute(code))
