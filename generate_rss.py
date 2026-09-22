from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime, timezone
import json
import re
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

SITE_URL="https://nyonggodspower726-wq.github.io"
ARTICLES_DIR=Path("articles")
OUTPUT_FILE=Path("rss.xml")
MAX_ITEMS=25

MEDIA_PUBLIC_BASE_URL="https://newsfactory-production-2729.up.railway.app"

TRUSTED_SITE_IMAGE_PATHS=(
    "/media/generated/",
    "/generated/",
    "/media/images/",
    "/images/generated/",
)

# Only put domains here when you actually have syndication permission.
# Example:
# LICENSED_IMAGE_ORIGINS={
#     "https://example.com":"Example Media"
# }
LICENSED_IMAGE_ORIGINS={}

NS_ATOM="http://www.w3.org/2005/Atom"
NS_MEDIA="http://search.yahoo.com/mrss/"
NS_DC="http://purl.org/dc/elements/1.1/"
NS_DCTERMS="http://purl.org/dc/terms/"
NS_CONTENT="http://purl.org/rss/1.0/modules/content/"
NS_MI="http://schemas.ingestion.microsoft.com/common/"

ET.register_namespace("atom",NS_ATOM)
ET.register_namespace("media",NS_MEDIA)
ET.register_namespace("dc",NS_DC)
ET.register_namespace("dcterms",NS_DCTERMS)
ET.register_namespace("content",NS_CONTENT)
ET.register_namespace("mi",NS_MI)

def clean(value):
    if value is None:return ""
    if isinstance(value,(list,tuple)):
        value=" ".join(str(x) for x in value if x)
    return re.sub(r"\s+"," ",str(value)).strip()

def base_url(url):
    try:
        p=urlparse(clean(url))
        if p.scheme and p.netloc:
            return f"{p.scheme.lower()}://{p.netloc.lower()}"
    except Exception:
        pass
    return ""

SITE_BASE=base_url(SITE_URL)
MEDIA_BASE=base_url(MEDIA_PUBLIC_BASE_URL)

def meta(soup,*names):
    for name in names:
        tag=soup.find("meta",attrs={"property":name})
        if tag and tag.get("content"):return clean(tag["content"])
        tag=soup.find("meta",attrs={"name":name})
        if tag and tag.get("content"):return clean(tag["content"])
    return ""

def jsonld_objects(soup):
    result=[]
    for script in soup.find_all("script",attrs={"type":"application/ld+json"}):
        raw=script.string or script.get_text(strip=True)
        if not raw:continue
        try:
            data=json.loads(raw)
        except Exception:
            continue
        if isinstance(data,list):
            result.extend(data)
        elif isinstance(data,dict):
            graph=data.get("@graph")
            result.extend(graph if isinstance(graph,list) else [data])
    return result

def article_jsonld(soup):
    for obj in jsonld_objects(soup):
        if not isinstance(obj,dict):continue
        typ=obj.get("@type","")
        types=typ if isinstance(typ,list) else [typ]
        types=[str(x).lower() for x in types]
        if "newsarticle" in types or "article" in types:
            return obj
    return {}

def title_from_slug(path):
    value=path.stem.replace("-"," ")
    value=re.sub(r"\s+"," ",value).strip()
    return value.title()

def clean_title(title):
    title=clean(title)
    title=re.sub(r"\s*\|\s*AI News Factory\s*$","",title,flags=re.I)
    title=re.sub(r"\s*[-–—]\s*AI News Factory\s*$","",title,flags=re.I)
    return title.strip(" ,|-")

def get_image(obj,soup):
    image=obj.get("image","")
    if isinstance(image,list):
        for x in image:
            if isinstance(x,str) and x:return clean(x)
            if isinstance(x,dict):
                value=x.get("url") or x.get("contentUrl")
                if value:return clean(value)
    elif isinstance(image,dict):
        return clean(image.get("url") or image.get("contentUrl"))
    elif isinstance(image,str) and image:
        return clean(image)
    return meta(soup,"og:image","twitter:image")

def classify_image(url):
    url=clean(url)
    if not url:return None
    try:
        p=urlparse(url)
        if p.scheme not in {"http","https"}:return None
        origin=base_url(url)
        path=p.path.lower()
        if MEDIA_BASE and origin==MEDIA_BASE:
            return ("AI_GENERATED",url,"")
        if origin==SITE_BASE and any(path.startswith(x) for x in TRUSTED_SITE_IMAGE_PATHS):
            return ("OWNED",url,"")
        if origin in LICENSED_IMAGE_ORIGINS:
            return ("LICENSED",url,LICENSED_IMAGE_ORIGINS[origin])
    except Exception:
        pass
    return ("EXTERNAL_UNVERIFIED",url,"")

