import unittest
from types import SimpleNamespace as Span
from karaoke_syllables import syllable_ranges
from karaoke_ctc import words_from_spans


class SyllableTests(unittest.TestCase):
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
