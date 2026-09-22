from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime, timezone
import html
import json
import re
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup


SITE_URL = "https://nyonggodspower726-wq.github.io"
ARTICLES_DIR = Path("articles")
OUTPUT_FILE = Path("rss.xml")

MAX_ITEMS = 25

# Your AI News Factory public media server.
MEDIA_PUBLIC_BASE_URL = (
    "https://newsfactory-production-2729.up.railway.app"
)


NS_ATOM = "http://www.w3.org/2005/Atom"
NS_CONTENT = "http://purl.org/rss/1.0/modules/content/"
NS_DC = "http://purl.org/dc/elements/1.1/"
NS_DCTERMS = "http://purl.org/dc/terms/"
NS_MEDIA = "http://search.yahoo.com/mrss/"
NS_MI = "http://schemas.microsoft.com/mi/"

ET.register_namespace("atom", NS_ATOM)
ET.register_namespace("content", NS_CONTENT)
ET.register_namespace("dc", NS_DC)
ET.register_namespace("dcterms", NS_DCTERMS)
ET.register_namespace("media", NS_MEDIA)
ET.register_namespace("mi", NS_MI)


# ---------------------------------------------------------------------
# TEXT HELPERS
# ---------------------------------------------------------------------

def clean_text(value):
    if not value:
        return ""

    value = html.unescape(str(value))
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def clean_title(title):
    title = clean_text(title)

    title = re.sub(
        r"\s*\|\s*AI News Factory\s*$",
        "",
        title,
        flags=re.IGNORECASE,
    )

    title = re.sub(
        r"\s*[-|–—]\s*AI News Factory\s*$",
        "",
        title,
        flags=re.IGNORECASE,
    )

    title = title.strip(" |,-–—")

    return title


def absolute_url(url):
    if not url:
        return ""

    url = url.strip()

    if url.startswith("//"):
        return "https:" + url

    if url.startswith("/"):
        return SITE_URL.rstrip("/") + url

    if url.startswith("http://") or url.startswith("https://"):
        return url

    return SITE_URL.rstrip("/") + "/" + url.lstrip("/")


# ---------------------------------------------------------------------
# DATE HELPERS
# ---------------------------------------------------------------------

def parse_datetime(value):
    if not value:
        return datetime.now(timezone.utc)

    value = str(value).strip()

    try:
        value = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(value)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc)

    except Exception:
        pass

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(value, fmt)

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            return dt.astimezone(timezone.utc)

        except Exception:
            continue

    return datetime.now(timezone.utc)


def rss_date(dt):
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")


# ---------------------------------------------------------------------
# HTML / META HELPERS
# ---------------------------------------------------------------------

def get_meta(soup, attrs):
    tag = soup.find("meta", attrs=attrs)

    if tag:
        return clean_text(
            tag.get("content", "")
        )

    return ""


def get_json_ld_objects(soup):
    objects = []

    for script in soup.find_all(
        "script",
        type="application/ld+json",
    ):
        raw = script.string or script.get_text()

        if not raw:
            continue

        try:
            data = json.loads(raw)

        except Exception:
            continue

        if isinstance(data, list):
            objects.extend(data)

        elif isinstance(data, dict):
            objects.append(data)

    return objects


def get_article_json_ld(soup):
    objects = get_json_ld_objects(soup)

    for obj in objects:
        if not isinstance(obj, dict):
            continue

        obj_type = obj.get("@type", "")

        if isinstance(obj_type, list):
            types = obj_type
        else:
            types = [obj_type]

        if any(
            str(t).lower()
            in {
                "article",
                "newsarticle",
                "reportagenewsarticle",
                "socialmediaposting",
            }
            for t in types
        ):
            return obj

    return {}


# ---------------------------------------------------------------------
# ARTICLE EXTRACTION
# ---------------------------------------------------------------------

