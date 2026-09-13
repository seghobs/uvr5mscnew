import copy
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError
import lyrics_ai as ai


class LyricsAITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        patcher=patch.object(ai,'SETTINGS',Path(self.tmp.name)/'settings.json');patcher.start();self.addCleanup(patcher.stop)
        clip=patch.object(ai,'audio_clip',return_value=b'test-wav');clip.start();self.addCleanup(clip.stop)
        ai.save_settings('test-secret',True)
        self.rows=[{'start':1.,'end':2.,'text':'ŞARKI','words':[{'word':'ŞARKI','start':1.,'end':2.,'probability':.9}]}]

    def test_secret_not_in_public_settings_and_blank_preserves(self):
        self.assertNotIn('test-secret',json.dumps(ai.public_settings()))
        ai.save_settings(None,False)
        self.assertEqual(ai.settings()['api_key'],'test-secret')
        self.assertFalse(ai.public_settings()['enabled'])
        ai.save_settings('replacement',True)
        self.assertEqual(ai.settings()['api_key'],'replacement')

    def test_invalid_model_rows_never_accepted(self):
        for output in ('bad','[]','[{"index":0,"text":""}]','[{"index":1,"text":"ŞARKI"}]'):
            with self.subTest(output=output),patch.object(ai,'generate',return_value=output):
                with self.assertRaises(ValueError):ai.proposals(self.rows,'test-secret')

    def test_invalid_key_never_replaces_saved_key(self):
        with self.assertRaises(ValueError):ai.save_settings('bad\nheader-secret',True)
        self.assertEqual(ai.settings()['api_key'],'test-secret')

    def test_provider_error_does_not_expose_request_or_response(self):
        with patch.object(ai,'urlopen',side_effect=HTTPError('https://example.com','403','test-secret',{},None)):
            with self.assertRaises(ValueError) as caught:ai.generate('text','test-secret')
            self.assertNotIn('test-secret',str(caught.exception))

    def test_punctuation_keeps_every_timestamp(self):
        original=copy.deepcopy(self.rows)
        with patch.object(ai,'proposals',return_value={0:'Şarkı!'}),patch('soundfile.info',return_value=SimpleNamespace(duration=5)):
            result,report=ai.correct_rows('fake.wav',self.rows,None)
        self.assertEqual(report['changed'],1)
        self.assertEqual(result[0]['words'][0]['start'],1.)
        self.assertEqual(result[0]['words'][0]['end'],2.)
        self.assertEqual(self.rows,original)

    def test_unheard_replacement_and_locked_row_preserved(self):
        with patch.object(ai,'proposals',return_value={0:'BAŞKA'}),patch('soundfile.info',return_value=SimpleNamespace(duration=5)),patch('karaoke_deep_words.deep_words',return_value={'candidates':[]}):
            result,report=ai.correct_rows('fake.wav',self.rows,None)
            self.assertEqual(result,self.rows);self.assertEqual(report['rejected'],1)
            self.rows[0]['locked']=True
            result,report=ai.correct_rows('fake.wav',self.rows,None)
            self.assertEqual(result,self.rows);self.assertEqual(report['changed'],0)

    def test_all_four_acoustic_passes_required_for_replacement(self):
        candidates=[{'run_id':i,'words':[{'word':'BAŞKA','start':1.1,'end':1.8,'probability':.95}]} for i in range(4)]
        with patch.object(ai,'proposals',return_value={0:'Başka'}),patch('soundfile.info',return_value=SimpleNamespace(duration=5)),patch('karaoke_deep_words.deep_words',return_value={'candidates':candidates}):
            result,report=ai.correct_rows('fake.wav',self.rows,None)
        self.assertEqual(report['changed'],1)
        self.assertEqual(result[0]['text'],'Başka')
        self.assertEqual(result[0]['words'][0]['start'],1.1)


if __name__=='__main__':unittest.main()
