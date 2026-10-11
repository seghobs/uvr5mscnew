import unittest
from tools.atlas_content_refine import passes_content_confirmation,passes_robust_confirmation

class ContentConfirmationTests(unittest.TestCase):
    def test_both_stems_must_meet_the_content_target(self):
        data={'accepted':True,'summary':{
            'current':{s:{'spectral_deficit':.1} for s in ('vocal','instrumental')},
            'candidate':{s:{'spectral_deficit':.098} for s in ('vocal','instrumental')}}}
        self.assertTrue(passes_content_confirmation(data))
        for stem in ('vocal','instrumental'):
            data['summary']['candidate'][stem]['spectral_deficit']=.0995
            self.assertFalse(passes_content_confirmation(data))
            data['summary']['candidate'][stem]['spectral_deficit']=.098
        data['accepted']=False
        self.assertFalse(passes_content_confirmation(data))

    def test_invalid_content_cannot_pass(self):
        data={'accepted':True,'summary':{
            'current':{s:{'spectral_deficit':.1} for s in ('vocal','instrumental')},
            'candidate':{s:{'spectral_deficit':float('nan')} for s in ('vocal','instrumental')}}}
        self.assertFalse(passes_content_confirmation(data))

    def test_robust_confirmation_needs_positive_conservative_interval(self):
        data={'accepted':True,'bootstrap_97_5pct':[-.01,.1],'summary':{
            'current':{s:{'spectral_deficit':.1} for s in ('vocal','instrumental')},
            'candidate':{s:{'spectral_deficit':.098} for s in ('vocal','instrumental')}}}
        self.assertFalse(passes_robust_confirmation(data))
        data['bootstrap_97_5pct']=[.01,.1]
        self.assertTrue(passes_robust_confirmation(data))
