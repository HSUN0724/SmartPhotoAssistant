"""從指定的攝影網站取得文章卡片資料。"""

from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from time import monotonic
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


@dataclass(frozen=True)
class ArticleSource:
    name: str
    url: str
    article_path: str


SOURCES = (
    ArticleSource(
        name="鼎愛文化",
        url="https://www.dace.com.tw/blog/imaging/",
        article_path="/blog/imaging/",
    ),
    ArticleSource(
        name="OM Art Studio",
        url="https://www.omartstudio.com.tw/blog",
        article_path="/post/",
    ),
    ArticleSource(
        name="Canon 台灣",
        url="https://tw.canon/zh_TW/consumer",
        article_path="/zh_TW/consumer/",
    ),
)

# 保留舊版匯入名稱，避免其他程式引用時發生錯誤。
SOURCE_NAME = "鼎愛文化、OM Art Studio、Canon 台灣"
SOURCE_URL = SOURCES[0].url

FALLBACK_ARTICLES = [
    {
        "title": "攝影構圖怎麼拍？新手必學的 3 大基礎構圖技巧",
        "url": "https://www.dace.com.tw/blog/imaging/easy-composition/",
        "source": "鼎愛文化",
        "summary": "從三分法、延伸線與景深入門，建立清楚而有重點的畫面。",
        "image": "",
    },
    {
        "title": "手機攝影必學的 3 個觀念",
        "url": "https://www.dace.com.tw/blog/imaging/phone-photography/",
        "source": "鼎愛文化",
        "summary": "整理主題、清晰度與後製三個手機攝影的重要觀念。",
        "image": "",
    },
    {
        "title": "攝影師不藏私的人像攝影技巧",
        "url": "https://www.dace.com.tw/blog/imaging/portrait-photography/",
        "source": "鼎愛文化",
        "summary": "從被攝者互動、光線方向與故事感，整理自然人像的拍攝重點。",
        "image": "",
    },
    {
        "title": "從亂拍到拍出美感：培養攝影師之眼的第一步",
        "url": "https://www.omartstudio.com.tw/post/%E5%BE%9E%E3%80%8C%E4%BA%82%E6%8B%8D%E3%80%8D%E5%88%B0%E3%80%8C%E6%8B%8D%E5%87%BA%E7%BE%8E%E6%84%9F%E3%80%8D%EF%BC%9A%E5%9F%B9%E9%A4%8A%E6%94%9D%E5%BD%B1%E5%B8%AB%E4%B9%8B%E7%9C%BC%E7%9A%84%E7%AC%AC%E4%B8%80%E6%AD%A5",
        "source": "OM Art Studio",
        "summary": "從觀察光線、線條與畫面重心開始，練習以攝影師的方式觀看。",
        "image": "",
    },
    {
        "title": "街邊拍照也能很出片：手機人像與構圖技巧分享",
        "url": "https://www.omartstudio.com.tw/post/%E8%A1%97%E9%82%8A%E6%8B%8D%E7%85%A7%E4%B9%9F%E8%83%BD%E5%BE%88%E5%87%BA%E7%89%87%EF%BC%9A%E6%89%8B%E6%A9%9F%E4%BA%BA%E5%83%8F%E8%88%87%E6%A7%8B%E5%9C%96%E6%8A%80%E5%B7%A7%E5%88%86%E4%BA%AB",
        "source": "OM Art Studio",
        "summary": "利用街頭光影與構圖，把日常環境轉化為自然的人像攝影棚。",
        "image": "",
    },
    {
        "title": "用手機拍出情緒美食照：掌握引導線構圖",
        "url": "https://www.omartstudio.com.tw/post/%E7%94%A8%E6%89%8B%E6%A9%9F%E6%8B%8D%E5%87%BA%E5%90%B8%E7%9D%9B%E7%BE%8E%E9%A3%9F%E7%85%A7%EF%BC%9A%E6%8E%8C%E6%8F%A1%E3%80%8C%E5%BC%95%E5%B0%8E%E7%B7%9A%E6%A7%8B%E5%9C%96%E3%80%8D%E7%9A%84%E6%89%8B%E6%A9%9F%E6%94%9D%E5%BD%B1%E6%8A%80%E5%B7%A7%EF%BC%81",
        "source": "OM Art Studio",
        "summary": "利用引導線安排視覺焦點，讓手機美食照片更有重點與故事。",
        "image": "",
    },
    {
        "title": "EOS R5 Mark II 機內重曝技巧與拍攝體驗",
        "url": "https://tw.canon/zh_TW/consumer/20250519-EOS-R5-Mark-II-with-Maggie-Sung/article",
        "source": "Canon 台灣",
        "summary": "介紹機內多重曝光的設定方式、構圖思考與實際拍攝技巧。",
        "image": "",
    },
    {
        "title": "RF 長焦鏡頭下的鳥類及生態攝影之美",
        "url": "https://tw.canon/zh_TW/consumer/20241217-EOS-R6-Mark-II-and-RF100-500mm-F4-5-7-1L-IS-USM-by-dw/article",
        "source": "Canon 台灣",
        "summary": "分享長焦鏡頭、生態題材與高速快門等飛羽攝影實戰經驗。",
        "image": "",
    },
    {
        "title": "EOS R5 Mark II 飛羽攝影經驗分享",
        "url": "https://tw.canon/zh_TW/consumer/20250604-Birding-with-EOS-R5-Mark-II-Chou-and-Chens-Story/article",
        "source": "Canon 台灣",
        "summary": "從器材相容性、長焦鏡頭與高速快門，了解飛羽攝影的實戰設定。",
        "image": "",
    },
]

