import unittest
from types import SimpleNamespace as Span
from karaoke_ctc import normalized_words, words_from_spans


class CharacterAlignmentTests(unittest.TestCase):
    def vocab(self):
        return {c:i for i,c in enumerate('|abcdefghijklmnopqrstuvwxyzçöüğış')}

    def test_mixed_script_copy_paste_is_repaired_without_changing_lyrics(self):
        words=[{'word':'DİĞERİNDЕ'},{'word':'KЕNDİNCE'},{'word':'KΑHVE'},{'word':'КAHVE'}]
        original=[dict(w) for w in words]
        self.assertEqual(normalized_words(words,self.vocab()),['diğerinde','kendince','kahve','kahve'])
        self.assertEqual(words,original)

    def test_typographic_forms_accents_and_invisible_formatting(self):
        words=[{'word':s} for s in ['ＫＡＨＶＥ','ka\u200bhve','kah\u00adve','âşık','İYİ','IŞIK','ÖZÜ','ŞE\u0301KER']]
        self.assertEqual(normalized_words(words,self.vocab()),['kahve','kahve','kahve','aşık','iyi','ışık','özü','şeker'])

    def test_foreign_words_are_not_guessed_or_partially_erased(self):
        for text in ['СОН','世界','kara2','KЖHVE']:
            with self.assertRaises(ValueError):normalized_words([{'word':text}],self.vocab())

    def test_unsupported_word_preserves_positions_and_known_alignment(self):
        from karaoke_ctc import supported_targets,restore_unsupported_words
        from karaoke_supplied_alignment import assemble
        words=[{'word':s} for s in ['GEL','KЖHVE','GEL']]
        indices,targets=supported_targets(words,self.vocab())
        self.assertEqual(indices,[0,2]);self.assertEqual(targets,['gel','gel'])
        aligned=[dict(word='GEL',start=t,end=t+.5,probability=.9,timing_source='ctc',needs_review=False) for t in [1,4]]
        restored=restore_unsupported_words(words,indices,aligned,0)
        result,report=assemble([dict(text='GEL KЖHVE GEL',start=0,end=5)], [([0],restored)],5)
        self.assertEqual([w['word'] for w in result[0]['words']],['GEL','KЖHVE','GEL'])
        self.assertEqual(result[0]['words'][0],aligned[0]);self.assertEqual(result[0]['words'][2],aligned[1])
        self.assertTrue(result[0]['words'][1]['needs_review']);self.assertEqual(report['linked_words'],2)
        self.assertEqual(report['review_rows'],[1])
        missing=restore_unsupported_words([{'word':'世界'}],[],[],0)
        self.assertEqual(missing[0]['start'],missing[0]['end'])

    def test_repeat_scan_skips_unknown_text_without_aborting_other_rows(self):
        import numpy as np
        from karaoke_repeat_spotting import find_occurrences,text_key,expand_supplied_rows
        vocab=self.vocab();vocab['[PAD]']=len(vocab)
        emission=np.full((30,len(vocab)),-10,dtype=np.float32);emission[:,vocab['[PAD]']]=0
        row=dict(id='unknown',text='KЖHVE',start=0,end=0,words=[])
        self.assertEqual(find_occurrences(emission,row,vocab),[])
        self.assertTrue(text_key(row,vocab).startswith('\0unsupported:'))
        self.assertEqual(text_key({'text':'KЕNDİNCE'},vocab),text_key({'text':'KENDİNCE'},vocab))
        rows=[row,dict(id='normal',text='GEL BANA',start=0,end=0,words=[])]
        expanded,_,_=expand_supplied_rows(rows,emission,vocab)
        self.assertEqual([r['text'] for r in expanded],[r['text'] for r in rows])

    def test_stereo_retries_preserve_channel_evidence_and_support_mono(self):
        import numpy as np
        from karaoke_ctc import alignment_mono
        stereo=np.array([[.8,-.8],[.2,-.2]])
        np.testing.assert_allclose(alignment_mono(stereo,'mix'),[0,0])
        np.testing.assert_allclose(alignment_mono(stereo,'left'),[.8,.2])
        np.testing.assert_allclose(alignment_mono(stereo,'right'),[-.8,-.2])
        mono=np.array([.8,.2])
        np.testing.assert_array_equal(alignment_mono(mono,'right'),mono)
        with self.assertRaises(ValueError):alignment_mono(stereo,'unknown')

    def test_sample_rounding_fix_does_not_shift_real_outside_words(self):
        from karaoke_ctc import clamp_sample_start
        words=[{'start':10.2412471655,'end':10.5,'syllables':[{'start':10.2412471655,'end':10.3}]},
               {'start':10.1,'end':10.2}]
        clamp_sample_start(words,10.241268,44100)
        self.assertEqual(words[0]['start'],10.241268)
        self.assertEqual(words[0]['syllables'][0]['start'],10.241268)
        self.assertEqual(words[0]['end'],10.5)
        self.assertEqual(words[1]['start'],10.1)

    def test_zero_placeholders_do_not_mark_real_neighbours_as_overlapping(self):
        from karaoke_ctc import mark_word_overlaps,has_timed_row
        rows=[{'start':10,'end':11,'words':[{'start':10,'end':11,'needs_review':False}]},
              {'start':0,'end':0,'words':[{'start':0,'end':0,'needs_review':True}]},
              {'start':12,'end':13,'words':[{'start':12,'end':13,'needs_review':False}]}]
        mark_word_overlaps(rows)
        self.assertFalse(rows[0]['words'][0]['needs_review'])
        self.assertFalse(rows[2]['words'][0]['needs_review'])
        self.assertFalse(has_timed_row(rows[1]))
        rows[2]['words'][0]['start']=10.5
        mark_word_overlaps(rows)
        self.assertTrue(rows[0]['words'][0]['needs_review'])
        self.assertTrue(rows[2]['words'][0]['needs_review'])

    def test_turkish_case_and_punctuation(self):
        self.assertEqual(normalized_words([{'word':'İYİ!'}, {'word':'IŞIK'}], {c:i for i,c in enumerate('iyışk')}), ['iyi','ışık'])

    def test_unsupported_characters_are_not_silently_dropped(self):
        with self.assertRaises(ValueError):
            normalized_words([{'word':'kara2'}], {c:i for i,c in enumerate('kara')})

    def test_repeated_words_consume_distinct_character_spans(self):
        targets = [1,2,3,2,4,1,2,3,2,4,5,6,7,8]
        spans = [Span(token=t,start=2*i,end=2*i+1,score=.9) for i,t in enumerate(targets)]
        result = words_from_spans([{'word':w} for w in ['kara','kara','seni']], ['kara','kara','seni'],spans,targets,.02,12.)
        self.assertEqual(len(result),3)
        self.assertLess(result[0]['end'],result[1]['start'])
        self.assertLess(result[1]['end'],result[2]['start'])
        self.assertEqual(result[1]['start'],12.2)
        self.assertEqual(result[1]['timing_source'],'ctc')

    def test_missing_repeat_is_rejected(self):
        with self.assertRaises(ValueError):
            words_from_spans([{'word':'a'},{'word':'a'}],['a','a'],[Span(token=1)], [1,2,1],.02,0)

    def test_low_acoustic_score_requires_review(self):
        result = words_from_spans([{'word':'a'}],['a'],[Span(token=1,start=1,end=2,score=.1)],[1],.02,0)
        self.assertTrue(result[0]['needs_review'])

    def test_short_ctc_blank_margins_are_bounded_without_faking_confidence(self):
        spans=[Span(token=1,start=0,end=1,score=.2),Span(token=2,start=5,end=6,score=.9),Span(token=3,start=10,end=11,score=.7)]
        words=[{'word':'a'},{'word':'b'}]
        balanced=words_from_spans(words,['a','b'],spans,[1,2,3],.02,0,boundary_policy='balanced')
        self.assertAlmostEqual(balanced[0]['end'],.06)
        self.assertAlmostEqual(balanced[1]['start'],.16)
        self.assertEqual(balanced[0]['probability'],.2);self.assertTrue(balanced[0]['needs_review'])
        self.assertFalse(balanced[0]['timing_reference']['acoustically_verified'])
        self.assertLessEqual(balanced[0]['end'],balanced[1]['start'])

    def test_breath_gaps_and_weak_delimiters_are_not_redistributed(self):
        for gap,score in [(50,.9),(5,.1)]:
            spans=[Span(token=1,start=0,end=1,score=.9),Span(token=2,start=gap,end=gap+1,score=score),Span(token=3,start=gap*2,end=gap*2+1,score=.9)]
            words=[{'word':'a'},{'word':'b'}]
            regular=words_from_spans(words,['a','b'],spans,[1,2,3],.02,0)
            balanced=words_from_spans(words,['a','b'],spans,[1,2,3],.02,0,boundary_policy='balanced')
            self.assertEqual(regular,balanced)

    def test_group_boundary_uses_source_duration_not_resampled_padding(self):
        # Resampling rounds length up; its padded duration would overlap the
        # next group's first source sample. Exercise the actual scale expression.
        import ast
        from pathlib import Path
        tree = ast.parse(Path('karaoke_ctc.py').read_text(encoding='utf8'))
        call = next(n for n in ast.walk(tree) if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Name) and n.func.id == 'words_from_spans')
        frames, rate, ticks = 44101, 44100, 50
        scale = eval(compile(ast.Expression(call.args[4]), '<scale>', 'eval'), {
            'audio':range(frames), 'rate':rate, 'emissions':Span(shape=(1,ticks)),
            'wave':range(16001)})
        result = words_from_spans([{'word':'a'}], ['a'],
            [Span(token=1,start=0,end=ticks,score=.9)], [1], scale, 90.)
        self.assertAlmostEqual(result[0]['end'], 90. + frames/rate)
        self.assertLess(result[0]['end'],90. + 16001/16000)

if __name__ == '__main__': unittest.main()
