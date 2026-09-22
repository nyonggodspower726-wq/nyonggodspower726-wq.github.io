from pathlib import Path
from datetime import datetime, timezone
import json
import re
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup


# ============================================================
# CONFIGURATION
# ============================================================

SITE_URL = "https://nyonggodspower726-wq.github.io"
ARTICLES_DIR = Path("articles")
OUTPUT_FILE = Path("rss.xml")

FEED_TITLE = "AI News Factory"
FEED_DESCRIPTION = "Latest news and analysis from AI News Factory."

MAX_ITEMS = 25


# ============================================================
# XML NAMESPACES
# ============================================================

ATOM_NS = "http://www.w3.org/2005/Atom"
MEDIA_NS = "http://search.yahoo.com/mrss/"
DC_NS = "http://purl.org/dc/elements/1.1/"
DCTERMS_NS = "http://purl.org/dc/terms/"
CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"
MI_NS = "http://schemas.ingestion.microsoft.com/common/"

ET.register_namespace("atom", ATOM_NS)
ET.register_namespace("media", MEDIA_NS)
ET.register_namespace("dc", DC_NS)
ET.register_namespace("dcterms", DCTERMS_NS)
ET.register_namespace("content", CONTENT_NS)
ET.register_namespace("mi", MI_NS)


# ============================================================
# HELPERS
# ============================================================

def clean_text(value):
    if not value:
        return ""

    value = BeautifulSoup(str(value), "html.parser").get_text(
        " ",
        strip=True
    )

    value = re.sub(r"\s+", " ", value)

    return value.strip()


def clean_title(title):
    """
    Cleans the article title without inventing missing words.
    Removes the site branding suffix and obvious trailing
    punctuation caused by the article generator.
    """

    title = clean_text(title)

    # Remove site branding added to HTML <title>
    title = re.sub(
        r"\s*\|\s*AI News Factory\s*$",
        "",
        title,
        flags=re.IGNORECASE
    )

    # Remove repeated trailing separators
    title = re.sub(r"\s*\|\s*$", "", title)

    # Remove an accidental trailing comma
    title = re.sub(r",\s*$", "", title)

    return title.strip()


def parse_datetime(value):
    """
    Converts common ISO date formats into a timezone-aware
    datetime object.
    """

    if not value:
        return None

    value = value.strip()

    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"

        dt = datetime.fromisoformat(value)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc)

    except Exception:
        return None


def rss_date(dt):
    """
    Converts datetime to RFC 822 format used by RSS.
    """

    if not dt:
        dt = datetime.now(timezone.utc)

    return dt.strftime("%a, %d %b %Y %H:%M:%S GMT")


def get_meta(soup, *names):
    """
    Finds meta content using name/property variants.
    """

    for name in names:
        tag = soup.find(
            "meta",
            attrs={"property": name}
        )

        if tag and tag.get("content"):
            return tag.get("content").strip()

        tag = soup.find(
            "meta",
            attrs={"name": name}
        )

        if tag and tag.get("content"):
            return tag.get("content").strip()

    return ""


def get_json_ld(soup):
    """
    Returns the first useful NewsArticle JSON-LD object.
    """

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

        candidates = []

        if isinstance(data, dict):
            if "@graph" in data and isinstance(
                data["@graph"],
                list
            ):
                candidates.extend(data["@graph"])
            else:
                candidates.append(data)

        elif isinstance(data, list):
            candidates.extend(data)

        for item in candidates:
            if not isinstance(item, dict):
                continue

            item_type = item.get("@type", "")

            if isinstance(item_type, list):
                item_type = " ".join(item_type)

            if (
                "NewsArticle" in str(item_type)
                or "Article" in str(item_type)
            ):
                return item

    return {}


def extract_article_body(soup):
    """
    Extracts the main article body as HTML.

    The preferred selector is:
    <article class="article-body">
    """

    article = soup.find(
        "article",
        class_=re.compile(r"\barticle-body\b")
    )

    if not article:
        article = soup.find("article")

    if not article:
        return ""

    # Remove elements that should not be syndicated
    for tag in article.find_all(
        ["script", "style", "noscript"]
    ):
        tag.decompose()

    return "".join(
        str(child)
        for child in article.contents
    ).strip()


def extract_image(soup, json_ld):
    """
    Finds the article image using OpenGraph, Twitter,
    JSON-LD, or the first large article image.
    """

    image = get_meta(
        soup,
        "og:image",
        "twitter:image"
    )

    if image:
        return image.strip()

    json_image = json_ld.get("image")

    if isinstance(json_image, str):
        return json_image.strip()

    if isinstance(json_image, list):
        for item in json_image:
            if isinstance(item, str) and item.strip():
                return item.strip()

            if isinstance(item, dict):
                url = item.get("url")

                if url:
                    return str(url).strip()

    if isinstance(json_image, dict):
        url = json_image.get("url")

        if url:
            return str(url).strip()

    article = soup.find("article")

    if article:
        img = article.find("img")

        if img and img.get("src"):
            return img.get("src").strip()

    return ""


