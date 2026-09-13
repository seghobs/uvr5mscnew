"""Public provider endpoints and the official Musixmatch API."""
import asyncio
import os
import re
from urllib.parse import quote, urlencode, urlsplit, urljoin

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException, Query, Request
from typing import Literal

Provider = Literal["lyricstranslate", "lrclib", "lyricfind", "musixmatch", "genius"]
NAMES = ("lyricstranslate", "lrclib", "lyricfind", "musixmatch", "genius")
router = APIRouter()


def genius_url(url):
    try:
        p = urlsplit(url)
        valid = p.scheme == 'https' and p.hostname in ('genius.com', 'www.genius.com') and p.port in (None, 443) and not p.username and not p.password
    except ValueError:
        valid = False
    if not valid:
        raise HTTPException(422, "HTTPS Genius şarkı bağlantısı gerekli.")
    return url


def parse_genius(html):
    soup = BeautifulSoup(html, 'html.parser')
    containers = soup.select('[data-lyrics-container="true"]')
    if not containers:
        raise ProviderError('not_found', 'Genius söz bölümü bulunamadı.')
    parts = []
    for container in containers:
        for unwanted in container.select('[data-exclude-from-selection="true"], script, style, button'):
            unwanted.decompose()
        for br in container.select('br'):
            br.replace_with('\n')
        # Inline annotation links remain part of the same lyric line.
        text = container.get_text().replace('\xa0', ' ')
        text = '\n'.join(line.strip() for line in text.splitlines()).strip()
        if text:
            parts.append(text)
    if not parts:
        raise ProviderError('not_found', 'Genius söz bölümü boş.')
    return '\n\n'.join(parts)


async def genius_lyrics(client, url):
    url = genius_url(url)
    try:
        for _ in range(5):
            r = await client.get(url, timeout=15, follow_redirects=False)
            if r.status_code in (301, 302, 303, 307, 308):
                if not r.headers.get('location'):
                    raise ProviderError('upstream_error', 'Geçersiz yönlendirme.')
                url = genius_url(urljoin(url, r.headers['location']))
                continue
            if r.status_code in (401, 403):
                raise ProviderError('access_denied', 'Genius isteği engelledi.')
            if r.status_code == 429:
                raise ProviderError('rate_limited', 'Genius istek sınırına ulaşıldı.')
            if r.status_code == 404:
                raise ProviderError('not_found', 'Genius şarkısı bulunamadı.')
            r.raise_for_status()
            return parse_genius(r.text), {'source_url': url, 'completeness': 'unknown'}
        raise ProviderError('upstream_error', 'Çok fazla yönlendirme.')
    except httpx.TimeoutException:
        raise ProviderError('timeout', 'Genius zamanında yanıt vermedi.') from None
    except httpx.HTTPError:
        raise ProviderError('upstream_error', 'Genius sayfası alınamadı.') from None


class ProviderError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


async def get_json(client, url, params=None):
    try:
        response = await client.get(url, params=params, timeout=15, follow_redirects=False,
                                    headers={"Accept": "application/json"})
        if response.status_code in (401, 403):
            raise ProviderError("access_denied", "Kaynak erişim yetkisi istiyor veya isteği engelledi.")
        if response.status_code == 429:
            raise ProviderError("rate_limited", "Kaynağın istek sınırına ulaşıldı.")
        if response.status_code == 404:
            raise ProviderError("not_found", "Kayıt bulunamadı.")
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException:
        raise ProviderError("timeout", "Kaynak zamanında yanıt vermedi.") from None
    except (httpx.HTTPError, ValueError):
        # Never expose request URLs: official APIs may include credentials.
        raise ProviderError("upstream_error", "Kaynak geçerli bir JSON yanıtı döndürmedi.") from None


async def mx(client, method, params):
    key = os.environ.get("MUSIXMATCH_API_KEY", "").strip()
    if not key:
        raise ProviderError("not_configured", "MUSIXMATCH_API_KEY yapılandırılmalı.")
    d = await get_json(client, f"https://api.musixmatch.com/ws/1.1/{method}",
                       {**params, "apikey": key, "format": "json"})
    code = d["message"]["header"]["status_code"]
    if code != 200:
        status = {401: "access_denied", 402: "quota_exceeded", 403: "access_denied", 404: "not_found", 429: "rate_limited"}.get(code, "upstream_error")
        raise ProviderError(status, f"Musixmatch API durum kodu: {code}.")
    return d["message"]["body"], d["message"]["header"]


def item(source, identifier, title, artist, source_url, **extra):
    return {"source": source, "id": str(identifier), "title": title, "artist": artist,
            "source_url": source_url,
            "lyrics_url": f"/providers/{source}/lyrics?{urlencode({'id': identifier})}", **extra}


