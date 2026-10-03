import re

# Crawlers, HTTP libraries, command-line tools and headless browsers.
# "bot" only counts as "Somebot/1.0", "Somebot;" or "Somebot)", so phone models like CUBOT pass.
# "+http://..." is the info URL crawlers put in their User-Agent; browsers never do.
BOTS = re.compile(
    r"bot/|bot;|bot\)|\bbot\b|\+https?://|crawl|spider|slurp|curl|wget|python|requests|httpx"
    r"|aiohttp|go-http-client"
    r"|java/|okhttp|libwww|scrapy|headless|phantomjs|selenium|puppeteer|playwright"
    r"|node-fetch|axios|postman|insomnia|httpclient|lighthouse|pingdom|uptime",
    re.IGNORECASE,
)


class BotFilterService:
    """Blocks bots and scripts: known bot User-Agents, or headers every real browser sends missing."""

    reason = "bot"

    def __init__(self, visit):
        self.visit = visit

    def matches(self):
        meta = self.visit.request.META
        if not self.visit.user_agent or BOTS.search(self.visit.user_agent):
            return True
        return not meta.get("HTTP_ACCEPT") or not meta.get("HTTP_ACCEPT_LANGUAGE")
