import copy
import unittest
from karaoke_supplied_alignment import alignment_blocks,assemble,repair_anomalous_words


class SuppliedAlignmentTests(unittest.TestCase):
    def test_default_times_do_not_limit_full_song_and_repeats_keep_order(self):
        rows=[{'text':'SOLO...','start':0,'end':.5},{'text':'AYNI SÖZ','start':0,'end':.5},
              {'text':'SOLO...','start':0,'end':.5},{'text':'AYNI SÖZ','start':0,'end':.5}]
        self.assertEqual(alignment_blocks(rows,300),[([1,3],0.,300)])
        before=copy.deepcopy(rows)
        words=[{'word':word,'start':a,'end':a+1,'probability':.9,'timing_source':'ctc','needs_review':False}
               for word,a in [('AYNI',20),('SÖZ',22),('AYNI',150),('SÖZ',152)]]
        result,report=assemble(rows,[([1,3],words)],300)
        self.assertEqual(rows,before)
        self.assertEqual([r['text'] for r in result],[r['text'] for r in rows])
        self.assertEqual((result[0]['start'],result[0]['end']),(0,20))
        self.assertEqual((result[2]['start'],result[2]['end']),(23,150))
        self.assertEqual(result[3]['words'][0]['start'],150)
        self.assertEqual(report['linked_words'],4)

    def test_locked_and_confirmed_manual_rows_delimit_audio_search(self):
        manual={'text':'KORU','start':30,'end':32,'words':[{'word':'KORU','start':30,'end':32,
            'timing_source':'manual','needs_review':False}]}
        locked={'text':'KİLİTLİ','start':60,'end':65,'locked':True}
        rows=[{'text':'ÖNCE','start':0,'end':.5},manual,{'text':'ORTA','start':0,'end':.5},locked,
              {'text':'SONRA','start':0,'end':.5}]
        self.assertEqual(alignment_blocks(rows,100),[([0],0.,30),([2],32,60),([4],65,100)])
        result,_=assemble(rows,[],100)
        self.assertEqual(result[1],manual);self.assertEqual(result[3],locked)
        with self.assertRaises(ValueError):alignment_blocks([locked,manual],100)

    def test_absent_low_confidence_word_is_not_marked_linked(self):
        rows=[{'text':'YOK','start':0,'end':.5}]
        result,report=assemble(rows,[([0],[{'word':'YOK','start':4,'end':5,'probability':.01}])],10)
        self.assertEqual(report['linked_words'],0)
        self.assertEqual(report['review_rows'],[1])
        self.assertEqual(result[0]['words'][0]['start'],result[0]['words'][0]['end'])

    def test_wrong_or_extra_recognized_text_is_rejected(self):
        rows=[{'text':'VERİLEN','start':0,'end':.5}]
        with self.assertRaises(ValueError):assemble(rows,[([0],[{'word':'BAŞKA'}])],10)

    def test_partial_manual_links_are_preserved_and_conflicts_rejected(self):
        manual={'word':'ELLE','start':2,'end':3,'timing_source':'manual','needs_review':False}
        row={'text':'ELLE YENİ','start':0,'end':5,'words':[manual]}
        aligned=[{'word':'ELLE','start':1,'end':1.5,'probability':.9,'timing_source':'ctc'},
                 {'word':'YENİ','start':4,'end':5,'probability':.9,'timing_source':'ctc'}]
        result,_=assemble([row],[([0],aligned)],10)
        self.assertEqual(result[0]['words'][0],manual)
        aligned[1].update(start=2.5,end=4)
        with self.assertRaises(ValueError):assemble([row],[([0],aligned)],10)

    def test_independent_occurrence_repairs_word_stretched_over_music(self):
        vocab={c:i for i,c in enumerate('eskive')}
        proposal=[{'word':'ESKİ','start':18,'end':19,'probability':.9},{'word':'VE','start':20,'end':21,'probability':.8}]
        rows=[{'text':'ESKİ VE','_occurrence_words':proposal}]
        words=[{'word':'ESKİ','start':1,'end':19,'probability':.8},{'word':'VE','start':20,'end':21,'probability':.8}]
        self.assertEqual(repair_anomalous_words(words,rows,{**vocab,'i':9},0,30),1)
        self.assertEqual((words[0]['start'],words[0]['end']),(18,19))
        self.assertFalse(words[0]['needs_review'])
    def test_occurrence_repair_preserves_manual_words_and_rejects_overlap(self):
        vocab={c:i for i,c in enumerate('eskive')};vocab['i']=9
        manual={'word':'ESKİ','start':1,'end':19,'timing_source':'manual','needs_review':False}
        rows=[{'text':'ESKİ VE','words':[manual],'_occurrence_words':[
            {'word':'ESKİ','start':18,'end':22,'probability':.9},{'word':'VE','start':20,'end':21,'probability':.8}]}]
        words=[{'word':'ESKİ','start':1,'end':19,'probability':.8},{'word':'VE','start':20,'end':21,'probability':.8}]
        before=copy.deepcopy(words)
        self.assertEqual(repair_anomalous_words(words,rows,vocab,0,30),0)
        self.assertEqual(words,before)
        rows[0]['words']=[]
        self.assertEqual(repair_anomalous_words(words,rows,vocab,0,30),0)


if __name__=='__main__':unittest.main()
