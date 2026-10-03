import re

# Servers that fetch a link to build a chat or social media preview, not people.
PREVIEW_CRAWLERS = re.compile(
    r"facebookexternalhit|facebookcatalog|meta-externalagent|twitterbot|telegrambot|whatsapp"
    r"|slackbot|slack-imgproxy|discordbot|linkedinbot|skypeuripreview|pinterestbot|redditbot"
    r"|applebot|embedly|iframely|vkshare|bingpreview|googleother|mastodon",
    re.IGNORECASE,
)


class PreviewCrawlerFilterService:
    """Blocks link-preview fetches from chat apps and social networks."""

    reason = "preview_crawler"

    def __init__(self, visit):
        self.visit = visit

    def matches(self):
        return bool(PREVIEW_CRAWLERS.search(self.visit.user_agent))