def extract_title(soup):
    title = get_meta(
        soup,
        {"property": "og:title"},
    )

    if not title:
        title = get_meta(
            soup,
            {"name": "twitter:title"},
        )

    if not title and soup.title:
        title = soup.title.get_text(" ", strip=True)

    return clean_title(title)


def extract_description(soup, json_ld):
    description = get_meta(
        soup,
        {"property": "og:description"},
    )

    if not description:
        description = get_meta(
            soup,
            {"name": "description"},
        )

    if not description:
        description = get_meta(
            soup,
            {"name": "twitter:description"},
        )

    if not description:
        description = json_ld.get("description", "")

    return clean_text(description)


def extract_author(soup, json_ld):
    author = json_ld.get("author", "")

    if isinstance(author, dict):
        author = author.get("name", "")

    elif isinstance(author, list):
        names = []

        for item in author:
            if isinstance(item, dict):
                name = item.get("name", "")
            else:
                name = str(item)

            if name:
                names.append(name)

        author = ", ".join(names)

    if not author:
        author = get_meta(
            soup,
            {"name": "author"},
        )

    if not author:
        author = get_meta(
            soup,
            {"property": "article:author"},
        )

    return clean_text(author)


def extract_category(soup, json_ld):
    section = json_ld.get("articleSection", "")

    if isinstance(section, list):
        section = section[0] if section else ""

    if not section:
        section = get_meta(
            soup,
            {"property": "article:section"},
        )

    if not section:
        section = get_meta(
            soup,
            {"name": "category"},
        )

    return clean_text(section) or "General"


def extract_dates(soup, json_ld):
    published = (
        json_ld.get("datePublished")
        or get_meta(
            soup,
            {"property": "article:published_time"},
        )
        or get_meta(
            soup,
            {"name": "date"},
        )
    )

    modified = (
        json_ld.get("dateModified")
        or get_meta(
            soup,
            {"property": "article:modified_time"},
        )
    )

    published_dt = parse_datetime(published)
    modified_dt = parse_datetime(
        modified or published
    )

    return published_dt, modified_dt


def extract_article_body(soup, json_ld):
    article_body = json_ld.get("articleBody", "")

    if article_body:
        return clean_text(article_body)

    article = soup.find("article")

    if article:
        paragraphs = article.find_all("p")

        if paragraphs:
            text = "\n\n".join(
                clean_text(p.get_text(" ", strip=True))
                for p in paragraphs
                if clean_text(p.get_text(" ", strip=True))
            )

            if text:
                return text

    selectors = [
        ".article-content",
        ".article-body",
        ".post-content",
        ".entry-content",
        ".story-content",
        "main",
    ]

    for selector in selectors:
        container = soup.select_one(selector)

        if not container:
            continue

        paragraphs = container.find_all("p")

        if paragraphs:
            text = "\n\n".join(
                clean_text(p.get_text(" ", strip=True))
                for p in paragraphs
                if clean_text(p.get_text(" ", strip=True))
            )

            if text:
                return text

    paragraphs = soup.find_all("p")

    text = "\n\n".join(
        clean_text(p.get_text(" ", strip=True))
        for p in paragraphs
        if clean_text(p.get_text(" ", strip=True))
    )

    return text


# ---------------------------------------------------------------------
# IMAGE EXTRACTION
# ---------------------------------------------------------------------

def extract_image(soup, json_ld):
    image = json_ld.get("image", "")

    if isinstance(image, list):
        image = image[0] if image else ""

    if isinstance(image, dict):
        image = (
            image.get("url")
            or image.get("contentUrl")
            or ""
        )

    if not image:
        image = get_meta(
            soup,
            {"property": "og:image"},
        )

    if not image:
        image = get_meta(
            soup,
            {"name": "twitter:image"},
        )

    if not image:
        image = get_meta(
            soup,
            {"property": "twitter:image"},
        )

    if not image:
        image_tag = soup.find(
            "img",
            class_=re.compile(
                r"(hero|featured|article)",
                re.IGNORECASE,
            ),
        )

        if image_tag:
            image = (
                image_tag.get("src")
                or image_tag.get("data-src")
                or ""
            )

    return absolute_url(image)


