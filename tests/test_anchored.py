import copy, unittest
from karaoke_anchored import anchor_exact_text,bounded_refine,combine_candidates
from karaoke_timing import timing_issues,ass_word_tags

class AnchorTests(unittest.TestCase):
    def test_matching_keeps_user_spelling_and_acoustic_metadata(self):
        words=[{'word':'MERHABA,','start':1.,'end':2.,'timing_source':'ctc','needs_review':True,'probability':.4},
               {'word':'DÜNYA!','start':2.5,'end':3.,'timing_source':'ctc'}]
        original=copy.deepcopy(words)
        result=anchor_exact_text({'text':'Merhaba dünya.'},[{'words':words}])
        self.assertEqual([w['word'] for w in result['words']],['Merhaba','dünya.'])
        for before,after in zip(words,result['words']):
            self.assertEqual({k:v for k,v in before.items() if k!='word'},
                             {k:v for k,v in after.items() if k!='word'})
        self.assertEqual(words,original)
        self.assertEqual(timing_issues([result],include_review=False),[])
        self.assertTrue(timing_issues([result]))
        self.assertIn(r'\kf',ass_word_tags(result))

    def test_alternative_preserves_missing_first_word(self):
        first={'word':'SEVDİĞİM','start':52,'end':53,'probability':.9}
        later={'word':'BİR','start':54,'end':55,'probability':.9}
        self.assertEqual([w['word'] for w in combine_candidates([{'words':[later]},{'words':[first,later]}])],['SEVDİĞİM','BİR'])
    def test_stale_envelope_replaced_without_changing_text(self):
        row={'start':23,'end':56,'text':'SEVDİĞİM BİR GÜN BANA'}
        words=[{'word':w,'start':52+i,'end':52.5+i} for i,w in enumerate(row['text'].split())]
        result=anchor_exact_text(row,[{'words':words}])
        self.assertEqual(result['start'],52)
        self.assertEqual(result['text'],row['text'])
        self.assertEqual(row['start'],23)
    def test_large_relocation_rejected(self):
        rows=[{'start':52,'end':53,'text':'BİR','words':[{'word':'BİR','start':52,'end':53}]}]
        def bad(path,segments,language):
            segments[0]['words'][0].update(start=23,end=24)
            return segments
        out=bounded_refine('',rows,'tr',bad)
        self.assertEqual(out[0]['words'][0]['start'],52)
        self.assertTrue(out[0]['words'][0]['needs_review'])
    def test_wrong_text_not_applied(self):
        with self.assertRaises(ValueError):anchor_exact_text({'text':'BİR'},[{'words':[]}])

if __name__=='__main__':unittest.main()
