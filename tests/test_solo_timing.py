import unittest
from karaoke_timing import repair_timing, ass_word_tags

class SoloTimingTests(unittest.TestCase):
    def test_instrumental_label_fills_full_interval_in_video(self):
        row={'text':'SOLO...','start':17,'end':21,'words':[]}
        fixed=repair_timing([row])[0]
        self.assertEqual(fixed['words'][0]['start'],17)
        self.assertEqual(fixed['words'][0]['end'],21)
        self.assertIn(r'\kf400',ass_word_tags(fixed))
        self.assertEqual(row['words'],[])

    def test_actual_lyrics_not_assigned_instrumental_timing(self):
        row={'text':'SOLO BİR ŞARKI','start':17,'end':21,'words':[]}
        self.assertEqual(repair_timing([row]),[row])
