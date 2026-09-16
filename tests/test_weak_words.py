import copy
import unittest
from karaoke_syllables import recover_weak_words

class WeakWordTests(unittest.TestCase):
    def words(self):
        return [{'word':'GEL','start':85.5757,'end':85.77636,'probability':.79,'timing_source':'ctc'},
                {'word':'EZO','start':86.11747,'end':86.45859,'probability':.332,'timing_source':'ctc'}]
    def test_real_ezo_fixture_recovered_without_changing_anchor(self):
        words=self.words();snapshot=copy.deepcopy(words)
        def align(path,rows,language,**options):
            self.assertEqual(rows[0]['text'],'EZO');self.assertEqual(rows[0]['start'],words[0]['end'])
            self.assertEqual(rows[0]['end'],88.68589);self.assertEqual(options['context_padding'],0)
            return [{'words':[{'word':'EZO','start':85.83655,'end':86.37832,'probability':.511,'timing_source':'ctc'}]}]
        result=recover_weak_words('',words,83.3685,88.68589,align)
        self.assertEqual(words,snapshot);self.assertEqual(result[0],snapshot[0])
        self.assertEqual(result[1]['probability'],.511);self.assertTrue(result[1]['needs_review'])
    def test_other_occurrence_or_low_confidence_is_rejected(self):
        for start,end,score in [(87.5,88,.9),(85.5,86.4,.9),(86.1,86.4,.3)]:
            words=self.words()
            def align(*args,**kw):return [{'words':[{'word':'EZO','start':start,'end':end,'probability':score,'timing_source':'ctc'}]}]
            self.assertEqual(recover_weak_words('',words,83.3685,88.68589,align),words)
    def test_no_reliable_anchor_does_not_retry(self):
        words=self.words()[1:]
        self.assertEqual(recover_weak_words('',words,83,89,lambda *a,**kw:self.fail()),words)

    def test_row_30_moderate_retry_agrees_with_weak_occurrence(self):
        words=[{'word':'GEL','start':278.254667,'end':278.415323,'probability':.995,'timing_source':'ctc'},
               {'word':'EZO','start':278.877209,'end':279.098111,'probability':.02077,'timing_source':'ctc'}]
        def align(*args,**kw):return [{'words':[{'word':'EZO','start':278.45547,'end':279.078016,'probability':.32697,'timing_source':'ctc'}]}]
        result=recover_weak_words('',words,276.206321,281.226824,align)
        self.assertEqual(result[0],words[0])
        self.assertEqual(result[1]['start'],278.45547)
        self.assertTrue(result[1]['needs_review'])
        for start,end,source in [(280,280.5,'ctc'),(278.877209,279.098111,'estimated')]:
            original=copy.deepcopy(words);original[1].update(start=start,end=end,timing_source=source)
            self.assertEqual(recover_weak_words('',original,276.206321,281.226824,align),original)

if __name__=='__main__':unittest.main()
