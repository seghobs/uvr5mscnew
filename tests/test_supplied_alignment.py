import copy
import unittest
from karaoke_supplied_alignment import alignment_blocks,assemble,repair_anomalous_words


class SuppliedAlignmentTests(unittest.TestCase):
    def test_occurrence_window_cannot_overlap_untouched_neighbour(self):
        from karaoke_supplied_alignment import apply_occurrence_windows
        rows=[{'text':'A','_occurrence_words':[{'word':'A','start':1,'end':4,'probability':.9}]},
              {'text':'B'}]
        aligned=[{'word':'A','start':1,'end':2,'probability':.8},
                 {'word':'B','start':3,'end':5,'probability':.8}]
        original=copy.deepcopy(aligned)
        self.assertEqual(apply_occurrence_windows(aligned,rows,{'a':1,'b':2},0,10),0)
        self.assertEqual(aligned,original)
        rows[0]['_occurrence_words'][0]['end']=2.5
        self.assertEqual(apply_occurrence_windows(aligned,rows,{'a':1,'b':2},0,10),1)

    def test_rejected_occurrence_exposes_original_neighbour_boundary(self):
        from karaoke_supplied_alignment import apply_occurrence_windows
        rows=[{'text':'A','_occurrence_words':[{'word':'A','start':1,'end':4,'probability':.9}]},
              {'text':'B','_occurrence_words':[{'word':'B','start':4,'end':6,'probability':.9}]},
              {'text':'C'}]
        aligned=[{'word':'A','start':1,'end':2}, {'word':'B','start':3,'end':4},
                 {'word':'C','start':5,'end':7}]
        original=copy.deepcopy(aligned)
        self.assertEqual(apply_occurrence_windows(aligned,rows,{'a':1,'b':2,'c':3},0,10),0)
        self.assertEqual(aligned,original)

    def test_automatic_copy_must_not_compress_and_steal_supplied_audio(self):
        from karaoke_supplied_alignment import inconsistent_auto_repeats
        rows=[{'id':'given','text':'TU HERE'},
              {'id':'auto-repeat:test','text':'DÎLANA NAV','_occurrence_words':[
                  {'start':245.78,'end':247.}, {'start':247.2,'end':249.8}]}]
        aligned=[{'start':246.54,'end':247.1,'probability':.9},
                 {'start':247.4,'end':249.24,'probability':.9},
                 {'start':249.4,'end':249.64,'probability':.7},
                 {'start':249.66,'end':250.46,'probability':.15}]
        rejected=inconsistent_auto_repeats(rows,aligned,{'given'})
        self.assertEqual([r['id'] for r in rejected],['auto-repeat:test'])
        self.assertEqual(inconsistent_auto_repeats(rows,aligned,{'given','auto-repeat:test'}),[])
        # A separate fast repeat keeps its own observed duration and position.
        fast=copy.deepcopy(rows);fast[1]['_occurrence_words']=[{'start':249.4,'end':249.64},{'start':249.66,'end':250.46}]
        self.assertEqual(inconsistent_auto_repeats(fast,aligned,{'given'}),[])
        shifted=copy.deepcopy(aligned)
        for word in shifted:word['start']+=100;word['end']+=100
        self.assertEqual(inconsistent_auto_repeats(rows,shifted,{'given'},offset=100)[0]['start'],345.78)

    def test_local_retry_handles_unscored_empty_audio_without_changing_word(self):
        import numpy as np
        from karaoke_supplied_alignment import rescue_weak_words
        for value in ('missing',None):
            for threshold in (.1,.5):
                word={'word':'AB','start':1,'end':1.5,'timing_source':'estimated','needs_review':True}
                if value!='missing':word['probability']=value
                words=[copy.deepcopy(word)]
                count=rescue_weak_words(np.zeros((0,2),dtype='float32'),16000,0,3,words,
                    None,None,{'a':1,'b':2,'|':3,'[PAD]':0},'cpu',lambda *args:None,threshold=threshold)
                self.assertEqual(count,0)
                self.assertEqual(words,[word])

    def test_unscored_candidates_cannot_abort_or_confirm_alignment(self):
        from karaoke_supplied_alignment import choose_boundary_candidate
        original={'word':'XEW','start':0,'end':0,'timing_source':'estimated','needs_review':True}
        for value in ('missing',None,float('nan'),float('inf'),-.1,1.1,True,'0.9'):
            candidate={**original,'start':1,'end':2,'recovery_channel':'left'}
            if value!='missing':candidate['probability']=value
            self.assertIs(choose_boundary_candidate(original,[candidate],0,3),original)
        left={**original,'start':1,'end':2,'probability':.8,'recovery_channel':'left'}
        right={**left,'probability':.9,'recovery_channel':'right'}
        fixed=choose_boundary_candidate(original,[original,left,right],0,3)
        self.assertFalse(fixed['needs_review'])
        self.assertEqual(fixed['probability'],.8)

    def test_unscored_word_becomes_review_placeholder_not_exception(self):
        for value in ('missing',None,float('nan')):
            word={'word':'XEW','start':1,'end':2}
            if value!='missing':word['probability']=value
            result,report=assemble([{'text':'XEW','start':0,'end':.5}],[([0],[word])],10)
            self.assertEqual(report['linked_words'],0)
            self.assertTrue(result[0]['words'][0]['needs_review'])
            self.assertEqual(result[0]['words'][0]['probability'],0)

    def test_generated_duplicate_prefix_without_audio_is_removed(self):
        from karaoke_supplied_alignment import trim_unvoiced_repeat_prefixes
        rows=[{'text':'YAZIMIZ HEY','words':[{'word':'HEY','start':9,'end':10}]},
              {'id':'auto-repeat:test','text':'HEY GÖNÜL','words':[{'word':'HEY','start':9,'end':9,'timing_source':'estimated','needs_review':True},{'word':'GÖNÜL','start':10.2,'end':11}]}]
        self.assertEqual(trim_unvoiced_repeat_prefixes(rows),1)
        self.assertEqual(rows[1]['text'],'GÖNÜL')
        self.assertEqual(rows[1]['repeat_prefix_repair'],{'word':'HEY','start':9,'end':9})
        self.assertEqual(rows[0]['words'][0]['end'],10)
        self.assertEqual(trim_unvoiced_repeat_prefixes(rows),0)

    def test_user_prefix_and_voiced_repeat_are_preserved(self):
        from karaoke_supplied_alignment import trim_unvoiced_repeat_prefixes
        for identity,locked,end in [('user',False,9),('auto-repeat:test',True,9),('auto-repeat:test',False,9.5)]:
            rows=[{'text':'HEY','words':[{'word':'HEY','start':9,'end':10}]},
                  {'id':identity,'locked':locked,'text':'HEY','words':[{'word':'HEY','start':9,'end':end}]}]
            self.assertEqual(trim_unvoiced_repeat_prefixes(rows),0)

    def test_local_uncertainty_retry_does_not_touch_confirmed_manual_word(self):
        from karaoke_supplied_alignment import rescue_weak_words
        word={'word':'GEL','start':1,'end':2,'probability':.2,'timing_source':'manual','needs_review':False}
        words=[copy.deepcopy(word)]
        self.assertEqual(rescue_weak_words(None,16000,0,3,words,None,None,{},'cpu',lambda *args:None,threshold=.5),0)
        self.assertEqual(words,[word])
    def test_uncertain_boundaries_require_two_agreeing_channels(self):
        from karaoke_supplied_alignment import choose_boundary_candidate
        original={'word':'GEL','start':1,'end':2,'probability':.3,'needs_review':True}
        left={**original,'start':1.1,'end':1.8,'probability':.8,'recovery_channel':'left'}
        right={**left,'start':1.12,'end':1.82,'probability':.9,'recovery_channel':'right'}
        fixed=choose_boundary_candidate(original,[left,right],0,3)
        self.assertFalse(fixed['needs_review'])
        self.assertAlmostEqual(fixed['end'],1.81)
        self.assertEqual(choose_boundary_candidate(original,[left],0,3),original)
        self.assertEqual(choose_boundary_candidate(original,[left,{**right,'end':2.2}],0,3),original)
        self.assertEqual(choose_boundary_candidate(original,[left,right],0,1.5),original)

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

    def test_terminal_context_repairs_short_borrowed_end_and_keeps_uncertainty(self):
        vocab={c:i for i,c in enumerate('gelbana')}
        proposal=[{'word':'GEL','start':1,'end':2,'probability':.9},
                  {'word':'BANA','start':3,'end':4,'probability':.8,'needs_review':True}]
        rows=[{'text':'GEL BANA','_terminal_occurrence':True,'_occurrence_words':proposal}]
        words=[{'word':'GEL','start':1,'end':2,'probability':.9},
               {'word':'BANA','start':3,'end':5,'probability':.8}]
        repair_anomalous_words(words,rows,vocab,0,6)
        self.assertEqual(words[1]['end'],4)
        self.assertTrue(words[1]['needs_review'])
        rows[0]['words']=[{'word':'BANA','start':3,'end':5,'timing_source':'manual','needs_review':False}]
        words[1]['end']=5
        repair_anomalous_words(words,rows,vocab,0,6)
        self.assertEqual(words[1]['end'],5)


if __name__=='__main__':unittest.main()
