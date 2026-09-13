"""Read-only lyric search inside the existing UVR backend; no second server."""
import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
import httpx
from fastapi import APIRouter, HTTPException, Query
from . import providers, translate

router = APIRouter(prefix='/api/lyrics/catalog', tags=['Lyrics catalog'])


@asynccontextmanager
async def provider_request():
    async with httpx.AsyncClient(timeout=15, follow_redirects=False,
            headers={'User-Agent':'OriginalLyricsBot/1.0','Accept':'text/html'}) as client:
        yield SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
            client=client,lt_search=translate.search,lt_lyrics=translate.fetch_original)))


@router.get('/search')
async def search(q: str = Query('',max_length=128), artist: str = Query('',max_length=128),
                 page: int = Query(0,ge=0,le=1000)):
    q,artist=q.strip(),artist.strip()
    if not q and not artist:raise HTTPException(422,'Önce şarkı adı, söz veya sanatçı belirtin.')
    async with provider_request() as request:
        result=await providers.search_all(request,q,artist,page,10,'TR')
    return result


@router.get('/lyrics')
async def lyrics(source: providers.Provider, id: str = Query(min_length=1,max_length=2048)):
    async with provider_request() as request:
        try:
            result=await asyncio.wait_for(providers.provider_lyrics(request,source,id,'text','TR'),25)
        except asyncio.TimeoutError:
            raise HTTPException(504,'Kaynak zamanında yanıt vermedi. Başka sonuç seçebilir veya sözleri yapıştırabilirsiniz.') from None
    return result
