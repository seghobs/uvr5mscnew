import unittest
import tempfile
import hashlib
from pathlib import Path
from unittest.mock import patch
import numpy as np
from tools.atlas_new_mix_screen import proposed_spectra,reference_leakage,choose_confirmation_manifest


class NewMixTests(unittest.TestCase):
    def test_holdout_selection_excludes_only_silent_references_without_scoring_candidates(self):
        from tools import atlas_extended as e,atlas_benchmark as b
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'references').mkdir();(root/'dataset/train').mkdir(parents=True)
            files=[root/'dataset/train'/f'Track{i}.stem.mp4' for i in range(9)]
            for file in files:file.touch()
            silent=min(files,key=lambda file:hashlib.sha256(('atlas-sdr-20261010:'+file.name).encode()).hexdigest()).name
            def reference(track):
                folder=root/'references'/track['id'];folder.mkdir()
                vocal=np.zeros((8,2)) if Path(track['file']).name==silent else np.ones((8,2))
                inst=np.full((8,2),2.)
                np.savez(folder/'reference.npz',source=vocal+inst,vocal=vocal,instrumental=inst)
                return folder
            with patch.object(e,'WORK',root),patch.object(b,'WORK',root),patch.object(e,'prepare_reference',side_effect=reference),patch('tools.atlas_new_mix_screen.score',side_effect=AssertionError('No candidate scoring during selection')):
                manifest=choose_confirmation_manifest(root/'confirmation')
            self.assertEqual(len(manifest['tracks']),8)
            self.assertEqual(len(manifest['excluded_silent_references']),1)
            self.assertEqual(Path(manifest['excluded_silent_references'][0]['track']['file']).name,silent)

    def test_crosstalk_measure_detects_opposite_stem_and_handles_reference_correlation(self):
        rng=np.random.default_rng(91)
        vocal=rng.normal(size=(8192,2));inst=.2*vocal+rng.normal(size=vocal.shape)
        ref={'vocal':vocal,'instrumental':inst,'source':vocal+inst}
        clean=reference_leakage(ref,vocal)
        contaminated=reference_leakage(ref,vocal+.1*inst)
        self.assertLess(clean['vocal'],1e-20)
        self.assertLess(clean['instrumental'],1e-20)
        self.assertAlmostEqual(contaminated['vocal'],.01*float(np.sum(inst**2)/np.sum(vocal**2)))
        self.assertLess(contaminated['instrumental'],1e-20)

    def test_silent_audio_does_not_generate_content(self):
        center=np.zeros((2,7,9),dtype=complex)
        for value in proposed_spectra(center,np.stack([center]*4),center).values():
            self.assertTrue(np.isfinite(value).all())
            np.testing.assert_array_equal(value,center)

    def test_identical_experts_preserve_complex_phase_and_stereo(self):
        rng=np.random.default_rng(91)
        center=rng.normal(size=(2,7,9))+1j*rng.normal(size=(2,7,9))
        source=2*center
        for value in proposed_spectra(center,np.stack([center]*4),source).values():
            np.testing.assert_allclose(value,center,atol=1e-10)

    def test_energy_consistency_reconciles_independent_stems(self):
        vocal=np.full((2,3,4),2.+0j)
        instrumental=np.full_like(vocal,1.+0j)
        source=np.full_like(vocal,4.+0j)
        experts=np.stack([vocal,source-instrumental,vocal,vocal])
        result=proposed_spectra(vocal,experts,source)['energy_consistency']
        np.testing.assert_allclose(result,2.8)
        np.testing.assert_allclose(result+(source-result),source)

if __name__=='__main__':unittest.main()