REQUEST_HEADERS = {
    "User-Agent": (
        "SmartPhotoAssistant/2.0 "
        "(student project; photography learning articles)"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.6",
}

CACHE_TTL_SECONDS = 15 * 60
_ARTICLE_CACHE = {"saved_at": 0.0, "articles": [], "using_fallback": False}


def _meta_content(soup, *, property_name=None, name=None):
    attrs = {"property": property_name} if property_name else {"name": name}
    tag = soup.find("meta", attrs=attrs)
    return tag.get("content", "").strip() if tag else ""


def _clean_text(text, max_length=150):
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= max_length:
        return cleaned
    return cleaned[: max_length - 1].rstrip() + "…"


def _is_article_url(source, url):
    parsed = urlparse(url)
    source_host = urlparse(source.url).netloc

    if parsed.netloc and parsed.netloc != source_host:
        return False
    if source.article_path not in parsed.path:
        return False

    # Canon 的 consumer 首頁與分類頁不是文章，文章網址以 /article 結尾。
    if source.name == "Canon 台灣" and not parsed.path.rstrip("/").endswith("/article"):
        return False

    return url.rstrip("/") != source.url.rstrip("/")


def _discover_article_urls(source, wanted):
    response = requests.get(
        source.url,
        headers=REQUEST_HEADERS,
        timeout=8,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    urls = []
    seen = set()
    for link in soup.find_all("a", href=True):
        url = urljoin(source.url, link["href"]).split("#", 1)[0]
        if not _is_article_url(source, url) or url in seen:
            continue
        seen.add(url)
        urls.append(url)
        if len(urls) >= wanted:
            break
    return urls


def _read_article(source, url):
    response = requests.get(
        url,
        headers=REQUEST_HEADERS,
        timeout=8,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    title = (
        _meta_content(soup, property_name="og:title")
        or (soup.find("h1").get_text(" ", strip=True) if soup.find("h1") else "")
        or (soup.title.get_text(" ", strip=True) if soup.title else "")
    )
    summary = (
        _meta_content(soup, property_name="og:description")
        or _meta_content(soup, name="description")
    )
    image = _meta_content(soup, property_name="og:image")

    if not summary:
        paragraph = soup.select_one("article p, main p, .post-content p, .entry-content p")
        summary = paragraph.get_text(" ", strip=True) if paragraph else ""

    if not image:
        for image_tag in soup.select("article img, main img, .post-content img, .entry-content img"):
            candidate = (
                image_tag.get("src")
                or image_tag.get("data-src")
                or image_tag.get("data-lazy-src")
                or ""
            ).strip()
            lowered = candidate.lower()
            if candidate and not lowered.startswith("data:") and "logo" not in lowered:
                image = candidate
                break

    title = _clean_text(title, 90)
    summary = _clean_text(summary, 150)
    if not title:
        raise ValueError("文章缺少標題")

    return {
        "title": title,
        "url": url,
        "source": source.name,
        "summary": summary or "點擊閱讀原文，了解更多攝影觀念與實拍技巧。",
        "image": urljoin(url, image) if image else "",
    }


def _scrape_source(source, wanted):
    urls = _discover_article_urls(source, wanted + 1)
    if not urls:
        raise ValueError("找不到可顯示的攝影文章")

    articles = []
    # 文章頁平行讀取，避免九篇文章逐頁等待。
    with ThreadPoolExecutor(max_workers=min(4, len(urls))) as executor:
        results = executor.map(lambda url: _safe_read_article(source, url), urls)
        for article in results:
            if article:
                articles.append(article)
            if len(articles) >= wanted:
                break

    if not articles:
        raise ValueError("文章頁缺少可顯示的內容")
    return articles


def _safe_read_article(source, url):
    try:
        return _read_article(source, url)
    except (requests.RequestException, ValueError):
        return None


def scrape_photography_articles(limit=9):
    """平均爬取三個指定來源；失敗的來源以同站備用文章補足。"""
    if limit <= 0:
        return [], False

    cache_age = monotonic() - _ARTICLE_CACHE["saved_at"]
    if _ARTICLE_CACHE["articles"] and cache_age < CACHE_TTL_SECONDS:
        return (
            [dict(article) for article in _ARTICLE_CACHE["articles"][:limit]],
            _ARTICLE_CACHE["using_fallback"],
        )

    per_source = max(1, (limit + len(SOURCES) - 1) // len(SOURCES))
    articles = []
    failed_sources = set()

    # 三個來源同步爬取；回傳順序仍依 SOURCES 保持一致。
    with ThreadPoolExecutor(max_workers=len(SOURCES)) as executor:
        results = executor.map(
            lambda source: _safe_scrape_source(source, per_source),
            SOURCES,
        )
        for source, source_articles in zip(SOURCES, results):
            if source_articles:
                articles.extend(source_articles)
            else:
                failed_sources.add(source.name)

    existing_urls = {article["url"] for article in articles}
    source_counts = {
        source.name: sum(article["source"] == source.name for article in articles)
        for source in SOURCES
    }
    for source in SOURCES:
        for fallback in FALLBACK_ARTICLES:
            if len(articles) >= limit or source_counts[source.name] >= per_source:
                break
            if (
                fallback["source"] == source.name
                and fallback["url"] not in existing_urls
            ):
                articles.append(dict(fallback))
                existing_urls.add(fallback["url"])
                source_counts[source.name] += 1

    articles = articles[:limit]
    using_fallback = bool(failed_sources)
    _ARTICLE_CACHE.update(
        saved_at=monotonic(),
        articles=[dict(article) for article in articles],
        using_fallback=using_fallback,
    )
    return articles, using_fallback


def _safe_scrape_source(source, wanted):
    try:
        return _scrape_source(source, wanted)
    except (requests.RequestException, ValueError):
        return []
