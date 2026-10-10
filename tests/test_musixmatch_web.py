import asyncio
import json
import unittest
from types import SimpleNamespace
import httpx
from fastapi import HTTPException
from lyric_sources.musixmatch_web import parse_page,song_url,fetch_page,validate_url
from lyric_sources.providers import search_one,ProviderError


def page(body='Bir\nİki\n\nÜç'):
    data={'props':{'pageProps':{'data':{'trackInfo':{'data':{
        'track':{'name':'Gözleri Fettan Güzel','artistName':'Müslüm Gürses','isInstrumental':False},
        'lyrics':{'body':body,'copyright':'Test copyright'}}},
        'albumGet':{'data':{'lyrics':{'body':'Do not select another track'}}}}}}}
    return '<script id="__NEXT_DATA__" type="application/json">'+json.dumps(data)+'</script>'


class MusixmatchTests(unittest.TestCase):
    def test_unicode_url_and_exact_song_json_preserve_stanzas(self):
        url=song_url('Müslüm Gürses','Gözleri Fettan Güzel')
        self.assertIn('M%C3%BCsl%C3%BCm-G%C3%BCrses',url)
        text,metadata=parse_page(page(),url)
        self.assertEqual(text,'Bir\nİki\n\nÜç')
        self.assertEqual(metadata['artist'],'Müslüm Gürses')
        self.assertFalse(metadata['api_key_required'])

    def test_no_api_key_or_private_api_contacted(self):
        calls=[]
        def handler(request):
            calls.append(request.url)
            self.assertEqual(request.url.host,'www.musixmatch.com')
            self.assertNotIn('apikey',str(request.url))
            return httpx.Response(200,text=page())
        async def run():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                request=SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(client=client)))
                songs,pagination=await search_one(request,'musixmatch','Gözleri Fettan Güzel','Müslüm Gürses',0,10,'TR')
                self.assertEqual(songs[0]['artist'],'Müslüm Gürses')
                self.assertFalse(pagination['has_next'])
                text,_=await fetch_page(client,songs[0]['id'])
                self.assertEqual(text,'Bir\nİki\n\nÜç')
        asyncio.run(run());self.assertEqual(len(calls),2)

    def test_other_host_redirect_not_followed(self):
        async def run():
            calls=[]
            def handler(request):
                calls.append(request.url)
                return httpx.Response(302,headers={'location':'http://127.0.0.1:8000/models'})
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                with self.assertRaises(HTTPException):await fetch_page(client,song_url('Artist','Song'))
            self.assertEqual(len(calls),1)
        asyncio.run(run())

    def test_no_fallback_to_album_lyrics_or_malformed_json(self):
        with self.assertRaises(ProviderError):parse_page('<script id="__NEXT_DATA__">{"props":{}}</script>',song_url('Artist','Song'))
        for url in ['http://www.musixmatch.com/lyrics/A/B','https://www.musixmatch.com.evil/lyrics/A/B',
                    'https://www.musixmatch.com/lyrics/A/../B','https://www.musixmatch.com/lyrics/A/B?redirect=evil']:
            with self.assertRaises(HTTPException):validate_url(url)

    def test_blocked_page_does_not_claim_lyrics_success(self):
        async def run():
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(403))) as client:
                with self.assertRaises(ProviderError) as result:await fetch_page(client,song_url('Artist','Song'))
                self.assertEqual(result.exception.status,'access_denied')
        asyncio.run(run())
