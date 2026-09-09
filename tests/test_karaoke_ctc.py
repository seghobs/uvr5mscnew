import unittest
from types import SimpleNamespace as Span
from karaoke_ctc import normalized_words, words_from_spans


class CharacterAlignmentTests(unittest.TestCase):
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