def extract_author(json_ld, soup):
    """
    Extracts author from JSON-LD or common metadata.
    """

    author = json_ld.get("author")

    if isinstance(author, dict):
        name = author.get("name")

        if name:
            return clean_text(name)

    if isinstance(author, list):
        for item in author:
            if isinstance(item, dict):
                name = item.get("name")

                if name:
                    return clean_text(name)

            elif isinstance(item, str):
                if item.strip():
                    return clean_text(item)

    author = get_meta(
        soup,
        "author",
        "article:author"
    )

    if author:
        return clean_text(author)

    return "AI News Factory"


def extract_category(json_ld, soup):
    """
    Extracts article category/section.
    """

    category = json_ld.get("articleSection")

    if isinstance(category, list):
        if category:
            category = category[0]
        else:
            category = ""

    if category:
        return clean_text(category)

    category = get_meta(
        soup,
        "article:section",
        "category"
    )

    if category:
        return clean_text(category)

    category_tag = soup.find(
        class_=re.compile(
            r"\b(category|article-category|post-category)\b",
            re.IGNORECASE
        )
    )

    if category_tag:
        category = clean_text(
            category_tag.get_text(" ", strip=True)
        )

        if category:
            return category

    return "general"


# ============================================================
# ARTICLE PARSER
# ============================================================

def parse_article(path):
    """
    Parses one article HTML file.
    """

    try:
        html = path.read_text(
            encoding="utf-8"
        )
    except Exception as exc:
        print(
            f"WARNING: Could not read {path}: {exc}"
        )
        return None

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    json_ld = get_json_ld(soup)

    # --------------------------------------------------------
    # TITLE
    # --------------------------------------------------------

    title = ""

    h1 = soup.find("h1")

    if h1:
        title = clean_title(
            h1.get_text(" ", strip=True)
        )

    if not title:
        title = clean_title(
            get_meta(
                soup,
                "og:title",
                "twitter:title"
            )
        )

    if not title and soup.title:
        title = clean_title(
            soup.title.get_text(
                " ",
                strip=True
            )
        )

    if not title:
        title = clean_title(
            json_ld.get("headline", "")
        )

    # --------------------------------------------------------
    # DESCRIPTION
    # --------------------------------------------------------

    description = get_meta(
        soup,
        "description",
        "og:description",
        "twitter:description"
    )

    if not description:
        description = json_ld.get(
            "description",
            ""
        )

    description = clean_text(description)

    # Keep RSS description reasonably short
    if len(description) > 500:
        description = description[:497].rstrip() + "..."

    # --------------------------------------------------------
    # URL
    # --------------------------------------------------------

    canonical = soup.find(
        "link",
        rel="canonical"
    )

    if canonical and canonical.get("href"):
        url = canonical.get("href").strip()
    else:
        url = json_ld.get(
            "url",
            ""
        )

    if not url:
        url = (
            SITE_URL.rstrip("/")
            + "/"
            + path.as_posix()
        )

    # --------------------------------------------------------
    # IMAGE
    # --------------------------------------------------------

    image_url = extract_image(
        soup,
        json_ld
    )

    # --------------------------------------------------------
    # BODY
    # --------------------------------------------------------

    content_html = extract_article_body(
        soup
    )

    if not content_html:
        # Fallback to main element
        main = soup.find("main")

        if main:
            for tag in main.find_all(
                ["script", "style", "noscript"]
            ):
                tag.decompose()

            content_html = "".join(
                str(child)
                for child in main.contents
            ).strip()

    if not content_html:
        content_html = (
            f"<p>{description}</p>"
            if description
            else ""
        )

    # --------------------------------------------------------
    # DATE
    # --------------------------------------------------------

    published_at = (
        json_ld.get("datePublished")
        or get_meta(
            soup,
            "article:published_time",
            "datePublished"
        )
    )

    modified_at = (
        json_ld.get("dateModified")
        or get_meta(
            soup,
            "article:modified_time",
            "dateModified"
        )
        or published_at
    )

    published_dt = parse_datetime(
        published_at
    )

    modified_dt = parse_datetime(
        modified_at
    )

    if not published_dt:
        published_dt = datetime.fromtimestamp(
            path.stat().st_mtime,
            tz=timezone.utc
        )

    if not modified_dt:
        modified_dt = published_dt

    # --------------------------------------------------------
    # AUTHOR
    # --------------------------------------------------------

    author = extract_author(
        json_ld,
        soup
    )

    # --------------------------------------------------------
    # CATEGORY
    # --------------------------------------------------------

    category = extract_category(
        json_ld,
        soup
    )

    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    if not title:
        print(
            f"WARNING: Skipping {path} because "
            "no title was found."
        )
        return None

    if not url:
        print(
            f"WARNING: Skipping {path} because "
            "no URL was found."
        )
        return None

    return {
        "title": title,
        "url": url,
        "description": description,
        "content_html": content_html,
        "image_url": image_url,
        "published_dt": published_dt,
        "modified_dt": modified_dt,
        "author": author,
        "category": category,
    }


