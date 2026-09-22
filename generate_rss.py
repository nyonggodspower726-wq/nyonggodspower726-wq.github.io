import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, ElementTree


SITE_URL = "https://nyonggodspower726-wq.github.io"
ARTICLES_DIR = Path("articles")
OUTPUT_FILE = Path("rss.xml")

FEED_TITLE = "AI News Factory"
FEED_DESCRIPTION = (
    "Latest news and analysis from AI News Factory."
)

MAX_ITEMS = 25


def clean_text(value):
    if not value:
        return ""

    value = html.unescape(str(value))
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def strip_html(value):
    if not value:
        return ""

    value = re.sub(r"<[^>]+>", " ", value)
    return clean_text(value)


def get_meta(content, name=None, property_name=None):
    if name:
        pattern = (
            r'<meta[^>]+name=["\']'
            + re.escape(name)
            + r'["\'][^>]+content=["\']([^"\']*)["\']'
        )
    else:
        pattern = (
            r'<meta[^>]+property=["\']'
            + re.escape(property_name)
            + r'["\'][^>]+content=["\']([^"\']*)["\']'
        )

    match = re.search(
        pattern,
        content,
        re.IGNORECASE
    )

    if match:
        return html.unescape(match.group(1)).strip()

    return ""


def get_title(content):
    match = re.search(
        r"<title[^>]*>(.*?)</title>",
        content,
        re.IGNORECASE | re.DOTALL
    )

    if match:
        return clean_text(match.group(1))

    match = re.search(
        r"<h1[^>]*>(.*?)</h1>",
        content,
        re.IGNORECASE | re.DOTALL
    )

    if match:
        return strip_html(match.group(1))

    return ""


def get_jsonld(content):
    matches = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>'
        r'(.*?)'
        r'</script>',
        content,
        re.IGNORECASE | re.DOTALL
    )

    for raw in matches:
        raw = raw.strip()

        try:
            data = json.loads(raw)

            if isinstance(data, dict):
                return data

            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        return item

        except Exception:
            continue

    return {}


def get_article_body(content):
    match = re.search(
        r'<article[^>]*class=["\'][^"\']*article-body[^"\']*["\'][^>]*>'
        r'(.*?)'
        r'</article>',
        content,
        re.IGNORECASE | re.DOTALL
    )

    if not match:
        return ""

    body = match.group(1).strip()

    # Remove scripts and styles if present.
    body = re.sub(
        r"<script\b[^>]*>.*?</script>",
        "",
        body,
        flags=re.IGNORECASE | re.DOTALL
    )

    body = re.sub(
        r"<style\b[^>]*>.*?</style>",
        "",
        body,
        flags=re.IGNORECASE | re.DOTALL
    )

    return body.strip()


def get_category(content, jsonld):
    category = ""

    if isinstance(jsonld, dict):
        category = jsonld.get(
            "articleSection",
            ""
        )

    if not category:
        match = re.search(
            r'<div[^>]+class=["\']category["\'][^>]*>'
            r'(.*?)</div>',
            content,
            re.IGNORECASE | re.DOTALL
        )

        if match:
            category = strip_html(
                match.group(1)
            )

    return clean_text(category) or "general"


def get_author(jsonld):
    if not isinstance(jsonld, dict):
        return "AI News Factory"

    author = jsonld.get("author")

    if isinstance(author, dict):
        return clean_text(
            author.get(
                "name",
                "AI News Factory"
            )
        )

    if isinstance(author, list):
        for item in author:
            if isinstance(item, dict):
                name = item.get("name")

                if name:
                    return clean_text(name)

    if isinstance(author, str):
        return clean_text(author)

    return "AI News Factory"


def parse_date(value):
    if not value:
        return None

    value = value.strip()

    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"

        dt = datetime.fromisoformat(value)

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt.astimezone(
            timezone.utc
        )

    except Exception:
        return None


def rss_date(dt):
    return dt.strftime(
        "%a, %d %b %Y %H:%M:%S GMT"
    )


def absolute_url(filename):
    return (
        SITE_URL
        + "/articles/"
        + filename
    )


