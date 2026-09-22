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

def normalize_base_url(url):
    if not url:return ""
    p=urlparse(url.strip())
    if not p.scheme or not p.netloc:return ""
    return f"{p.scheme.lower()}://{p.netloc.lower()}".rstrip("/")

MEDIA_BASE=normalize_base_url(MEDIA_PUBLIC_BASE_URL)
SITE_HOST=urlparse(SITE_URL).netloc.lower()

def image_origin(url):
    if not url:return ""
    try:
        p=urlparse(url.strip())
        if p.scheme not in {"http","https"}:return ""
        return normalize_base_url(f"{p.scheme}://{p.netloc}")
    except Exception:
        return ""

def classify_image(url):
    if not url:return {"status":"NONE","url":"","licensor":""}
    url=url.strip()
    p=urlparse(url)
    if p.scheme not in {"http","https"}:
        return {"status":"NONE","url":"","licensor":""}
    origin=image_origin(url)
    if MEDIA_BASE and origin==MEDIA_BASE:
        return {"status":"TRUSTED_AI","url":url,"licensor":""}
    if p.netloc.lower()==SITE_HOST:
        path=p.path.lower()
        if any(path.startswith(x) for x in TRUSTED_SITE_IMAGE_PATHS):
            return {"status":"TRUSTED_SITE","url":url,"licensor":""}
    if origin in LICENSED_IMAGE_ORIGINS:
        return {
            "status":"LICENSED",
            "url":url,
            "licensor":LICENSED_IMAGE_ORIGINS[origin]
        }
    return {"status":"UNKNOWN_EXTERNAL","url":"","licensor":""}

def clean_text(value):
    if value is None:return ""
    if isinstance(value,(list,tuple)):
        value=" ".join(str(x) for x in value if x)
    return re.sub(r"\s+"," ",str(value)).strip()

def clean_title(title):
    title=clean_text(title)
    title=re.sub(r"\s*\|\s*AI News Factory\s*$","",title,flags=re.I)
    title=re.sub(r"\s*[-–—]\s*AI News Factory\s*$","",title,flags=re.I)
    return title.strip(" ,|-")

def meta_content(soup,*names):
    for name in names:
        tag=soup.find("meta",attrs={"property":name})
        if tag and tag.get("content"):return clean_text(tag["content"])
        tag=soup.find("meta",attrs={"name":name})
        if tag and tag.get("content"):return clean_text(tag["content"])
    return ""

def load_json_ld(soup):
    objects=[]
    for script in soup.find_all("script",attrs={"type":"application/ld+json"}):
        raw=script.string or script.get_text(strip=True)
        if not raw:continue
        try:data=json.loads(raw)
        except Exception:continue
        if isinstance(data,list):objects.extend(data)
        elif isinstance(data,dict):
            graph=data.get("@graph")
            if isinstance(graph,list):objects.extend(graph)
            else:objects.append(data)
    return objects

def find_news_article_jsonld(soup):
    for obj in load_json_ld(soup):
        if not isinstance(obj,dict):continue
        obj_type=obj.get("@type","")
        types=[str(x).lower() for x in obj_type] if isinstance(obj_type,list) else [str(obj_type).lower()]
        if "newsarticle" in types or "article" in types:return obj
    return {}

def extract_article(path):
    try:raw=path.read_text(encoding="utf-8")
    except Exception as exc:
        print(f"[ERROR] {path}: {exc}")
        return None
    soup=BeautifulSoup(raw,"html.parser")
    jsonld=find_news_article_jsonld(soup)

    title=clean_text(
        jsonld.get("headline")
        or meta_content(soup,"og:title","twitter:title")
        or (soup.title.get_text(strip=True) if soup.title else "")
    )
    title=clean_title(title)
    if not title:return None

    canonical=soup.find("link",rel="canonical")
    url=clean_text(canonical.get("href","")) if canonical else ""
    url=url or clean_text(jsonld.get("url",""))
    url=url or f"{SITE_URL}/articles/{path.stem}.html"

    description=clean_text(
        jsonld.get("description")
        or meta_content(soup,"description","og:description","twitter:description")
    )

    author=""
    ja=jsonld.get("author")
    if isinstance(ja,dict):author=clean_text(ja.get("name"))
    elif isinstance(ja,list):
        names=[]
        for x in ja:
            if isinstance(x,dict) and x.get("name"):names.append(clean_text(x["name"]))
            elif x:names.append(clean_text(x))
        author=", ".join(names)
    elif ja:author=clean_text(ja)
    author=author or meta_content(soup,"author","article:author") or "AI News Factory"

    category=clean_text(jsonld.get("articleSection",""))
    category=category or meta_content(soup,"article:section","category") or "general"

    published=clean_text(jsonld.get("datePublished",""))
    published=published or meta_content(soup,"article:published_time","datePublished")

    modified=clean_text(jsonld.get("dateModified",""))
    modified=modified or meta_content(soup,"article:modified_time","dateModified") or published

    image=""
    ji=jsonld.get("image")
    if isinstance(ji,list):
        for x in ji:
            if isinstance(x,str):image=x;break
            if isinstance(x,dict):
                image=x.get("url") or x.get("contentUrl","")
                if image:break
    elif isinstance(ji,dict):
        image=ji.get("url") or ji.get("contentUrl","")
    elif isinstance(ji,str):
        image=ji
    image=clean_text(image or meta_content(soup,"og:image","twitter:image"))
    image_info=classify_image(image)

    body=soup.find("article",class_="article-body")
    body=body or soup.find("article") or soup.find("main")
    if body is None:return None
    for x in body.find_all(["script","style","nav","footer"]):x.decompose()
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
        "image":image_info
    }