# ---------------------------------------------------------------------
# IMAGE RIGHTS / TRUST
# ---------------------------------------------------------------------

def normalize_base_url(url):
    return url.rstrip("/").lower()


MEDIA_BASE = normalize_base_url(
    MEDIA_PUBLIC_BASE_URL
)

SITE_HOST = urlparse(
    SITE_URL
).netloc.lower()


def image_is_trusted(image_url):
    """
    Return True only when the image clearly belongs
    to our own generated media system.

    Trusted sources:
    1. Railway AI News Factory public media server.
    2. GitHub Pages newsroom generated-image paths.

    External publisher images are NOT trusted.
    """

    if not image_url:
        return False

    image_url = image_url.strip()

    parsed = urlparse(image_url)

    if parsed.scheme not in {
        "http",
        "https",
    }:
        return False

    normalized = normalize_base_url(
        f"{parsed.scheme}://{parsed.netloc}"
    )

    full_url = image_url.lower()

    # -------------------------------------------------------------
    # Railway AI News Factory media server
    # -------------------------------------------------------------

    if normalized == MEDIA_BASE:
        return True

    # -------------------------------------------------------------
    # Our own GitHub Pages generated image locations
    # -------------------------------------------------------------

    if parsed.netloc.lower() == SITE_HOST:

        trusted_paths = (
            "/media/generated/",
            "/generated/",
            "/media/images/",
            "/images/generated/",
        )

        if any(
            parsed.path.lower().startswith(path)
            for path in trusted_paths
        ):
            return True

    return False


def image_rights_status(image_url):
    if not image_url:
        return "NONE"

    if image_is_trusted(image_url):
        return "TRUSTED"

    return "UNKNOWN_EXTERNAL"


# ---------------------------------------------------------------------
# BUILD RSS ITEM
# ---------------------------------------------------------------------

def build_item(article_path):
    html_text = article_path.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    soup = BeautifulSoup(
        html_text,
        "html.parser",
    )

    json_ld = get_article_json_ld(soup)

    title = extract_title(
        soup
    )

    if not title:
        return None

    slug = article_path.stem

    article_url = (
        SITE_URL.rstrip("/")
        + "/articles/"
        + slug
        + ".html"
    )

    description = extract_description(
        soup,
        json_ld,
    )

    body = extract_article_body(
        soup,
        json_ld,
    )

    author = extract_author(
        soup,
        json_ld,
    )

    category = extract_category(
        soup,
        json_ld,
    )

    published_dt, modified_dt = extract_dates(
        soup,
        json_ld,
    )

    image_url = extract_image(
        soup,
        json_ld,
    )

    rights_status = image_rights_status(
        image_url
    )

    item = {
        "title": title,
        "url": article_url,
        "description": description,
        "body": body,
        "author": author or "AI News Factory",
        "category": category,
        "published_dt": published_dt,
        "modified_dt": modified_dt,
        "image_url": image_url,
        "image_rights": rights_status,
    }

    return item


# ---------------------------------------------------------------------
# RSS GENERATION
# ---------------------------------------------------------------------

