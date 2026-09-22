from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse
from email.utils import format_datetime
import json
import mimetypes
import re
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup


# ============================================================
# NEWSROOM CONFIGURATION
# ============================================================

SITE_URL = "https://nyonggodspower726-wq.github.io"
ARTICLES_DIR = Path("articles")
OUTPUT_FILE = Path("rss.xml")

# MSN recommends keeping the number of fresh feed items below 30.
MAX_ITEMS = 25


# ============================================================
# RSS NAMESPACES
# ============================================================

NS_ATOM = "http://www.w3.org/2005/Atom"
NS_CONTENT = "http://purl.org/rss/1.0/modules/content/"
NS_DC = "http://purl.org/dc/elements/1.1/"
NS_DCTERMS = "http://purl.org/dc/terms/"
NS_MEDIA = "http://search.yahoo.com/mrss/"
NS_MI = "http://schemas.microsoft.com/msn/mi"

ET.register_namespace("atom", NS_ATOM)
ET.register_namespace("content", NS_CONTENT)
ET.register_namespace("dc", NS_DC)
ET.register_namespace("dcterms", NS_DCTERMS)
ET.register_namespace("media", NS_MEDIA)
ET.register_namespace("mi", NS_MI)


# ============================================================
# IMAGE RIGHTS / OWNERSHIP SETTINGS
# ============================================================

# Hosts that are automatically considered part of our newsroom.
# The GitHub Pages hostname is included because an AI-generated
# image may be published directly from the newsroom site.
TRUSTED_IMAGE_HOSTS = {
    urlparse(SITE_URL).netloc.lower(),
}

# Image URL path patterns commonly used by our generated-media
# system. These are deliberately narrow.
TRUSTED_IMAGE_PATH_PATTERNS = (
    "/media/generated/",
    "/generated/",
    "/media/images/",
    "/images/generated/",
)


# ============================================================
# GENERAL HELPERS
# ============================================================

def clean_text(value):
    if not value:
        return ""

    value = BeautifulSoup(str(value), "html.parser").get_text(
        " ",
        strip=True
    )

    value = re.sub(r"\s+", " ", value).strip()

    return value


def clean_title(title):
    if not title:
        return "Untitled"

    title = clean_text(title)

    # Remove common factory suffixes.
    title = re.sub(
        r"\s*\|\s*AI News Factory\s*$",
        "",
        title,
        flags=re.IGNORECASE
    )

    title = re.sub(
        r"\s*[-–—|]\s*AI News Factory\s*$",
        "",
        title,
        flags=re.IGNORECASE
    )

    # Remove accidental trailing separators.
    title = re.sub(r"\s*[|:,-]\s*$", "", title).strip()

    return title


def absolute_url(url):
    if not url:
        return ""

    url = str(url).strip()

    if url.startswith("//"):
        return "https:" + url

    if url.startswith("http://") or url.startswith("https://"):
        return url

    if url.startswith("/"):
        return SITE_URL.rstrip("/") + url

    return url