def parse_date(value):
    if not value:return None
    try:
        dt=datetime.fromisoformat(value.strip().replace("Z","+00:00"))
        if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:return None

def rss_date(value):
    dt=parse_date(value) or datetime.now(timezone.utc)
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")

def add_text(parent,tag,value):
    e=ET.SubElement(parent,tag)
    e.text=clean_text(value)
    return e

def add_image_metadata(item,article):
    image=article.get("image",{})
    status=image.get("status")
    url=image.get("url")
    if status=="UNKNOWN_EXTERNAL":
        print(f"[IMAGE] EXCLUDED: {article.get('title')}")
        return
    if not url:return
    if status in {"TRUSTED_AI","TRUSTED_SITE"}:
        media=ET.SubElement(item,f"{{{NS_MEDIA}}}content")
        media.set("url",url)
        media.set("type","image/jpeg")
        media.set("medium","image")
        rights=ET.SubElement(item,f"{{{NS_MI}}}HasSyndicationRights")
        rights.text="true"
        desc=ET.SubElement(item,f"{{{NS_MEDIA}}}description")
        desc.text=article.get("title","News image")
        print(f"[IMAGE] INCLUDED ({status}): {url}")
        return
    if status=="LICENSED":
        media=ET.SubElement(item,f"{{{NS_MEDIA}}}content")
        media.set("url",url)
        media.set("type","image/jpeg")
        media.set("medium","image")
        rights=ET.SubElement(item,f"{{{NS_MI}}}HasSyndicationRights")
        rights.text="false"
        licensor=image.get("licensor","")
        if licensor:
            e=ET.SubElement(item,f"{{{NS_MI}}}ImageLicensorName")
            e.text=licensor
        print(f"[IMAGE] INCLUDED (licensed): {licensor}")

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
        key=lambda x:parse_date(x.get("published","")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True
    )
    articles=articles[:MAX_ITEMS]

    rss=ET.Element("rss",{"version":"2.0"})
    channel=ET.SubElement(rss,"channel")

    add_text(channel,"title","AI News Factory")
    add_text(channel,"link",SITE_URL)
    add_text(channel,"description","Latest news from AI News Factory.")

    atom=ET.SubElement(channel,f"{{{NS_ATOM}}}link")
    atom.set("href",f"{SITE_URL}/rss.xml")
    atom.set("rel","self")
    atom.set("type","application/rss+xml")

    included=0
    excluded=0

    for article in articles:
        item=ET.SubElement(channel,"item")
        url=article.get("url","")

        add_text(item,"title",article.get("title","Untitled"))
        add_text(item,"link",url)

        guid=ET.SubElement(item,"guid")
        guid.set("isPermaLink","true")
        guid.text=url

        add_text(item,"pubDate",rss_date(article.get("published","")))

        if article.get("modified"):
            add_text(item,f"{{{NS_DCTERMS}}}modified",article["modified"])

        add_text(item,"description",article.get("description",""))
        add_text(item,f"{{{NS_DC}}}creator",article.get("author","AI News Factory"))
        add_text(item,"category",article.get("category","general"))
        add_text(item,"category","AI-Assisted")
        add_text(item,f"{{{NS_CONTENT}}}encoded",article.get("body",""))

        before=len(item)
        add_image_metadata(item,article)
        after=len(item)

        if after>before:included+=1
        elif article.get("image",{}).get("status")=="UNKNOWN_EXTERNAL":excluded+=1

    try:ET.indent(rss,space="    ")
    except AttributeError:pass

    ET.ElementTree(rss).write(
        OUTPUT_FILE,
        encoding="utf-8",
        xml_declaration=True
    )

    print("="*60)
    print("RSS GENERATION COMPLETE")
    print(f"Articles: {len(articles)}")
    print(f"Images included: {included}")
    print(f"Images excluded: {excluded}")
    print(f"Output: {OUTPUT_FILE}")
    print("="*60)

if __name__=="__main__":
    main()