# ============================================================
# LOAD ARTICLES
# ============================================================

def load_articles():
    articles = []

    if not ARTICLES_DIR.exists():
        print(
            f"WARNING: {ARTICLES_DIR} does not exist."
        )
        return articles

    files = sorted(
        ARTICLES_DIR.glob("*.html")
    )

    print(
        f"Found {len(files)} article HTML file(s)."
    )

    for path in files:
        article = parse_article(path)

        if article:
            articles.append(article)

    articles.sort(
        key=lambda item: item["published_dt"],
        reverse=True
    )

    return articles[:MAX_ITEMS]


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

    ET.SubElement(
        channel,
        "title"
    ).text = FEED_TITLE

    ET.SubElement(
        channel,
        "link"
    ).text = SITE_URL

    ET.SubElement(
        channel,
        "description"
    ).text = FEED_DESCRIPTION

    ET.SubElement(
        channel,
        "language"
    ).text = "en"

    ET.SubElement(
        channel,
        "lastBuildDate"
    ).text = rss_date(
        datetime.now(timezone.utc)
    )

    # Atom self-reference
    ET.SubElement(
        channel,
        f"{{{ATOM_NS}}}link",
        {
            "href": f"{SITE_URL}/rss.xml",
            "rel": "self",
            "type": "application/rss+xml",
        }
    )

    # --------------------------------------------------------
    # ITEMS
    # --------------------------------------------------------

    for article in articles:
        item = ET.SubElement(
            channel,
            "item"
        )

        title = article["title"]
        url = article["url"]

        ET.SubElement(
            item,
            "guid",
            {
                "isPermaLink": "true"
            }
        ).text = url

        ET.SubElement(
            item,
            "title"
        ).text = title

        ET.SubElement(
            item,
            "link"
        ).text = url

        ET.SubElement(
            item,
            "pubDate"
        ).text = rss_date(
            article["published_dt"]
        )

        ET.SubElement(
            item,
            f"{{{DCTERMS_NS}}}modified"
        ).text = article[
            "modified_dt"
        ].isoformat()

        ET.SubElement(
            item,
            "description"
        ).text = article[
            "description"
        ]

        ET.SubElement(
            item,
            f"{{{DC_NS}}}creator"
        ).text = article[
            "author"
        ]

        # Normal topical category
        ET.SubElement(
            item,
            "category"
        ).text = article[
            "category"
        ]

        # MSN AI-assisted content indicator
        ET.SubElement(
            item,
            "category"
        ).text = "AI-Assisted"

        # Full article HTML
        ET.SubElement(
            item,
            f"{{{CONTENT_NS}}}encoded"
        ).text = article[
            "content_html"
        ]

        # Article image
        if article["image_url"]:
            media_content = ET.SubElement(
                item,
                f"{{{MEDIA_NS}}}content",
                {
                    "url": article["image_url"],
                    "medium": "image",
                }
            )

            # Try to preserve a sensible MIME type
            image_url = article[
                "image_url"
            ].lower()

            if ".png" in image_url:
                media_content.set(
                    "type",
                    "image/png"
                )
            elif ".webp" in image_url:
                media_content.set(
                    "type",
                    "image/webp"
                )
            else:
                media_content.set(
                    "type",
                    "image/jpeg"
                )

            ET.SubElement(
                media_content,
                f"{{{MEDIA_NS}}}description"
            ).text = title

    return rss


# ============================================================
# WRITE RSS
# ============================================================

def write_rss(root):
    tree = ET.ElementTree(root)

    ET.indent(
        tree,
        space="  "
    )

    tree.write(
        OUTPUT_FILE,
        encoding="utf-8",
        xml_declaration=True
    )


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("AI NEWS FACTORY RSS GENERATOR")
    print("=" * 60)

    articles = load_articles()

    print(
        f"Valid articles loaded: {len(articles)}"
    )

    if not articles:
        print(
            "No valid articles found."
        )
        return

    rss = build_rss(
        articles
    )

    write_rss(
        rss
    )

    print(
        f"RSS feed generated successfully: "
        f"{OUTPUT_FILE}"
    )

    print(
        f"Articles included: {len(articles)}"
    )

    print("=" * 60)


if __name__ == "__main__":
    main()
