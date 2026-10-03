from django.core import signing

COOKIE_NAME = "rc"
COOKIE_MAX_AGE = 30 * 24 * 60 * 60
SALT = "redirect.challenge"


class ChallengeService:
    """JavaScript check: the challenge page sets a signed cookie and reloads.

    Visitors that don't run JavaScript (almost all bots) never get the cookie, so never get through.
    """

    cookie_name = COOKIE_NAME
    cookie_max_age = COOKIE_MAX_AGE

    def __init__(self, request):
        self.request = request

    def passed(self):
        value = self.request.COOKIES.get(COOKIE_NAME)
        if not value:
            return False
        try:
            signing.TimestampSigner(salt=SALT).unsign(value, max_age=COOKIE_MAX_AGE)
        except signing.BadSignature:
            return False
        return True

    def token(self):
        return signing.TimestampSigner(salt=SALT).sign("ok")
