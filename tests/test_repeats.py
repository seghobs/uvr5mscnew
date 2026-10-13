import copy
import tempfile
import unittest
from pathlib import Path
import numpy as np
import soundfile as sf
from karaoke_repeats import expand_repeats

class RepeatTests(unittest.TestCase):
    def test_verified_copy_and_idempotence(self):
        rng=np.random.default_rng(15);phrase=rng.normal(0,.1,4000)
        wave=np.zeros(24000,dtype='float32');wave[2000:6000]=phrase;wave[14000:18000]=phrase
        row={'id':'verse-a','text':'GEL BANA','start':1.,'end':3.,'words':[
            {'word':'GEL','start':1.,'end':2.,'probability':.9,'timing_source':'ctc'},
            {'word':'BANA','start':2.,'end':3.,'probability':.9,'timing_source':'ctc'}]}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'test.wav';sf.write(path,wave,2000,subtype='FLOAT')
            result,report=expand_repeats([row],path)
            self.assertEqual(report['repeated_rows_added'],1)
            self.assertEqual([r['text'] for r in result],['GEL BANA','GEL BANA'])
            self.assertAlmostEqual(result[1]['start'],7,places=2)
            self.assertEqual(result[1]['repeat_source_id'],'verse-a')
            again,report=expand_repeats(result,path)
            self.assertEqual(report['repeated_rows_added'],0)
            self.assertEqual(result,again)
            protected=copy.deepcopy(row);protected['locked']=True
            self.assertEqual(expand_repeats([protected],path)[1]['repeated_rows_added'],0)
    def test_silence_never_adds_repeat(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'silent.wav';sf.write(path,np.zeros(20000),2000)
            row={'id':'x','text':'GEL BANA','start':1,'end':3,'words':[{'word':'GEL','probability':.9,'start':1,'end':2},{'word':'BANA','probability':.9,'start':2,'end':3}]}
            self.assertEqual(expand_repeats([row],path)[1]['repeated_rows_added'],0)
