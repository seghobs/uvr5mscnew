import unittest
from types import SimpleNamespace as Span
from karaoke_syllables import syllable_ranges
from karaoke_ctc import words_from_spans


class SyllableTests(unittest.TestCase):
    def test_standalone_punctuation_does_not_block_or_shift_alignment(self):
        from unittest.mock import patch
        import numpy as np
        from karaoke_syllables import detect_syllables
        def align(path,segments,language,**options):
            self.assertEqual(segments[0]['text'],'OY EZO TUTMUYOR DİZİM EZO')
            return [{'words':[{'word':w['word'],'start':i+1.,'end':i+1.5,'probability':.9,'timing_source':'ctc','syllables':[]}
                             for i,w in enumerate(segments[0]['words'])]}]
        with patch('soundfile.info',return_value=Span(duration=20,samplerate=16000)),patch('soundfile.read',return_value=(np.ones(32000)*.1,16000)),patch('karaoke_ctc.refine_turkish',side_effect=align):
            result=detect_syllables('test.wav',{'start':0,'end':10,'text':'OY EZO ! TUTMUYOR , DİZİM EZO'})
        self.assertEqual([w['index'] for w in result['word_times']],[0,1,3,5,6])
        self.assertEqual(len(result['word_times']),5)

    def test_selected_range_is_not_expanded_and_last_word_is_retained(self):
        from unittest.mock import patch
        import numpy as np
        from karaoke_syllables import detect_syllables
        def align(path,segments,language,**options):
            self.assertEqual(options['context_padding'],0)
            self.assertEqual((segments[0]['start'],segments[0]['end']),(141.72489,145.944546))
            return [{'words':[{'word':'MASAL','start':144.,'end':145.8,'probability':.8,'timing_source':'ctc','syllables':[]}]}]
        with patch('soundfile.info',return_value=Span(duration=200,samplerate=16000)),patch('soundfile.read',return_value=(np.ones(32000)*.1,16000)),patch('karaoke_ctc.refine_turkish',side_effect=align):
            result=detect_syllables('test.wav',{'start':141.72489,'end':145.944546,'text':'MASAL'})
        self.assertEqual(result['word_times'][0]['end'],145.8)

    def test_silence_and_invalid_ranges(self):
        import tempfile
        from pathlib import Path
        import numpy as np
        import soundfile as sf
        from karaoke_syllables import detect_syllables
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'silent.wav'
            sf.write(path,np.zeros(32000),16000)
            self.assertEqual(detect_syllables(path,{'start':0,'end':1,'text':'MERHABA'})['passages'],[])
            for start,end in [(-1,1),(1,1),(0,3),(float('nan'),1)]:
                with self.assertRaises(ValueError):
                    detect_syllables(path,{'start':start,'end':end,'text':'MERHABA'})

    def test_turkish_groups(self):
        for text, expected in [('merhaba',['mer','ha','ba']),('söyle',['söy','le']),('yağmur',['yağ','mur']),('yüreğime',['yü','re','ği','me']),('aile',['a','i','le']),('türkçe',['türk','çe'])]:
            self.assertEqual([text[a:b] for a,b in syllable_ranges(text)], expected)
        self.assertEqual(syllable_ranges('mk'), [])

    def test_acoustic_spans_not_equal_slices(self):
        text='kara'; targets=[1,2,3,2]
        spans=[Span(token=t,start=s,end=e,score=.8) for t,s,e in zip(targets,[0,1,8,9],[1,6,9,12])]
        word=words_from_spans([{'word':text}],[text],spans,targets,.02,12,True)[0]
        self.assertEqual([s['text'] for s in word['syllables']],['ka','ra'])
        self.assertAlmostEqual(word['syllables'][0]['end'],12.12)
        self.assertAlmostEqual(word['syllables'][1]['start'],12.16)
        self.assertNotIn('syllables',words_from_spans([{'word':text}],[text],spans,targets,.02,12)[0])

if __name__=='__main__': unittest.main()
