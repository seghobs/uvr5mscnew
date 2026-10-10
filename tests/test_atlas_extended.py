import unittest
import numpy as np
from tools.atlas_extended import frequency_statistics, passes_expanded, content_statistics
import copy


class ExtendedBenchmarkTests(unittest.TestCase):
    def test_content_constraint_gradient_matches_finite_difference_for_both_stems(self):
        rng=np.random.default_rng(98)
        x=rng.normal(size=(3,2,7,9))+1j*rng.normal(size=(3,2,7,9))
        src=rng.normal(size=(2,7,9))+1j*rng.normal(size=(2,7,9))
        v=np.abs(src*.4);inst=np.abs(src*.6)
        basis=rng.uniform(size=(7,2));basis/=basis.sum(axis=1,keepdims=True)
        weights=np.full((3,2),1/3)
        values,jac=content_statistics(weights,basis,x,src,v,inst,True)
        np.testing.assert_allclose(values,content_statistics(weights,basis,x,src,v,inst))
        for m in range(3):
            for a in range(2):
                plus=weights.copy();minus=weights.copy();plus[m,a]+=1e-6;minus[m,a]-=1e-6
                numerical=(content_statistics(plus,basis,x,src,v,inst)-content_statistics(minus,basis,x,src,v,inst))/2e-6
                np.testing.assert_allclose(jac[:,m,a],numerical,atol=1e-8,rtol=1e-6)

    def test_acceptance_requires_mean_gain_confidence_and_both_stem_content(self):
        baseline={'si_sdr_db':10.,'spectral_deficit':.1,'spectral_excess':.1}
        candidate={'si_sdr_db':10.2,'spectral_deficit':.09,'spectral_excess':.09}
        report={'test_mean_delta_db':.3,'bootstrap_95pct':[.1,.5],
            'summary':{'test':{'v1':{s:dict(baseline) for s in ('vocal','instrumental')},
                'v2_band':{s:dict(candidate) for s in ('vocal','instrumental')}}}}
        self.assertTrue(passes_expanded(report))
        for field,value in [('test_mean_delta_db',.19),('bootstrap_95pct',[-.01,.5])]:
            bad=copy.deepcopy(report);bad[field]=value
            self.assertFalse(passes_expanded(bad))
        for stem in ('vocal','instrumental'):
            for metric,value in [('si_sdr_db',9.),('spectral_deficit',.11),('spectral_excess',.11)]:
                bad=copy.deepcopy(report);bad['summary']['test']['v2_band'][stem][metric]=value
                self.assertFalse(passes_expanded(bad))

    def test_quadratic_fit_matches_direct_complex_spectral_error(self):
        rng=np.random.default_rng(48)
        x=rng.normal(size=(4,2,13,7))+1j*rng.normal(size=(4,2,13,7))
        target=rng.normal(size=(2,13,7))+1j*rng.normal(size=(2,13,7))
        basis=rng.uniform(size=(13,3));basis/=basis.sum(axis=1,keepdims=True)
        weights=rng.uniform(size=(4,3));weights/=weights.sum(axis=0,keepdims=True)
        gram,linear,constant=frequency_statistics(x,target,basis,.17)
        flat=weights.ravel()
        predicted=np.einsum('mf,mcft->cft',weights@basis.T,x)
        expected=.17*np.sum(np.abs(predicted-target)**2)
        self.assertAlmostEqual(float(flat@gram@flat-2*linear@flat+constant),float(expected),places=10)
