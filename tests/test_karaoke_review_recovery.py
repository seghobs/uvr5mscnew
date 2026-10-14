import unittest
from karaoke_review_recovery import repeat_boundary_candidate

class RepeatBoundaryTests(unittest.TestCase):
    def test_requires_distinct_channels_and_discriminating_acoustic_match(self):
        original={'word':'YÜCE','start':1,'end':2,'probability':.25,'needs_review':True}
        candidates=[{**original,'start':1.01,'end':2.01,'probability':.4,'recovery_channel':channel} for channel in ['mix','right']]
        result=repeat_boundary_candidate(original,candidates,0,3,.10,.20)
        self.assertFalse(result['needs_review']);self.assertEqual(result['probability'],.4)
        self.assertIs(repeat_boundary_candidate(original,candidates,0,3,.18,.20),original)
        self.assertIs(repeat_boundary_candidate(original,candidates[:1]*2,0,3,.10,.20),original)
        self.assertIs(repeat_boundary_candidate(original,candidates,0,1.9,.10,.20),original)

    def test_large_boundary_changes_are_rejected(self):
        original={'word':'GEL','start':1,'end':2,'needs_review':True}
        proposals=[{'start':1.4,'end':2,'probability':.8,'recovery_channel':channel} for channel in ['left','right']]
        self.assertIs(repeat_boundary_candidate(original,proposals,0,3,.01,.40),original)