def extract_article(path):
    content = path.read_text(
        encoding="utf-8",
        errors="ignore"
    )

    jsonld = get_jsonld(content)

    title = get_title(content)

    description = get_meta(
        content,
        name="description"
    )

    if not description and isinstance(
        jsonld,
        dict
    ):
        description = clean_text(
            jsonld.get(
                "description",
                ""
            )
        )

    canonical = get_meta(
        content,
        property_name="og:url"
    )

    if not canonical:
        match = re.search(
            r'<link[^>]+rel=["\']canonical["\']'
            r'[^>]+href=["\']([^"\']+)["\']',
            content,
            re.IGNORECASE
        )

        if match:
            canonical = match.group(1).strip()

    if not canonical:
        canonical = absolute_url(
            path.name
        )

    image_url = get_meta(
        content,
        property_name="og:image"
    )

    if not image_url and isinstance(
        jsonld,
        dict
    ):
        image = jsonld.get("image")

        if isinstance(image, list):
            if image:
                image_url = str(image[0])

        elif isinstance(image, dict):
            image_url = image.get(
                "url",
                ""
            )

        elif isinstance(image, str):
            image_url = image

    published_at = ""

    if isinstance(jsonld, dict):
        published_at = jsonld.get(
            "datePublished",
            ""
        )

    if not published_at:
        match = re.search(
            r"Published\s+([^<·]+)",
            content,
            re.IGNORECASE
        )

        if match:
            published_at = (
                match.group(1)
                .strip()
            )

    modified_at = ""

    if isinstance(jsonld, dict):
        modified_at = jsonld.get(
            "dateModified",
            ""
        )

    published_dt = parse_date(
        published_at
    )

    modified_dt = parse_date(
        modified_at
    )

    if not published_dt:
        return None

    if not modified_dt:
        modified_dt = published_dt

    body = get_article_body(content)

    if not title or not body:
        return None

    category = get_category(
        content,
        jsonld
    )

    author = get_author(
        jsonld
    )

    return {
        "title": clean_text(title),
        "description": clean_text(
            description
        ),
        "url": canonical,
        "image": clean_text(
            image_url
        ),
        "published": published_dt,
        "modified": modified_dt,
        "body": body,
        "category": category,
        "author": author,
    }


def load_articles():
    articles = []

    if not ARTICLES_DIR.exists():
        print(
            "ERROR: articles directory not found."
        )
        return articles

    for path in ARTICLES_DIR.glob(
        "*.html"
    ):
        try:
            article = extract_article(
                path
            )

            if article:
                articles.append(article)

        except Exception as exc:
            print(
                f"WARNING: Could not parse "
                f"{path}: {exc}"
            )

    articles.sort(
        key=lambda item: item["published"],
        reverse=True
    )

    return articles[:MAX_ITEMS]


def add_text(parent, tag, value):
    element = SubElement(
        parent,
        tag
    )

    element.text = value or ""

    return element


def build_feed(articles):
    rss = Element(
        "rss",
        {
            "version": "2.0",
            "xmlns:atom":
                "http://www.w3.org/2005/Atom",
            "xmlns:media":
                "http://search.yahoo.com/mrss/",
            "xmlns:dc":
                "http://purl.org/dc/elements/1.1/",
            "xmlns:dcterms":
                "http://purl.org/dc/terms/",
            "xmlns:mi":
                "http://schemas.ingestion.microsoft.com/common/",
        }
    )

    channel = SubElement(
        rss,
        "channel"
    )

    add_text(
        channel,
        "title",
        FEED_TITLE
    )

    add_text(
        channel,
        "link",
        SITE_URL
    )

    add_text(
        channel,
        "description",
        FEED_DESCRIPTION
    )

    add_text(
        channel,
        "language",
        "en"
    )

    now = datetime.now(
        timezone.utc
    )

    add_text(
        channel,
        "lastBuildDate",
        rss_date(now)
    )

    atom_link = SubElement(
        channel,
        "{http://www.w3.org/2005/Atom}link",
        {
            "href":
                SITE_URL + "/rss.xml",
            "rel": "self",
            "type":
                "application/rss+xml",
        }
    )

    for article in articles:
        item = SubElement(
            channel,
            "item"
        )

        url = article["url"]

        # Stable unique ID.
        guid = SubElement(
            item,
            "guid",
            {
                "isPermaLink": "true"
            }
        )

        guid.text = url

        add_text(
            item,
            "title",
            article["title"]
        )

        add_text(
            item,
            "link",
            url
        )

        add_text(
            item,
            "pubDate",
            rss_date(
                article["published"]
            )
        )

        modified = SubElement(
            item,
            "{http://purl.org/dc/terms/}"
            "modified"
        )

        modified.text = (
            article["modified"]
            .isoformat()
        )

        add_text(
            item,
            "description",
            article["description"]
        )

        author = SubElement(
            item,
            "{http://purl.org/dc/elements/1.1/}"
            "creator"
        )

        author.text = article["author"]

        add_text(
            item,
            "category",
            article["category"]
        )

        # MSN allows HTML in article bodies.
        encoded = SubElement(
            item,
            "{http://purl.org/rss/1.0/modules/"
            "content/}"
            "encoded"
        )

        encoded.text = article["body"]

        if article["image"]:
            media_content = SubElement(
                item,
                "{http://search.yahoo.com/mrss/}"
                "content",
                {
                    "url":
                        article["image"],
                    "medium":
                        "image",
                }
            )

            media_content.set(
                "type",
                "image/jpeg"
            )

            media_description = SubElement(
                media_content,
                "{http://search.yahoo.com/mrss/}"
                "description"
            )

            media_description.text = (
                article["title"]
            )

    tree = ElementTree(
        rss
    )

    tree.write(
        OUTPUT_FILE,
        encoding="utf-8",
        xml_declaration=True
    )


def main():
    articles = load_articles()

    print(
        f"Found {len(articles)} article(s)."
    )

    if not articles:
        print(
            "WARNING: No articles found."
        )

    build_feed(
        articles
    )

    print(
        f"RSS feed generated: "
        f"{OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()