def extract_article(path):
    try:
        raw=path.read_text(encoding="utf-8")
    except Exception as exc:
        print(f"[ERROR] {path.name}: {exc}")
        return None

    soup=BeautifulSoup(raw,"html.parser")
    obj=article_jsonld(soup)

    title=clean_title(
        obj.get("headline")
        or meta(soup,"og:title","twitter:title")
        or (soup.title.get_text(" ",strip=True) if soup.title else "")
        or title_from_slug(path)
    )

    if not title:return None

    canonical=soup.find("link",rel="canonical")
    url=clean(canonical.get("href","")) if canonical else ""
    url=url or clean(obj.get("url"))
    url=url or f"{SITE_URL}/articles/{path.stem}.html"

    description=clean(
        obj.get("description")
        or meta(soup,"description","og:description","twitter:description")
    )

    author=obj.get("author","")
    if isinstance(author,dict):
        author=clean(author.get("name"))
    elif isinstance(author,list):
        names=[]
        for x in author:
            if isinstance(x,dict) and x.get("name"):
                names.append(clean(x["name"]))
            elif x:
                names.append(clean(x))
        author=", ".join(names)
    else:
        author=clean(author)

    author=author or meta(soup,"author","article:author") or "AI News Factory"

    category=clean(obj.get("articleSection"))
    category=category or meta(soup,"article:section","category") or "general"

    published=clean(obj.get("datePublished"))
    published=published or meta(soup,"article:published_time","datePublished")

    modified=clean(obj.get("dateModified"))
    modified=modified or meta(soup,"article:modified_time","dateModified") or published

    body=soup.find("article",class_="article-body")
    body=body or soup.find("article") or soup.find("main")
    if body is None:return None

    for tag in body.find_all(["script","style","nav","footer"]):
        tag.decompose()

    body_html="".join(str(x) for x in body.contents).strip()
    if not body_html:return None

    return {
        "title":title,
        "url":url,
        "description":description,
        "author":author,
        "category":category,
        "published":published,
        "modified":modified,
        "body":body_html,
        "image":classify_image(get_image(obj,soup))
    }

def parse_date(value):
    if not value:return None
    try:
        dt=datetime.fromisoformat(clean(value).replace("Z","+00:00"))
        if dt.tzinfo is None:
            dt=dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None

def rss_date(value):
    dt=parse_date(value) or datetime.now(timezone.utc)
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")

def add(parent,tag,value):
    element=ET.SubElement(parent,tag)
    element.text=clean(value)
    return element

def add_image(item,article):
    info=article.get("image")
    if not info:return

    status,url,licensor=info

    if status=="EXTERNAL_UNVERIFIED":
        print(f"[IMAGE] EXCLUDED: {url}")
        return

    media=ET.SubElement(item,f"{{{NS_MEDIA}}}content")
    media.set("url",url)
    media.set("medium","image")
    media.set("type","image/jpeg")

    rights=ET.SubElement(item,f"{{{NS_MI}}}HasSyndicationRights")

    if status in {"AI_GENERATED","OWNED"}:
        rights.text="true"
        print(f"[IMAGE] INCLUDED ({status}): {url}")
    elif status=="LICENSED":
        rights.text="false"
        if licensor:
            name=ET.SubElement(item,f"{{{NS_MI}}}ImageLicensorName")
            name.text=licensor
        print(f"[IMAGE] INCLUDED (LICENSED): {url}")

    description=ET.SubElement(item,f"{{{NS_MEDIA}}}description")
    description.text=article["title"]

def main():
    print("="*60)
    print("AI NEWS FACTORY RSS GENERATOR")
    print("="*60)

    files=list(ARTICLES_DIR.glob("*.html"))
    articles=[]

    print(f"Found {len(files)} article file(s).")

    for path in files:
        article=extract_article(path)
        if article:
            articles.append(article)
        else:
            print(f"[SKIP] {path.name}")

    articles.sort(
        key=lambda x:parse_date(x["published"]) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True
    )

    articles=articles[:MAX_ITEMS]

    rss=ET.Element("rss",{"version":"2.0"})
    channel=ET.SubElement(rss,"channel")

    add(channel,"title","AI News Factory")
    add(channel,"link",SITE_URL)
    add(channel,"description","Latest news from AI News Factory.")

    atom=ET.SubElement(channel,f"{{{NS_ATOM}}}link")
    atom.set("href",f"{SITE_URL}/rss.xml")
    atom.set("rel","self")
    atom.set("type","application/rss+xml")

    images=0

    for article in articles:
        item=ET.SubElement(channel,"item")

        add(item,"title",article["title"])
        add(item,"link",article["url"])

        guid=ET.SubElement(item,"guid")
        guid.set("isPermaLink","true")
        guid.text=article["url"]

        add(item,"pubDate",rss_date(article["published"]))

        if article["modified"]:
            add(item,f"{{{NS_DCTERMS}}}modified",article["modified"])

        add(item,"description",article["description"])
        add(item,f"{{{NS_DC}}}creator",article["author"])
        add(item,"category",article["category"])
        add(item,"category","AI-Assisted")
        add(item,f"{{{NS_CONTENT}}}encoded",article["body"])

        before=len(item)
        add_image(item,article)
        if len(item)>before:
            images+=1

    try:
        ET.indent(rss,space="    ")
    except AttributeError:
        pass

    ET.ElementTree(rss).write(
        OUTPUT_FILE,
        encoding="utf-8",
        xml_declaration=True
    )

    print("="*60)
    print("RSS GENERATION COMPLETE")
    print(f"Articles: {len(articles)}")
    print(f"Images included: {images}")
    print(f"Output: {OUTPUT_FILE}")
    print("="*60)

if __name__=="__main__":
    main()
