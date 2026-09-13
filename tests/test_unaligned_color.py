import unittest
from karaoke_timing import ass_word_tags

class UnalignedColorTests(unittest.TestCase):
    def test_unaligned_row_stays_neutral(self):
        result=ass_word_tags(dict(start=1,end=4,text='YAR',words=[]))
        self.assertEqual(result,r'{\1c&HFFFFFF&}YAR')
        self.assertNotIn(r'\kf',result)
    def test_aligned_words_keep_karaoke(self):
        result=ass_word_tags(dict(start=1,end=4,text='YAR',words=[dict(word='YAR',start=2,end=3,timing_source='ctc')]))
        self.assertIn(r'\kf100',result)
        self.assertNotIn(r'\1c',result)
if __name__=='__main__': unittest.main()
