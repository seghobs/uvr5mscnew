import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from karaoke_row_boundaries import suspicious_boundaries, apply_boundary_candidates, recover_row_boundaries


def word(text,start,end,probability=.9,review=False):
    return dict(word=text,start=start,end=end,probability=probability,timing_source='ctc',needs_review=review)


def fixture():
    return [dict(id='reference',text='DİZLERİM TUTULUR',start=101.36,end=103.48,
                 words=[word('DİZLERİM',101.36,102.04),word('TUTULUR',102.3,103.48)]),
            dict(id='tail',text='BENİ SARAMAZ',start=215.56,end=216.82,
                 words=[word('BENİ',215.56,215.9),word('SARAMAZ',215.98,216.82,.42,True)]),
            dict(id='head',text='DİZLERİM TUTULUR',start=217.26,end=221.52,
                 words=[word('DİZLERİM',217.26,220.12,.59),word('TUTULUR',220.38,221.52)])]


def candidate(rows,channel='left'):
    pair=copy.deepcopy(rows[1:])
    pair[0]['words'][-1]=word('SARAMAZ',216.02,218.04,.68)
    pair[1]['words'][0]=word('DİZLERİM',219.4,220.18,.74)
    return dict(model='tr_mms',channel=channel,rows=pair)


class RowBoundaryTests(unittest.TestCase):
    def test_retry_trigger_does_not_retime_a_word_by_reference_duration(self):
        rows=fixture();before=copy.deepcopy(rows)
        self.assertEqual(suspicious_boundaries(rows),[2])
        self.assertEqual(rows,before)
        self.assertEqual(suspicious_boundaries(rows[1:]),[],'a long word alone is not evidence')
        rows[2]['words'][0]['start']=219.4;rows[2]['start']=219.4
        self.assertEqual(suspicious_boundaries(rows),[])

    def test_joint_consensus_keeps_held_ending_on_previous_row(self):
        rows=fixture();before=copy.deepcopy(rows)
        self.assertTrue(apply_boundary_candidates(rows,2,[candidate(rows),candidate(rows,'right')],243))
        self.assertAlmostEqual(rows[1]['end'],218.04)
        self.assertAlmostEqual(rows[2]['start'],219.4)
        self.assertEqual([r['text'] for r in rows],[r['text'] for r in before])
        self.assertEqual(rows[1]['words'][0],before[1]['words'][0])
        self.assertEqual(rows[2]['words'][1],before[2]['words'][1])
        self.assertLessEqual(rows[1]['end'],rows[2]['start'])
        self.assertTrue(rows[2]['words'][0]['timing_reference']['acoustically_verified'])

    def test_weak_disagreeing_duplicate_or_colliding_evidence_is_rejected(self):
        for kind in ('single','duplicate','weak','disagree','overlap','wrong_text','shifted_anchor','genuine_hold'):
            rows=fixture();before=copy.deepcopy(rows)
            a,b=candidate(rows),candidate(rows,'right')
            if kind=='duplicate':b['channel']='left'
            if kind=='weak':b['rows'][0]['words'][-1]['probability']=.49
            if kind=='disagree':b['rows'][1]['words'][0]['start']-=.3
            if kind=='overlap':
                for c in (a,b):c['rows'][0]['words'][-1]['end']=219.6
            if kind=='wrong_text':b['rows'][1]['words'][0]['word']='BAŞKA'
            if kind=='shifted_anchor':
                for c in (a,b):c['rows'][1]['words'][0]['end']=220.5
            if kind=='genuine_hold':
                for c in (a,b):c['rows'][1]['words'][0]['start']=217.26
            self.assertFalse(apply_boundary_candidates(rows,2,[a] if kind=='single' else [a,b],243),kind)
            self.assertEqual(rows,before,kind)

    def test_manual_and_locked_boundaries_are_preserved(self):
        for part in (1,2):
            for kind in ('locked','manual'):
                rows=fixture();evidence=[candidate(rows),candidate(rows,'right')]
                if kind=='locked':rows[part]['locked']=True
                else:rows[part]['words'][-1 if part==1 else 0]['timing_source']='manual'
                before=copy.deepcopy(rows)
                self.assertEqual(suspicious_boundaries(rows),[])
                self.assertFalse(apply_boundary_candidates(rows,2,evidence,243))
                self.assertEqual(rows,before)

    def test_acoustic_retry_uses_both_rows_together(self):
        rows=fixture();calls=[]
        def refine(path,pair,model,**kwargs):
            calls.append((pair,kwargs))
            return candidate(rows,kwargs['channel'])['rows']
        with patch('soundfile.info',return_value=SimpleNamespace(duration=243)),patch('karaoke_ctc.refine_ctc',side_effect=refine):
            report=recover_row_boundaries('song.wav',rows)
        self.assertEqual(report['row_boundary_repairs'],1)
        self.assertEqual(len(calls),2)
        self.assertTrue(all(len(pair)==2 and not options.get('independent_rows',False) for pair,options in calls))

    def test_failed_models_leave_suspected_handoff_visible_for_review(self):
        rows=fixture();before=copy.deepcopy(rows)
        with patch('soundfile.info',return_value=SimpleNamespace(duration=243)),patch('karaoke_ctc.refine_ctc',side_effect=RuntimeError('unavailable')):
            report=recover_row_boundaries('song.wav',rows)
        self.assertEqual(report['row_boundary_repairs'],0)
        self.assertEqual(report['row_boundary_review_rows'],[3])
        self.assertTrue(rows[2]['words'][0]['needs_review'])
        rows[2]['words'][0]['needs_review']=False
        self.assertEqual(rows,before,'uncertain timing is flagged, never guessed')


if __name__=='__main__':unittest.main()
