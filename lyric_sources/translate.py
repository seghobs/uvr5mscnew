"""Original LyricsTranslate parser and search from the local lyric project."""
import re
from urllib.parse import urljoin, urlsplit
from typing import Literal
import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException, Query, Request
ALLOWED_HOSTS = {"lyricstranslate.com", "www.lyricstranslate.com"}

def validate_url(url: str) -> str:
    try:
        parsed = urlsplit(url)
        valid = (
            parsed.scheme == "https"
            and parsed.hostname in ALLOWED_HOSTS
            and parsed.port in (None, 443)
            and not parsed.username
            and not parsed.password
        )
    except ValueError:
        valid = False
    if not valid:
        raise HTTPException(422, "Yalnızca HTTPS LyricsTranslate bağlantıları kabul edilir.")
    return url


def extract_original(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one("#original-lyrics")
    if root is None:
        root = soup.select_one(".song-node-text")
    if root is None:
        root = soup.select_one("#song-body")
    if root is None or "translate-node-text" in root.get("class", []):
        raise HTTPException(404, "Orijinal şarkı sözü bölümü bulunamadı.")
    content = root.select_one(".ltf")
    if content is None:
        raise HTTPException(404, "Orijinal sözlerin metin bölümü bulunamadı.")
    for unwanted in content.select(
        "script, style, sup, .footnote, .incontent-spacer, .emptyline, "
        ".translate-node-text, #translation-body"
    ):
        unwanted.decompose()

    def plain_text(node):
        for br in node.find_all("br"):
            br.replace_with("\n")
        # Preserve inline markup without splitting a lyric line into fragments.
        for block in reversed(node.find_all(["div", "p"])):
            block.append("\n")
        lines = [re.sub(r"[^\S\n]+", " ", line).strip()
                 for line in node.get_text().splitlines()]
        return "\n".join(line for line in lines if line)

    paragraphs = content.select(".par")
    lyrics = "\n\n".join(filter(None, (plain_text(p) for p in paragraphs))) if paragraphs else plain_text(content)
    if not lyrics:
        raise HTTPException(404, "Orijinal şarkı sözleri boş.")
    return lyrics


async def source_request(client: httpx.AsyncClient, url: str, method="GET", data=None) -> httpx.Response:
    url = validate_url(url)
    try:
        for _ in range(6):
            response = await client.request(method, url, data=data)
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("location")
                if not location:
                    raise HTTPException(502, "Kaynak site geçersiz yönlendirme döndürdü.")
                url = validate_url(urljoin(url, location))
                if response.status_code == 303 or (response.status_code in (301, 302) and method == "POST"):
                    method, data = "GET", None
                continue
            if response.status_code in (403, 429):
                raise HTTPException(503, "Kaynak site isteği engelledi veya istek sınırı uyguladı. Daha sonra deneyin.")
            if response.status_code == 404:
                raise HTTPException(404, "Kaynak sayfa bulunamadı.")
            response.raise_for_status()
            return response
        raise HTTPException(502, "Kaynak site çok fazla yönlendirme yaptı.")
    except httpx.TimeoutException as exc:
        raise HTTPException(504, "Kaynak site zamanında yanıt vermedi.") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Kaynak siteye erişilemedi.") from exc


async def fetch_original(client: httpx.AsyncClient, url: str) -> str:
    return extract_original((await source_request(client, url)).text)


def source_json(response):
    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(502, "Kaynak site beklenen JSON yanıtını döndürmedi.") from exc
    if not isinstance(payload, dict):
        raise HTTPException(502, "Kaynak yanıt biçimi değişmiş.")
    return payload


def text_of(node, selector):
    found = node.select_one(selector)
    return found.get_text(" ", strip=True) if found else None


def parse_search(html: str, page: int):
    soup = BeautifulSoup(html, "html.parser")
    items, seen = [], set()
    for row in soup.select(".s-search-songs .table__trow"):
        link = row.select_one(".block-1-table__title a.title-link[href]")
        if not link:
            raise HTTPException(502, "Arama sonuçlarının HTML yapısı değişmiş.")
        url = validate_url(urljoin("https://lyricstranslate.com", link["href"]))
        if url in seen:
            continue
        seen.add(url)
        nid = row.select_one("[data-song-nid], [nid]")
        song_id = (nid.get("data-song-nid") or nid.get("nid")) if nid else None
        items.append({"title": link.get_text(" ", strip=True),
                      "artist": text_of(row, ".block-1-table__author"),
                      "language": text_of(row, ".table__langs"),
                      "song_id": int(song_id) if song_id and song_id.isdigit() else None,
                      "url": url})
    has_next = soup.select_one("a.pages-comments__icon.-next[href]") is not None
    return {"results": items, "count": len(items), "page": page,
            "has_next": has_next, "next_page": page + 1 if has_next else None}


async def search(
    request: Request,
    q: str = Query(default="", max_length=128),
    artist: str = Query(default="", max_length=128),
    language_id: list[int] = Query(default=[], description="/languages listesindeki dil kimlikleri"),
    page: int = Query(default=0, ge=0, le=1000),
    sort: Literal["relevance", "popularity", "trending", "date", "oldest", "artist", "song"] = "relevance",
):
    """Şarkı başlığında veya sözlerinde arama; sanatçı/dil filtresi ve sayfalama."""
    if not q.strip() and not artist.strip() and not language_id:
        raise HTTPException(422, "Arama metni, sanatçı veya dil filtresi belirtin.")
    if any(i <= 0 for i in language_id) or len(language_id) > 20:
        raise HTTPException(422, "En fazla 20 pozitif dil kimliği belirtin.")
    url = f"https://lyricstranslate.com/en/ajax/lyricstranslatesearch/song/search?order={sort}&page={page}"
    data = {"ltsearchtextsong": q.strip(), "ltsearchtextartist": artist.strip()}
    if language_id:
        data["ltsearchlanguage[]"] = [str(i) for i in language_id]
    payload = source_json(await source_request(request.app.state.client, url, "POST", data))
    if not isinstance(payload.get("html"), str) or not isinstance(payload.get("has_content"), (bool, int)):
        raise HTTPException(502, "Kaynak arama yanıt biçimi değişmiş.")
    result = parse_search(payload["html"], page)
    if payload["has_content"] and not result["results"]:
        raise HTTPException(502, "Kaynak sonuçları ayrıştırılamadı.")
    return result

