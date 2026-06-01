import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import asyncio
from src.models import ScrapedContent
from src.config import MAX_SCRAPE_PAGES


async def _fetch_text(url: str, client: httpx.AsyncClient) -> str:
    try:
        resp = await client.get(url, timeout=15.0, follow_redirects=True)
        resp.raise_for_status()
        return resp.text
    except Exception:
        return ""


def _extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(separator=" ", strip=True)


def _extract_meta(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    meta = {}
    if tag := soup.find("title"):
        meta["title"] = tag.get_text(strip=True)
    if tag := soup.find("meta", attrs={"name": "description"}):
        meta["description"] = tag.get("content", "")
    if tag := soup.find("h1"):
        meta["h1"] = tag.get_text(strip=True)
    return meta


def _get_same_domain_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    base_domain = urlparse(base_url).netloc
    links = set()
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"])
        parsed = urlparse(href)
        if parsed.netloc == base_domain and parsed.scheme in ("http", "https"):
            links.add(href)
    return list(links)


async def scrape_website(url: str) -> ScrapedContent:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; MarketingAgent/1.0; +https://github.com/marketing-agent)"
    }
    async with httpx.AsyncClient(headers=headers, timeout=15.0) as client:
        html = await _fetch_text(url, client)
        if not html:
            return ScrapedContent()

        meta = _extract_meta(html)
        tagline = meta.get("h1") or meta.get("title", "")
        about_summary = _extract_text(html)[:2000]

        linked_urls = _get_same_domain_links(html, url)
        priority_keywords = ["about", "product", "service", "blog", "mission", "feature"]
        scored = sorted(
            linked_urls,
            key=lambda u: sum(
                1 for kw in priority_keywords if kw in urlparse(u).path.lower()
            ),
            reverse=True,
        )
        candidates = scored[: MAX_SCRAPE_PAGES - 1]

        pages_text = []
        for link in candidates:
            page_html = await _fetch_text(link, client)
            if page_html:
                pages_text.append(_extract_text(page_html))

    return ScrapedContent(
        tagline=tagline[:500] if tagline else None,
        about_summary=about_summary[:2000],
        products_services=[],
        blog_themes=[],
        tone_markers=[],
        value_propositions=[],
        raw_snippets=[about_summary[:2000]] + [p[:2000] for p in pages_text],
    )
