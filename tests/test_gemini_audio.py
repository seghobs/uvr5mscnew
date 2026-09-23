import base64
import io
import json
import tempfile
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import lyrics_ai as ai


class GeminiAudioTests(unittest.TestCase):
    def test_audio_sent_to_requested_model_without_paid_search(self):
        response=io.BytesIO(json.dumps({'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'[]'}]}}]}).encode())
        with patch.object(ai,'urlopen',return_value=response) as network,patch.object(ai,'wait_for_request_slot') as throttle:
            self.assertEqual(ai.generate('transcribe','test-key',b'wave'),'[]')
        throttle.assert_called_once_with()
        request=network.call_args.args[0];body=json.loads(request.data)
        self.assertIn('/gemma-4-26b-a4b-it:generateContent',request.full_url)
        self.assertNotIn('test-key',request.full_url)
        self.assertNotIn('tools',body)
        self.assertEqual(base64.b64decode(body['contents'][0]['parts'][1]['inlineData']['data']),b'wave')

    def test_real_audio_conversion(self):
        import numpy as np
        import soundfile as sf
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'sample.wav'
            sf.write(path,np.zeros((48000*2,2)),48000)
            info=sf.info(io.BytesIO(ai.audio_clip(path,.5,1.5)))
            self.assertEqual((info.samplerate,info.channels,info.frames),(16000,1,16000))

    def test_whole_recording_chunks_have_absolute_times_and_no_word_claim(self):
        with patch('soundfile.info',return_value=SimpleNamespace(duration=65)),patch.object(ai,'audio_clip',return_value=b'wave') as clip,patch.object(ai,'generate',return_value='[{"start":1,"end":2,"text":"Bir söz"}]'):
            result=ai.transcribe_audio('sample.wav','test-key')
        self.assertEqual([row['start'] for row in result['segments']],[1,61])
        self.assertTrue(result['review_required'])
        self.assertEqual(result['segments'][0]['words'],[])
        self.assertEqual(clip.call_args_list[1].args,('sample.wav',60,65))

    def test_invalid_or_invented_times_are_rejected(self):
        for response in ('[{"start":0,"end":999,"text":"fake"}]','[{"start":2,"end":1,"text":"fake"}]','null'):
            with self.subTest(response=response),patch('soundfile.info',return_value=SimpleNamespace(duration=5)),patch.object(ai,'audio_clip',return_value=b'wave'),patch.object(ai,'generate',return_value=response):
                with self.assertRaises(ValueError):ai.transcribe_audio('sample.wav','test-key')


if __name__=='__main__':unittest.main()
