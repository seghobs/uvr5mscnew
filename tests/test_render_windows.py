import unittest
from karaoke_timing import render_windows, centiseconds

class RenderWindowsTests(unittest.TestCase):
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
