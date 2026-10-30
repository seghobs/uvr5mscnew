import copy
import unittest

from karaoke_quality import checked_refinement,quality_report
from task_cancellation import TaskCancelled


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.rows=[{'id':'a','text':'SÖZ','start':1.,'end':2.,'words':[
            {'word':'SÖZ','start':1.,'end':2.,'timing_source':'ctc','needs_review':False}]}]

    def test_stage_failure_cannot_leave_partial_changes(self):
        before=copy.deepcopy(self.rows);report={}
        def fail(rows):rows[0]['words'][0]['end']=5;raise RuntimeError('model unavailable')
        self.assertIsNone(checked_refinement(self.rows,10,'retry',fail,report))
        self.assertEqual(self.rows,before);self.assertEqual(report['refinement_warnings'][0]['stage'],'retry')

    def test_new_overlap_invalid_bounds_text_changes_and_manual_edits_rollback(self):
        for kind in ('overlap','bounds','text','manual','locked','delete'):
            rows=copy.deepcopy(self.rows)
            rows.append({'id':'b','text':'SON','start':3.,'end':4.,'words':[{'word':'SON','start':3.,'end':4.}]})
            if kind=='manual':rows[0]['words'][0]['timing_source']='manual'
            if kind=='locked':rows[0]['locked']=True
            before=copy.deepcopy(rows);report={}
            def bad(candidate):
                if kind=='overlap':candidate[1]['words'][0]['start']=1.5
                elif kind=='bounds':candidate[1]['words'][0]['end']=float('nan')
                elif kind=='text':candidate[0]['text']='YENİ'
                elif kind=='delete':candidate.pop(0)
                else:candidate[0]['words'][0]['end']=1.9
            self.assertIsNone(checked_refinement(rows,10,kind,bad,report),kind)
            self.assertEqual(rows,before,kind)

    def test_valid_repair_commits_but_estimation_is_never_reported_as_verified(self):
        def fix(rows):rows[0]['words'][0].update(timing_source='repeat_inferred');return {'fixed':1}
        self.assertEqual(checked_refinement(self.rows,10,'repeat',fix,{}),{'fixed':1})
        result=quality_report(self.rows,10)
        self.assertEqual(result['status'],'estimated');self.assertEqual(len(result['estimated_words']),1)
        self.assertFalse(result['accuracy_guaranteed'])

    def test_missing_and_review_words_are_not_hidden(self):
        self.rows[0]['words'][0].update(start=0,end=0,needs_review=True,timing_source='estimated')
        result=quality_report(self.rows,10)
        self.assertEqual(result['status'],'needs_review');self.assertEqual(len(result['missing_words']),1)
        self.assertEqual(len(result['review_words']),1)

    def test_cancellation_is_never_swallowed_as_model_failure(self):
        def cancelled(_):raise TaskCancelled()
        with self.assertRaises(TaskCancelled):checked_refinement(self.rows,10,'cancel',cancelled,{})


if __name__=='__main__':unittest.main()
