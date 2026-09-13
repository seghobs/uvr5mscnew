import asyncio
from contextlib import asynccontextmanager
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from lyric_sources import api, providers, translate


class CatalogTests(unittest.TestCase):
    def call(self,path,handler,params=None):
        @asynccontextmanager
        async def fake_request():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                yield SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
                    client=client,lt_search=translate.search,lt_lyrics=translate.fetch_original)))
        app=FastAPI();app.include_router(api.router)
        with patch.object(api,'provider_request',fake_request),patch.dict(os.environ,{'MUSIXMATCH_API_KEY':''}),TestClient(app) as client:
            return client.get('/api/lyrics/catalog/'+path,params=params)

    def test_partial_results_preserve_available_sources(self):
        def handler(r):
            if r.url.host=='lrclib.net':return httpx.Response(200,json=[{'id':7,'trackName':'Nesrine','artistName':'Berdan Mardini'}])
            if r.url.host=='lyricstranslate.com':return httpx.Response(200,json={'html':'','has_content':False})
            return httpx.Response(403)
        result=self.call('search',handler,{'q':'Nesrine','artist':'Berdan Mardini'})
        self.assertEqual(result.status_code,200)
        data=result.json();self.assertTrue(data['partial'])
        self.assertEqual(len(data['sources']),5)
        self.assertEqual(data['sources']['lrclib']['results'][0]['title'],'Nesrine')
        self.assertEqual(data['sources']['musixmatch']['status'],'not_configured')

    def test_blank_search_does_not_contact_providers(self):
        def fail(r):self.fail('Unexpected network request')
        self.assertEqual(self.call('search',fail,{'q':'  '}).status_code,422)

    def test_lyrics_preserve_lines_and_stanzas(self):
        response=self.call('lyrics',lambda r:httpx.Response(200,json={
            'trackName':'Test','artistName':'Artist','plainLyrics':'Bir\nİki\n\nÜç'}),{'source':'lrclib','id':'7'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['lyrics'],'Bir\nİki\n\nÜç')

    def test_instrumental_returns_no_text(self):
        response=self.call('lyrics',lambda r:httpx.Response(200,json={
            'trackName':'Test','artistName':'Artist','instrumental':True,'plainLyrics':None}),{'source':'lrclib','id':'7'})
        self.assertEqual(response.json()['status'],'instrumental')

    def test_invalid_source_and_identifier(self):
        def fail(r):self.fail('Unexpected network request')
        for params in ({'source':'unknown','id':'7'},{'source':'lrclib','id':'../../settings'},
                       {'source':'genius','id':'http://127.0.0.1:8000/settings'},
                       {'source':'lyricstranslate','id':'https://example.com/lyrics'}):
            self.assertEqual(self.call('lyrics',fail,params).status_code,422)

    def test_redirect_cannot_leave_allowed_host(self):
        calls=[]
        def handler(r):
            calls.append(r.url)
            return httpx.Response(302,headers={'location':'http://127.0.0.1:8000/settings'})
        response=self.call('lyrics',handler,{'source':'genius','id':'https://genius.com/Test-lyrics'})
        self.assertEqual(response.status_code,422);self.assertEqual(len(calls),1)

    def test_denied_and_timeout_return_usable_errors(self):
        response=self.call('lyrics',lambda r:httpx.Response(401),{'source':'lyricfind','id':'002-964985'})
        self.assertEqual(response.status_code,403)
        def timeout(r):raise httpx.ReadTimeout('timeout',request=r)
        self.assertEqual(self.call('lyrics',timeout,{'source':'lrclib','id':'7'}).status_code,504)

    def test_genius_keeps_inline_words(self):
        self.assertEqual(providers.parse_genius('<div data-lyrics-container="true">Bir <a>güzel</a> satır<br>İki</div>'),'Bir güzel satır\nİki')

    def test_translate_extracts_original_only(self):
        html='<div id="original-lyrics"><div class="ltf"><div class="par">Bir<br>İki</div><div class="par">Üç</div></div></div><div class="translate-node-text">Translation</div>'
        self.assertEqual(translate.extract_original(html),'Bir\nİki\n\nÜç')

    def test_malformed_provider_response_is_isolated(self):
        response=self.call('search',lambda r:httpx.Response(200,json={'invalid':True}),{'q':'Test'})
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json()['partial'])


if __name__=='__main__':unittest.main()
