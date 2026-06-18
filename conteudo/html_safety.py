from html import escape
from html.parser import HTMLParser
from urllib.parse import urlsplit


EMAIL_ALLOWED_TAGS = {
    "a",
    "b",
    "br",
    "em",
    "h2",
    "h3",
    "hr",
    "i",
    "li",
    "ol",
    "p",
    "strong",
    "u",
    "ul",
}
EMAIL_VOID_TAGS = {"br", "hr"}
EMAIL_SKIP_CONTENT_TAGS = {
    "script",
    "style",
    "iframe",
    "object",
    "embed",
    "svg",
    "math",
    "noscript",
    "textarea",
    "template",
}
EMAIL_ALLOWED_URI_SCHEMES = {"http", "https", "mailto"}


def _sanitize_email_href(value):
    href = (value or "").strip()
    if not href:
        return ""

    parsed = urlsplit(href)
    scheme = (parsed.scheme or "").lower()
    lowered = href.lower()

    if lowered.startswith("//"):
        return ""
    if scheme:
        if scheme not in EMAIL_ALLOWED_URI_SCHEMES:
            return ""
        return href
    if href.startswith("/") or href.startswith("#"):
        return href
    return ""


class _LimitedEmailHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.open_tags = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = (tag or "").lower()
        if self.skip_depth:
            if tag in EMAIL_SKIP_CONTENT_TAGS:
                self.skip_depth += 1
            return
        if tag in EMAIL_SKIP_CONTENT_TAGS:
            self.skip_depth = 1
            return
        if tag not in EMAIL_ALLOWED_TAGS:
            return

        if tag == "a":
            attrs_out = []
            for name, value in attrs:
                if (name or "").lower() == "href":
                    href = _sanitize_email_href(value)
                    if href:
                        attrs_out.append(("href", href))
                elif (name or "").lower() == "title" and value:
                    attrs_out.append(("title", value))
            if any(name == "href" for name, _ in attrs_out):
                attrs_out.append(("rel", "noopener noreferrer nofollow"))
            attrs_html = "".join(
                f' {escape(name, quote=True)}="{escape(value, quote=True)}"'
                for name, value in attrs_out
            )
        else:
            attrs_html = ""

        if tag in EMAIL_VOID_TAGS:
            self.parts.append(f"<{tag}{attrs_html}>")
            return

        self.parts.append(f"<{tag}{attrs_html}>")
        self.open_tags.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        tag = (tag or "").lower()
        if self.skip_depth:
            if tag in EMAIL_SKIP_CONTENT_TAGS:
                self.skip_depth = max(0, self.skip_depth - 1)
            return
        if tag not in EMAIL_ALLOWED_TAGS or tag in EMAIL_VOID_TAGS:
            return
        if tag not in self.open_tags:
            return
        while self.open_tags:
            current = self.open_tags.pop()
            self.parts.append(f"</{current}>")
            if current == tag:
                break

    def handle_data(self, data):
        if self.skip_depth or not data:
            return
        self.parts.append(escape(data))

    def handle_comment(self, data):
        return

    def get_html(self):
        while self.open_tags:
            self.parts.append(f"</{self.open_tags.pop()}>")
        return "".join(self.parts).strip()


def sanitize_email_html(value):
    parser = _LimitedEmailHTMLParser()
    parser.feed(value or "")
    parser.close()
    return parser.get_html()