def parse_datetime(value):
    if not value:
        return None

    value = str(value).strip()

    # ISO formats.
    try:
        value_clean = value.replace("Z", "+00:00")

        dt = datetime.fromisoformat(value_clean)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc)

    except Exception:
        pass

    # Common HTML date formats.
    formats = [
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%f%z",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(value, fmt)

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            return dt.astimezone(timezone.utc)

        except Exception:
            continue

    return None


def get_meta(soup, *names):
    for name in names:
        tag = soup.find(
            "meta",
            attrs={"property": name}
        )

        if not tag:
            tag = soup.find(
                "meta",
                attrs={"name": name}
            )

        if tag and tag.get("content"):
            return tag.get("content").strip()

    return ""


# ============================================================
# JSON-LD
# ============================================================

def get_json_ld(soup):
    scripts = soup.find_all(
        "script",
        attrs={"type": "application/ld+json"}
    )

    for script in scripts:
        raw = script.string or script.get_text()

        if not raw:
            continue

        try:
            data = json.loads(raw)
        except Exception:
            continue

        if isinstance(data, dict):

            # Direct Article object.
            if (
                data.get("@type") in (
                    "Article",
                    "NewsArticle",
                    "ReportageNewsArticle",
                    "BlogPosting",
                )
            ):
                return data

            # @graph.
            graph = data.get("@graph")

            if isinstance(graph, list):
                for item in graph:
                    if not isinstance(item, dict):
                        continue

                    if item.get("@type") in (
                        "Article",
                        "NewsArticle",
                        "ReportageNewsArticle",
                        "BlogPosting",
                    ):
                        return item

        elif isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue

                if item.get("@type") in (
                    "Article",
                    "NewsArticle",
                    "ReportageNewsArticle",
                    "BlogPosting",
                ):
                    return item

    return {}


# ============================================================
# ARTICLE BODY
# ============================================================

def extract_article_body(soup):
    """
    Extract the main article body while avoiding navigation,
    headers, footers and unrelated page elements.
    """

    selectors = [
        "article",
        "[itemprop='articleBody']",
        ".article-content",
        ".article-body",
        ".post-content",
        ".entry-content",
        "main",
    ]

    container = None

    for selector in selectors:
        candidate = soup.select_one(selector)

        if candidate:
            container = candidate
            break

    if container is None:
        return ""

    # Remove elements that should never be syndicated as article body.
    for selector in [
        "script",
        "style",
        "noscript",
        "nav",
        "header",
        "footer",
        "form",
        ".advertisement",
        ".ads",
        ".ad",
        ".social-share",
        ".share-buttons",
        ".related-posts",
        ".comments",
        ".comment-section",
    ]:
        for tag in container.select(selector):
            tag.decompose()

    paragraphs = []

    for element in container.find_all(
        ["p", "h2", "h3", "h4", "blockquote", "ul", "ol"]
    ):
        text = clean_text(element)

        if not text:
            continue

        # Avoid duplicating extremely short navigation-like text.
        if len(text) < 2:
            continue

        paragraphs.append(
            str(element)
        )

    if paragraphs:
        return "\n".join(paragraphs)

    return str(container)


# ============================================================
# IMAGE EXTRACTION
# ============================================================

def extract_image(soup, json_ld):
    candidates = []

    # OpenGraph.
    og_image = get_meta(
        soup,
        "og:image",
        "og:image:url"
    )

    if og_image:
        candidates.append(og_image)

    # Twitter.
    twitter_image = get_meta(
        soup,
        "twitter:image",
        "twitter:image:src"
    )

    if twitter_image:
        candidates.append(twitter_image)

    # JSON-LD.
    image = json_ld.get("image")

    if isinstance(image, str):
        candidates.append(image)

    elif isinstance(image, list):
        for item in image:
            if isinstance(item, str):
                candidates.append(item)

            elif isinstance(item, dict):
                url = item.get("url") or item.get("contentUrl")

                if url:
                    candidates.append(url)

    elif isinstance(image, dict):
        url = image.get("url") or image.get("contentUrl")

        if url:
            candidates.append(url)

    # Article image element.
    selectors = [
        "article img",
        ".hero-image",
        ".featured-image",
        "main img",
    ]

    for selector in selectors:
        tag = soup.select_one(selector)

        if tag:
            src = (
                tag.get("src")
                or tag.get("data-src")
                or tag.get("data-lazy-src")
            )

            if src:
                candidates.append(src)

    # Return first usable image.
    seen = set()

    for candidate in candidates:
        candidate = absolute_url(candidate)

        if not candidate:
            continue

        if candidate in seen:
            continue

        seen.add(candidate)

        if candidate.startswith("http://") or candidate.startswith("https://"):
            return candidate

    return ""


# ============================================================
# IMAGE RIGHTS DETECTION
# ============================================================

def image_is_trusted(image_url):
    """
    Determines whether an image appears to be controlled by our
    newsroom/generated-media system.

    IMPORTANT:
    Unknown external images are NOT treated as licensed.
    """

    if not image_url:
        return False

    try:
        parsed = urlparse(image_url)

        host = (parsed.netloc or "").lower()
        path = (parsed.path or "").lower()

    except Exception:
        return False

    # Our own newsroom host.
    if host in TRUSTED_IMAGE_HOSTS:
        return True

    # Generated-media style paths.
    for pattern in TRUSTED_IMAGE_PATH_PATTERNS:
        if pattern in path:
            return True

    return False


def image_rights_status(image_url):
    """
    Returns a simple rights classification.
    """

    if not image_url:
        return "NONE"

    if image_is_trusted(image_url):
        return "TRUSTED"

    return "UNKNOWN_EXTERNAL"


# ============================================================
# AUTHOR
# ============================================================

def extract_author(soup, json_ld):
    author = json_ld.get("author")

    if isinstance(author, str):
        return clean_text(author)

    if isinstance(author, dict):
        name = author.get("name")

        if name:
            return clean_text(name)

    if isinstance(author, list):
        for item in author:
            if isinstance(item, str):
                return clean_text(item)

            if isinstance(item, dict) and item.get("name"):
                return clean_text(item["name"])

    return clean_text(
        get_meta(
            soup,
            "author",
            "article:author",
            "byl"
        )
    )


# ============================================================
# CATEGORY
# ============================================================

def extract_category(soup, json_ld):
    article_section = json_ld.get("articleSection")

    if isinstance(article_section, str):
        return clean_text(article_section)

    if isinstance(article_section, list):
        for item in article_section:
            if item:
                return clean_text(item)

    category = get_meta(
        soup,
        "article:section",
        "category"
    )

    return clean_text(category) or "general"


# ============================================================
# DESCRIPTION
# ============================================================

def extract_description(soup, json_ld):
    description = json_ld.get("description")

    if description:
        return clean_text(description)

    description = get_meta(
        soup,
        "description",
        "og:description",
        "twitter:description"
    )

    if description:
        return clean_text(description)

    # Fallback to first paragraph.
    paragraph = soup.find("p")

    if paragraph:
        return clean_text(paragraph)

    return ""


# ============================================================
# DATES
# ============================================================

def extract_dates(soup, json_ld):
    published = (
        json_ld.get("datePublished")
        or get_meta(
            soup,
            "article:published_time",
            "datePublished",
            "date"
        )
    )

    modified = (
        json_ld.get("dateModified")
        or get_meta(
            soup,
            "article:modified_time",
            "dateModified",
        )
    )

    published_dt = parse_datetime(published)
    modified_dt = parse_datetime(modified)

    if published_dt is None:
        published_dt = datetime.now(timezone.utc)

    if modified_dt is None:
        modified_dt = published_dt

    return published_dt, modified_dt


# ============================================================
# ARTICLE PARSER
# ============================================================

def parse_article(path):
    try:
        html = path.read_text(
            encoding="utf-8",
            errors="ignore"
        )

    except Exception as exc:
        print(f"Could not read {path}: {exc}")
        return None

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    json_ld = get_json_ld(soup)

    title = (
        json_ld.get("headline")
        or get_meta(
            soup,
            "og:title",
            "twitter:title"
        )
    )

    if not title:
        title_tag = soup.find("title")

        if title_tag:
            title = title_tag.get_text(
                " ",
                strip=True
            )

    title = clean_title(title)

    if not title or title == "Untitled":
        return None

    canonical = get_meta(
        soup,
        "og:url"
    )

    if not canonical:
        canonical_tag = soup.find(
            "link",
            rel="canonical"
        )

        if canonical_tag:
            canonical = canonical_tag.get("href", "")

    if canonical:
        url = absolute_url(canonical)
    else:
        url = (
            SITE_URL.rstrip("/")
            + "/articles/"
            + path.name
        )

    description = extract_description(
        soup,
        json_ld
    )

    content_html = extract_article_body(
        soup
    )

    if not content_html:
        return None

    image_url = extract_image(
        soup,
        json_ld
    )

    published_dt, modified_dt = extract_dates(
        soup,
        json_ld
    )

    author = extract_author(
        soup,
        json_ld
    )

    category = extract_category(
        soup,
        json_ld
    )

    rights_status = image_rights_status(
        image_url
    )

    return {
        "title": title,
        "url": url,
        "description": description,
        "content_html": content_html,
        "image_url": image_url,
        "image_rights": rights_status,
        "published_dt": published_dt,
        "modified_dt": modified_dt,
        "author": author or "AI News Factory",
        "category": category or "general",
    }


# ============================================================
# LOAD ARTICLES
# ============================================================

def load_articles():
    articles = []

    if not ARTICLES_DIR.exists():
        print(
            f"Articles directory does not exist: "
            f"{ARTICLES_DIR}"
        )
        return articles

    files = sorted(
        ARTICLES_DIR.glob("*.html"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    for path in files:
        article = parse_article(path)

        if not article:
            continue

        articles.append(article)

    # Newest first.
    articles.sort(
        key=lambda item: item.get(
            "published_dt"
        ) or datetime.min.replace(
            tzinfo=timezone.utc
        ),
        reverse=True
    )

    return articles[:MAX_ITEMS]


# ============================================================
# RSS ITEM
# ============================================================

def add_text_element(parent, tag, value):
    element = ET.SubElement(
        parent,
        tag
    )

    element.text = value or ""

    return element


def build_item(parent, article):
    item = ET.SubElement(
        parent,
        "item"
    )

    title = article["title"]
    url = article["url"]
    description = article["description"]
    content_html = article["content_html"]
    image_url = article["image_url"]
    image_rights = article["image_rights"]

    add_text_element(
        item,
        "title",
        title
    )

    add_text_element(
        item,
        "link",
        url
    )

    guid = ET.SubElement(
        item,
        "guid",
        {
            "isPermaLink": "true"
        }
    )

    guid.text = url

    published_dt = article["published_dt"]

    add_text_element(
        item,
        "pubDate",
        format_datetime(
            published_dt
        )
    )

    modified_dt = article["modified_dt"]

    modified_element = ET.SubElement(
        item,
        f"{{{NS_DCTERMS}}}modified"
    )

    modified_element.text = (
        modified_dt.isoformat()
    )

    add_text_element(
        item,
        "description",
        description
    )

    creator = ET.SubElement(
        item,
        f"{{{NS_DC}}}creator"
    )

    creator.text = article["author"]

    category = ET.SubElement(
        item,
        "category"
    )

    category.text = article["category"]

    # --------------------------------------------------------
    # MSN AI CONTENT DECLARATION
    # --------------------------------------------------------
    #
    # The newsroom uses AI-assisted generation.
    # Human review should still be part of your editorial process.
    #
    ai_category = ET.SubElement(
        item,
        "category"
    )

    ai_category.text = "AI-Assisted"

    # --------------------------------------------------------
    # FULL ARTICLE CONTENT
    # --------------------------------------------------------

    encoded = ET.SubElement(
        item,
        f"{{{NS_CONTENT}}}encoded"
    )

    encoded.text = content_html

    # --------------------------------------------------------
    # IMAGE RIGHTS HANDLING
    # --------------------------------------------------------
    #
    # This is the critical part.
    #
    # If the image is from our own trusted/generated system,
    # include it.
    #
    # If it is an unknown external image such as an image
    # hosted by another publisher, do NOT place it in
    # media:content.
    #
    # The article itself remains in the feed.
    # --------------------------------------------------------

    if image_url and image_rights == "TRUSTED":

        mime_type, _ = mimetypes.guess_type(
            image_url
        )

        if not mime_type:
            mime_type = "image/jpeg"

        media_content = ET.SubElement(
            item,
            f"{{{NS_MEDIA}}}content",
            {
                "url": image_url,
                "medium": "image",
                "type": mime_type,
            }
        )

        media_description = ET.SubElement(
            media_content,
            f"{{{NS_MEDIA}}}description"
        )

        media_description.text = title

        # MSN syndication-rights declaration.
        rights = ET.SubElement(
            item,
            f"{{{NS_MI}}}HasSyndicationRights"
        )

        rights.text = "true"

    elif image_url and image_rights == "UNKNOWN_EXTERNAL":

        print(
            "IMAGE EXCLUDED FROM RSS "
            f"(unknown external rights): {image_url}"
        )

    return item


# ============================================================
# BUILD RSS
# ============================================================

def build_rss(articles):
    rss = ET.Element(
        "rss",
        {
            "version": "2.0"
        }
    )

    channel = ET.SubElement(
        rss,
        "channel"
    )

    add_text_element(
        channel,
        "title",
        "AI News Factory"
    )

    add_text_element(
        channel,
        "link",
        SITE_URL
    )

    add_text_element(
        channel,
        "description",
        "Latest news and analysis from AI News Factory."
    )

    language = ET.SubElement(
        channel,
        "language"
    )

    language.text = "en-us"

    # Atom self-reference.
    atom_link = ET.SubElement(
        channel,
        f"{{{NS_ATOM}}}link",
        {
            "href": (
                SITE_URL.rstrip("/")
                + "/rss.xml"
            ),
            "rel": "self",
            "type": "application/rss+xml",
        }
    )

    atom_link.text = ""

    # Last build date.
    now = datetime.now(
        timezone.utc
    )

    add_text_element(
        channel,
        "lastBuildDate",
        format_datetime(now)
    )

    for article in articles:
        build_item(
            channel,
            article
        )

    return rss


# ============================================================
# WRITE RSS
# ============================================================

def write_rss(rss):
    tree = ET.ElementTree(rss)

    try:
        ET.indent(
            tree,
            space="  "
        )
    except AttributeError:
        pass

    tree.write(
        OUTPUT_FILE,
        encoding="utf-8",
        xml_declaration=True
    )


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 70)
    print("GENERATING NEWSROOM RSS FEED")
    print("=" * 70)

    print(
        f"Articles directory: {ARTICLES_DIR}"
    )

    print(
        f"Maximum RSS items: {MAX_ITEMS}"
    )

    articles = load_articles()

    print(
        f"Articles loaded: {len(articles)}"
    )

    trusted_images = 0
    excluded_images = 0
    no_images = 0

    for article in articles:

        image_status = article.get(
            "image_rights",
            "NONE"
        )

        if image_status == "TRUSTED":
            trusted_images += 1

        elif image_status == "UNKNOWN_EXTERNAL":
            excluded_images += 1

        else:
            no_images += 1

        print(
            f"- {article['title']}"
        )

        print(
            f"  Image: "
            f"{image_status}"
        )

        if image_status == "UNKNOWN_EXTERNAL":
            print(
                "  External image will NOT "
                "be syndicated."
            )

    rss = build_rss(
        articles
    )

    write_rss(
        rss
    )

    print()
    print("=" * 70)
    print("RSS GENERATION COMPLETE")
    print("=" * 70)

    print(
        f"RSS file: {OUTPUT_FILE}"
    )

    print(
        f"Articles: {len(articles)}"
    )

    print(
        f"Trusted images included: "
        f"{trusted_images}"
    )

    print(
        f"Unknown external images excluded: "
        f"{excluded_images}"
    )

    print(
        f"Articles without images: "
        f"{no_images}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()