def generate_rss():
    articles = []

    if not ARTICLES_DIR.exists():
        print(
            f"Articles directory not found: "
            f"{ARTICLES_DIR}"
        )
        return

    article_files = sorted(
        ARTICLES_DIR.glob("*.html"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    for article_path in article_files:

        try:
            article = build_item(
                article_path
            )

        except Exception as exc:
            print(
                f"ERROR parsing "
                f"{article_path.name}: {exc}"
            )
            continue

        if not article:
            continue

        if not article["body"]:
            print(
                f"SKIP no article body: "
                f"{article_path.name}"
            )
            continue

        articles.append(article)

    articles.sort(
        key=lambda article: article["published_dt"],
        reverse=True,
    )

    articles = articles[:MAX_ITEMS]

    rss = ET.Element(
        "rss",
        {
            "version": "2.0",
        },
    )

    channel = ET.SubElement(
        rss,
        "channel",
    )

    title = ET.SubElement(
        channel,
        "title",
    )

    title.text = "AI News Factory"

    link = ET.SubElement(
        channel,
        "link",
    )

    link.text = SITE_URL

    description = ET.SubElement(
        channel,
        "description",
    )

    description.text = (
        "Latest news published by AI News Factory."
    )

    language = ET.SubElement(
        channel,
        "language",
    )

    language.text = "en"

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
        },
    )

    for article in articles:

        item = ET.SubElement(
            channel,
            "item",
        )

        item_title = ET.SubElement(
            item,
            "title",
        )

        item_title.text = article["title"]

        item_link = ET.SubElement(
            item,
            "link",
        )

        item_link.text = article["url"]

        guid = ET.SubElement(
            item,
            "guid",
            {
                "isPermaLink": "true",
            },
        )

        guid.text = article["url"]

        pub_date = ET.SubElement(
            item,
            "pubDate",
        )

        pub_date.text = rss_date(
            article["published_dt"]
        )

        modified = ET.SubElement(
            item,
            f"{{{NS_DCTERMS}}}modified",
        )

        modified.text = (
            article["modified_dt"]
            .isoformat()
        )

        item_description = ET.SubElement(
            item,
            "description",
        )

        item_description.text = (
            article["description"]
            or article["body"][:500]
        )

        creator = ET.SubElement(
            item,
            f"{{{NS_DC}}}creator",
        )

        creator.text = article["author"]

        category = ET.SubElement(
            item,
            "category",
        )

        category.text = article["category"]

        # Explicitly identify AI-assisted content.
        ai_category = ET.SubElement(
            item,
            "category",
        )

        ai_category.text = "AI-Assisted"

        encoded = ET.SubElement(
            item,
            f"{{{NS_CONTENT}}}encoded",
        )

        encoded.text = (
            "<p>"
            + html.escape(
                article["body"]
            ).replace(
                "\n\n",
                "</p><p>",
            )
            + "</p>"
        )

        # ---------------------------------------------------------
        # IMAGE
        # ---------------------------------------------------------

        image_url = article["image_url"]
        rights = article["image_rights"]

        if rights == "TRUSTED":

            media = ET.SubElement(
                item,
                f"{{{NS_MEDIA}}}content",
                {
                    "url": image_url,
                    "medium": "image",
                },
            )

            ET.SubElement(
                media,
                f"{{{NS_MEDIA}}}title",
            ).text = article["title"]

            ET.SubElement(
                item,
                f"{{{NS_MI}}}HasSyndicationRights",
            ).text = "true"

            print(
                "IMAGE INCLUDED:",
                article["title"],
                "->",
                image_url,
            )

        elif rights == "UNKNOWN_EXTERNAL":

            print(
                "EXTERNAL IMAGE EXCLUDED:",
                article["title"],
                "->",
                image_url,
            )

        else:

            print(
                "NO IMAGE:",
                article["title"],
            )

    tree = ET.ElementTree(rss)

    ET.indent(
        tree,
        space="  ",
    )

    tree.write(
        OUTPUT_FILE,
        encoding="utf-8",
        xml_declaration=True,
    )

    print()
    print("=" * 60)
    print("RSS GENERATION COMPLETE")
    print("=" * 60)
    print(
        f"Articles included: {len(articles)}"
    )
    print(
        f"Output file: {OUTPUT_FILE}"
    )
    print(
        f"Media base URL: "
        f"{MEDIA_PUBLIC_BASE_URL}"
    )
    print("=" * 60)


if __name__ == "__main__":
    generate_rss()