async def search_one(request, source, q, artist, page, limit, territory):
    client = request.app.state.client
    if source == 'genius':
        # The public multi-search endpoint accepts per_page only from 1 to 5.
        genius_limit = min(limit, 5)
        d = await get_json(client, 'https://genius.com/api/search/multi',
                           {'q': ' '.join(filter(None, (artist, q))), 'page': page + 1, 'per_page': genius_limit})
        if d['meta']['status'] != 200:
            raise ProviderError('upstream_error', 'Genius aramayı kabul etmedi.')
        results, seen = [], set()
        for section in d['response']['sections']:
            if section['type'] != 'song':
                continue
            for hit in section['hits']:
                if hit.get('type') != 'song':
                    continue
                t = hit['result']
                url = genius_url(t['url'])
                if url not in seen:
                    seen.add(url)
                    results.append(item(source, url, t['title'], t['primary_artist']['name'], url,
                                        song_id=t['id'], lyrics_state=t.get('lyrics_state')))
        return results, {'page': page, 'has_next': None, 'page_size': genius_limit,
                         'note': 'Kaynak kesin sonraki sayfa bilgisi vermiyor; sanatçı ve başlık ortak sorguda aranır.'}
    if source == "lyricstranslate":
        # Injected by main.py to keep the existing parser and URL restrictions.
        data = await request.app.state.lt_search(request, q=q, artist=artist,
                                                language_id=[], page=page, sort="relevance")
        results = [item(source, t['url'], t['title'], t['artist'], t['url'], language=t['language']) for t in data['results']]
        return results, {"page": page, "has_next": data['has_next'], "next_page": data['next_page'],
                         "page_size": "source_defined"}
    if source == "lrclib":
        params = {"track_name": q, "artist_name": artist} if artist and q else {"q": q or artist}
        rows = await get_json(client, "https://lrclib.net/api/search", params)
        if not isinstance(rows, list):
            raise ValueError("invalid schema")
        # LRCLIB does not expose server-side pagination; do not invent page params.
        selected = rows[page * limit:(page + 1) * limit]
        results = [item(source, t['id'], t['trackName'], t['artistName'], f"https://lrclib.net/api/get/{t['id']}",
                        album=t.get('albumName'), duration=t.get('duration'), instrumental=t.get('instrumental', False),
                        has_plain_lyrics=bool(t.get('plainLyrics')), has_synced_lyrics=bool(t.get('syncedLyrics'))) for t in selected]
        return results, {"page": page, "has_next": (page + 1) * limit < len(rows), "pagination": "local_slice",
                         "returned_by_source": len(rows), "catalog_total": None}
    if source == "lyricfind":
        params = {"reqtype": "default", "territory": territory, "searchtype": "track", "output": "json",
                  "useragent": "OriginalLyricsBot/1.0", "limit": limit, "offset": page * limit}
        if q:
            params["track"] = q
        if artist:
            params["artist"] = artist
        d = await get_json(client, "https://lyrics.lyricfind.com/api/v1/search", params)
        if d['response']['code'] != 100:
            raise ProviderError("upstream_error", "LyricFind arama isteğini kabul etmedi.")
        results = [item(source, t['lfid'], t['title'], (t.get('artist') or {}).get('name'),
                        f"https://lyrics.lyricfind.com/lyrics/{quote(t['slug'], safe='')}",
                        viewable=t.get('viewable'), lyrics_access="authorization_required") for t in d.get('tracks', [])]
        total = d.get('totalresults')
        return results, {"page": page, "has_next": (page + 1) * limit < total if isinstance(total, int) else None, "total": total}
    body, header = await mx(client, "track.search", {"q_track": q, "q_artist": artist,
                                                    "f_has_lyrics": 1, "page": page + 1, "page_size": limit})
    results = []
    for row in body['track_list']:
        t = row['track']
        results.append(item(source, t['track_id'], t['track_name'], t['artist_name'], t.get('track_share_url'),
                            album=t.get('album_name'), has_lyrics=bool(t.get('has_lyrics'))))
    total = header.get('available')
    return results, {"page": page, "has_next": (page + 1) * limit < total if isinstance(total, int) else None, "total": total}


async def guarded_search(request, source, q, artist, page, limit, territory):
    try:
        results, pagination = await asyncio.wait_for(search_one(request, source, q, artist, page, limit, territory), timeout=22)
        return {"source": source, "status": "ok", "count": len(results), "results": results, "pagination": pagination}
    except asyncio.TimeoutError:
        error = ProviderError("timeout", "Kaynak zamanında yanıt vermedi.")
    except ProviderError as exc:
        error = exc
    except HTTPException as exc:
        error = ProviderError("upstream_error", str(exc.detail))
    except (KeyError, TypeError, ValueError, AttributeError):
        error = ProviderError("invalid_response", "Kaynak yanıt yapısı değişmiş.")
    return {"source": source, "status": error.status, "error": error.message, "count": 0, "results": []}


