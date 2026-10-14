import unittest
from karaoke_timing import render_windows, centiseconds

class RenderWindowsTests(unittest.TestCase):
    def test_lead_does_not_cut_the_previous_measured_word(self):
        rows=[{'start':1,'end':2.95,'text':'A','words':[{'word':'A','start':1,'end':2.95}]},
              {'start':3,'end':4,'text':'B','words':[{'word':'B','start':3,'end':4}]}]
        windows=render_windows(rows,lead=.12)
        self.assertEqual(windows[0][1],2.95)
        self.assertEqual(windows[1][0]['start'],2.95)

    def test_lead_is_display_only_and_follows_earlier_measured_word(self):
        row={'start':2,'end':4,'text':'GEL','words':[{'word':'GEL','start':1.8,'end':3.9}]}
        window=render_windows([row],lead=.12)[0]
        self.assertAlmostEqual(window[0]['start'],1.68)
        self.assertEqual(window[0]['words'][0]['start'],1.8)
        self.assertEqual(row['start'],2)

    def test_overlap_and_out_of_order(self):
        rows=[dict(start=241.65,end=246.47,text='A'),dict(start=246.47,end=251.59,text='B'),dict(start=243.92,end=246.92,text='C')]
        windows=render_windows(rows)
        self.assertEqual([r['text'] for r,e in windows],['A','C','B'])
        for i,(row,end) in enumerate(windows[:-1]):
            self.assertLessEqual(centiseconds(end),centiseconds(windows[i+1][0]['start']))
        self.assertEqual(rows[0]['end'],246.47)
    def test_same_start_and_empty_rows(self):
        rows=[dict(start=0,end=2,text='A'),dict(start=0,end=3,text='B'),dict(start=1,end=2,text=' ')]
        self.assertEqual(len(render_windows(rows)),1)
if __name__=='__main__': unittest.main()
