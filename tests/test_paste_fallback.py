import copy
import unittest
from karaoke_anchored import anchor_transcript,anchor_transcript_rows
from karaoke_timing import timing_issues


class PasteFallbackTests(unittest.TestCase):
    def test_missing_middle_line_does_not_discard_matched_rows(self):
        recognized=[{'words':[{'word':'BİR','start':2,'end':3},{'word':'ÜÇ','start':10,'end':11}]}]
        original=copy.deepcopy(recognized)
        with self.assertRaises(ValueError):anchor_transcript('Bir\nİki\nÜç',recognized)
        rows,report=anchor_transcript_rows('Bir\nİki\nÜç',recognized)
        self.assertEqual([r['text'] for r in rows],['Bir','İki','Üç'])
        self.assertEqual([r['start'] for r in rows],[2,3,10])
        self.assertEqual(report['pending'],[2])
        self.assertEqual(rows[1]['end'],rows[1]['start'])
        self.assertTrue(timing_issues(rows,require_words=False))
        self.assertEqual(recognized,original)

    def test_repeated_chorus_uses_later_occurrence(self):
        recognized=[{'words':[{'word':'BİR','start':2,'end':3},{'word':'BİR','start':20,'end':21}]}]
        rows,report=anchor_transcript_rows('Bir\nEksik\nBir',recognized)
        self.assertEqual([r['start'] for r in rows],[2,3,20])
        self.assertEqual(report['aligned'],2)

    def test_no_recognition_retains_every_nonempty_line(self):
        rows,report=anchor_transcript_rows(' İlk satır \n\nİkinci satır ',[])
        self.assertEqual([r['text'] for r in rows],['İlk satır','İkinci satır'])
        self.assertEqual(report['pending'],[1,2])
        self.assertTrue(all(r['start']==r['end']==0 and not r['words'] for r in rows))


if __name__=='__main__':unittest.main()
