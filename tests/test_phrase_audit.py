import copy
import unittest
from karaoke_phrase_audit import consensus,apply_phrase_audit,attach_consensus_syllables
from karaoke_syllable_timing import syllable_pieces,syllable_fill
from karaoke_timing import ass_word_tags


def row():
    return {'id':'a','text':'KARA','start':1.,'end':4.,'words':[{'word':'KARA','start':1.,'end':4.,'probability':.95,'timing_source':'ctc','needs_review':False}]}


def proposal(model='one',source='vocals',start=1.,end=4.):
    return {'word':'KARA','start':start,'end':end,'probability':.8,'needs_review':False,'model':model,'source':source,
            'syllables':[{'text':'ka','start':1.,'end':1.2,'score':.8},{'text':'ra','start':2.,'end':4.,'score':.8}]}


class PhraseAuditTests(unittest.TestCase):
    def test_repeated_contexts_of_same_model_are_not_independent_votes(self):
        self.assertIsNone(consensus([proposal(),proposal(source='original'),proposal()]))
        self.assertIsNotNone(consensus([proposal(),proposal('two')]))

    def test_equally_supported_conflicting_occurrences_are_not_chosen(self):
        self.assertIsNone(consensus([proposal(),proposal('two'),proposal(source='original',start=10,end=13),proposal('two','original',10,13)]))

    def test_high_confidence_mistake_is_flagged_without_moving_it(self):
        rows=[row()];old=copy.deepcopy(rows)
        result=apply_phrase_audit(rows,{('a',0):[proposal(start=1.5),proposal('two',start=1.5)]},10)
        self.assertEqual(result['phrase_disagreements'],1);self.assertTrue(rows[0]['words'][0]['needs_review'])
        self.assertEqual(rows[0]['words'][0]['start'],old[0]['words'][0]['start'])

    def test_unlocated_word_requires_bounded_multimodel_evidence(self):
        rows=[row()];rows[0]['words'][0].update(start=0,end=0,needs_review=True,probability=0)
        result=apply_phrase_audit(rows,{('a',0):[proposal(),proposal('two')]},10)
        self.assertEqual(result['phrase_repaired_words'],1);self.assertEqual(rows[0]['words'][0]['start'],1)
        self.assertFalse(rows[0]['words'][0]['needs_review'])

    def test_manual_and_locked_words_are_untouched(self):
        for kind in ('manual','locked'):
            rows=[row()]
            if kind=='locked':rows[0]['locked']=True
            else:rows[0]['words'][0]['timing_source']='manual'
            before=copy.deepcopy(rows)
            apply_phrase_audit(rows,{('a',0):[proposal(),proposal('two')]},10)
            attach_consensus_syllables(rows,{('a',0):[proposal(),proposal('two')]})
            self.assertEqual(rows,before)

    def test_syllables_keep_real_gap_and_held_vowel_duration(self):
        rows=[row()]
        report=attach_consensus_syllables(rows,{('a',0):[proposal(),proposal('two')]})
        word=rows[0]['words'][0]
        self.assertEqual(report['automatic_syllables'],2)
        self.assertEqual(syllable_fill(word,1.5),.5);self.assertEqual(syllable_fill(word,1.9),.5)
        self.assertEqual(syllable_fill(word,3),.75)
        self.assertIn(r'{\kf20}KA{\k80}\h{\kf200}RA',ass_word_tags(rows[0]))

    def test_invalid_stale_and_disagreeing_syllables_are_ignored(self):
        for kind in ('text','bounds','order','weak','nan'):
            word=row()['words'][0];word['syllables']=proposal()['syllables']
            if kind=='text':word['word']='BAŞKA'
            if kind=='bounds':word['end']=3
            if kind=='order':word['syllables'][1]['start']=1.1
            if kind=='weak':word['syllables'][0]['score']=.1
            if kind=='nan':word['syllables'][0]['end']=float('nan')
            self.assertEqual(syllable_pieces(word),[],kind)
        rows=[row()];bad=proposal('two');bad['syllables'][1]['start']=2.4
        self.assertEqual(attach_consensus_syllables(rows,{('a',0):[proposal(),bad]})['automatic_syllables'],0)

    def test_held_final_syllable_uses_verified_vocal_endpoint_not_equal_slices(self):
        rows=[row()];word=rows[0]['words'][0];word['end']=5.;rows[0]['end']=5.
        word['timing_reference']={'method':'vocal_sustain_endpoint','scope':'end_only','previous_end':4.}
        self.assertEqual(attach_consensus_syllables(rows,{('a',0):[proposal(),proposal('two')]})['automatic_syllables'],2)
        self.assertEqual(word['syllables'][0]['end'],1.2);self.assertEqual(word['syllables'][1]['end'],5.)
        self.assertEqual(syllable_fill(word,3.5),.75)
        word['end']=6.
        self.assertEqual(syllable_pieces(word),[],'manual retiming invalidates the old internal syllable map')


if __name__=='__main__':unittest.main()