@router.get("/search/all")
async def search_all(request: Request, q: str = Query(default="", max_length=128),
                     artist: str = Query(default="", max_length=128),
                     page: int = Query(default=0, ge=0, le=1000),
                     limit: int = Query(default=20, ge=1, le=50),
                     territory: str = Query(default="TR", pattern="^[A-Z]{2}$")):
    """Tüm kaynakları eşzamanlı arar; sonuçları kaynağa göre ayrı gruplar."""
    q, artist = q.strip(), artist.strip()
    if not q and not artist:
        raise HTTPException(422, "Arama metni veya sanatçı belirtin.")
    groups = await asyncio.gather(*(guarded_search(request, s, q, artist, page, limit, territory) for s in NAMES))
    return {"query": q, "artist": artist, "partial": any(g['status'] != 'ok' for g in groups),
            "sources": {g['source']: g for g in groups}}


@router.get("/providers")
async def provider_status():
    return {"sources": [
        {"source": "lyricstranslate", "search": "available", "lyrics": "available"},
        {"source": "lrclib", "search": "available", "lyrics": "available"},
        {"source": "genius", "search": "available", "lyrics": "available", "api_key_required": False,
         "note": "Halka açık web uç noktası ve HTML; kaynak erişimi sonradan engelleyebilir."},
        {"source": "lyricfind", "search": "available", "lyrics": "authorization_required",
         "note": "Halka açık söz API'si canlı denemede 401 verdi; lisanslı entegrasyon belgesi/erişimi gerekiyor."},
        {"source": "musixmatch", "search": "configured" if os.environ.get('MUSIXMATCH_API_KEY', '').strip() else "not_configured",
         "lyrics": "plan_dependent", "note": "Anahtar tanımlı olması erişimin doğrulandığı anlamına gelmez."}
    ]}


async def read_lyrics(request, source, identifier, territory):
    client = request.app.state.client
    if source == 'genius':
        return await genius_lyrics(client, identifier)
    if source == 'lyricstranslate':
        text = await request.app.state.lt_lyrics(client, identifier)
        return text, {"source_url": identifier, "completeness": "unknown"}
    if source in ('lrclib', 'musixmatch') and not re.fullmatch(r'[1-9][0-9]{0,18}', identifier):
        raise HTTPException(422, "Pozitif sayısal kayıt kimliği gerekli.")
    if source == 'lrclib':
        d = await get_json(client, f"https://lrclib.net/api/get/{identifier}")
        return d.get('plainLyrics'), {"source_url": f"https://lrclib.net/api/get/{identifier}",
            "title": d['trackName'], "artist": d['artistName'], "synced_lyrics": d.get('syncedLyrics'),
            "instrumental": d.get('instrumental', False), "completeness": "unknown"}
    if source == 'lyricfind':
        if not re.fullmatch(r'[A-Za-z0-9:-]{1,80}', identifier):
            raise HTTPException(422, "Geçersiz LyricFind kimliği.")
        d = await get_json(client, 'https://lyrics.lyricfind.com/api/v1/lyric',
            {"territory": territory, "trackid": identifier, "reqtype": "default", "output": "json", "useragent": "OriginalLyricsBot/1.0"})
        if d['response']['code'] not in (100, 101):
            raise ProviderError("access_denied", "LyricFind söz gösterme yetkisi vermedi.")
        t = d['track']
        return t.get('lyrics'), {"title": t.get('title'), "copyright": t.get('copyright'), "completeness": "unknown"}
    body, _ = await mx(client, 'track.lyrics.get', {"track_id": identifier})
    t = body['lyrics']
    if t.get('restricted'):
        raise ProviderError("restricted", "Bu sözlerin gösterimi kaynak tarafından kısıtlanmış.")
    return t.get('lyrics_body'), {"copyright": t.get('lyrics_copyright'),
        "completeness": "unknown", "note": "Dönen metin API planına göre kısmi olabilir.",
        "tracking": {k: t.get(k) for k in ('backlink_url', 'pixel_tracking_url', 'script_tracking_url') if t.get(k)}}


@router.get("/providers/{source}/lyrics")
async def provider_lyrics(request: Request, source: Provider, id: str = Query(min_length=1, max_length=2048),
                          format: Literal['lines', 'text'] = 'lines',
                          territory: str = Query(default='TR', pattern='^[A-Z]{2}$')):
    try:
        text, metadata = await read_lyrics(request, source, id, territory)
        if text is not None and not isinstance(text, str):
            raise ValueError('invalid lyrics')
        status = 'ok' if text else ('instrumental' if metadata.get('instrumental') else 'no_plain_lyrics')
        return {"source": source, "id": id, "status": status,
                "lyrics": text.splitlines() if text is not None and format == 'lines' else text, **metadata}
    except ProviderError as exc:
        code = {'not_found': 404, 'access_denied': 403, 'restricted': 403, 'timeout': 504,
                'not_configured': 503, 'rate_limited': 503, 'quota_exceeded': 503}.get(exc.status, 502)
        raise HTTPException(code, {"source": source, "status": exc.status, "message": exc.message}) from None
    except (KeyError, TypeError, ValueError, AttributeError):
        raise HTTPException(502, {"source": source, "status": "invalid_response"}) from None
