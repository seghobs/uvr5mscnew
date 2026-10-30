from pathlib import Path
import tempfile
import unittest

import numpy as np
import soundfile as sf

from karaoke_source_recovery import verified_original


class SourceRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.root=Path(self.folder.name);self.sources=self.root/'sources';self.sources.mkdir()
        rng=np.random.default_rng(63);self.v=rng.normal(0,.05,(32000,2));self.i=rng.normal(0,.05,(32000,2))
        self.vocal=self.root/'v.wav';self.music=self.root/'i.wav'
        sf.write(self.vocal,self.v,8000,subtype='FLOAT');sf.write(self.music,self.i,8000,subtype='FLOAT')

    def source(self,name,audio):
        path=self.sources/name;sf.write(path,audio,8000,subtype='FLOAT');return path

    def test_finds_complete_sum_without_any_title_or_provenance(self):
        right=self.source('unrelated-name.wav',self.v+self.i)
        self.source('song-title.wav',self.v-self.i)
        self.assertEqual(verified_original(self.vocal,self.music,[self.sources]),right)

    def test_matching_preview_windows_do_not_hide_an_edit_elsewhere(self):
        changed=self.v+self.i;changed[:300]+=.1
        self.source('edited.wav',changed)
        self.assertIsNone(verified_original(self.vocal,self.music,[self.sources]))

    def test_equal_duration_shifted_version_is_rejected(self):
        self.source('shifted.wav',np.roll(self.v+self.i,400,axis=0))
        self.assertIsNone(verified_original(self.vocal,self.music,[self.sources]))

    def test_small_local_edit_cannot_hide_in_whole_recording_average(self):
        changed=self.v+self.i;changed[200,0]+=.002
        self.source('subtle-local-edit.wav',changed)
        self.assertIsNone(verified_original(self.vocal,self.music,[self.sources]))

    def test_identical_decoded_copies_are_one_time_base(self):
        self.source('a.wav',self.v+self.i);self.source('b.wav',self.v+self.i)
        self.assertEqual(verified_original(self.vocal,self.music,[self.sources]).name,'a.wav')

    def test_missing_stem_and_silent_sum_never_guess_a_source(self):
        self.source('silent.wav',np.zeros_like(self.v))
        self.assertIsNone(verified_original(self.vocal,None,[self.sources]))
        sf.write(self.vocal,np.zeros_like(self.v),8000);sf.write(self.music,np.zeros_like(self.i),8000)
        self.assertIsNone(verified_original(self.vocal,self.music,[self.sources]))
