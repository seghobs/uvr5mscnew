import copy
import random
import re
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from karaoke_timing import ass_time, ass_word_tags, centiseconds, timing_issues, align_lyrics, repair_timing


def segment(words, start=None, end=None):
    return {"start": words[0][1] if start is None else start,
            "end": words[-1][2] if end is None else end,
            "text": " ".join(w[0] for w in words),
            "words": [{"word": w, "start": s, "end": e} for w, s, e in words]}


def ass_intervals(seg):
    cursor = centiseconds(seg['start'])
    intervals = []
    for tag, duration in re.findall(r'\\(kf|k)(\d+)', ass_word_tags(seg)):
        duration = int(duration)
        if tag == 'kf':
            intervals.append((cursor, cursor + duration))
        cursor += duration
    return intervals


class TimingTests(unittest.TestCase):
    def test_automatic_repair_is_bounded_lossless_and_idempotent(self):
        original = [segment([('DUR',85,91.6)]), segment([('AY',91.59997732426304,92)])]
        original[0]['words'][0]['needs_review'] = True
        before = copy.deepcopy(original)
        repaired = repair_timing(original)
        self.assertEqual(repaired[0]['words'][0]['end'],original[1]['words'][0]['start'])
        self.assertEqual(original,before)
        self.assertTrue(repaired[0]['words'][0]['needs_review'])
        self.assertEqual(repair_timing(repaired),repaired)
        self.assertFalse(timing_issues(repaired,include_review=False))
        original[1]['words'][0]['start'] = 91.5
        self.assertEqual(repair_timing(original)[0]['words'][0]['end'],91.6)
        self.assertTrue(timing_issues(repair_timing(original),include_review=False))

    def test_repair_expands_envelope_without_moving_words_or_filling_gaps(self):
        original = [segment([('BİR',4,5),('İKİ',7,8)],5,7)]
        fixed = repair_timing(original)
        self.assertEqual(fixed[0]['words'],original[0]['words'])
        self.assertEqual((fixed[0]['start'],fixed[0]['end']),(4,8))
        self.assertEqual(repair_timing([segment([('X',4,4)])])[0]['words'][0]['end'],4)

    def test_preserves_leading_trailing_silence(self):
        seg = segment([('Bir', 10.4, 11), ('iki', 11.5, 12.5)], 10, 13)
        before = copy.deepcopy(seg)
        self.assertEqual(ass_intervals(seg), [(1040, 1100), (1150, 1250)])
        self.assertEqual(seg, before)

    def test_short_and_long_gaps_are_not_removed(self):
        for gap in (0.01, 0.05, 0.079, 0.08, 0.6, 1.2, 5.0):
            seg = segment([('Bir', 10, 11), ('iki', 11 + gap, 12 + gap)])
            self.assertEqual(ass_intervals(seg)[1][0], centiseconds(11 + gap))

    def test_single_word_does_not_fill_line_padding(self):
        self.assertEqual(ass_intervals(segment([('uzun', 2.2, 4.5)], 1, 6)), [(220, 450)])

    def test_ceiling_never_starts_early(self):
        self.assertEqual(ass_time(59.999), '0:01:00.00')
        self.assertEqual(ass_time(10.001), '0:00:10.01')

    def test_random_timeline_has_no_cumulative_drift(self):
        rng = random.Random(5)
        for _ in range(500):
            time = rng.randint(0, 500000) / 1000
            words = []
            for i in range(20):
                start = round(time + rng.randint(0, 5000) / 1000, 3)
                end = round(start + rng.randint(1, 9000) / 1000, 3)
                words.append((str(i), start, end)); time = end
            seg = segment(words)
            self.assertEqual(ass_intervals(seg), [(centiseconds(s), centiseconds(e)) for _, s, e in words])

    def test_invalid_timings_cannot_render(self):
        for ws in ([('a', 1, 1)], [('a', 1, .9)], [('a', 1, 2), ('b', 1.9, 3)]):
            with self.assertRaises(ValueError): ass_word_tags(segment(ws))
        with self.assertRaises(ValueError):
            ass_word_tags({'start': 1, 'end': 2, 'text': 'missing', 'words': []})

    def test_cross_line_overlap_is_rejected(self):
        self.assertTrue(timing_issues([segment([('a', 1, 2)]), segment([('b', 1.9, 3)])]))

    def test_uncertain_word_renders_without_clearing_warning(self):
        seg = segment([('a', 1, 2)]); seg['words'][0]['needs_review'] = True
        self.assertTrue(timing_issues([seg]))
        self.assertFalse(timing_issues([seg], include_review=False))
        self.assertEqual(ass_intervals(seg), [(100, 200)])
        self.assertTrue(seg['words'][0]['needs_review'])
        seg['words'][0]['timing_source'] = 'estimated'
        with self.assertRaises(ValueError): ass_word_tags(seg)

    def test_text_edits_require_alignment(self):
        seg = segment([('a', 1, 2)]); seg['text'] = 'a b'
        self.assertTrue(timing_issues([seg]))

    def test_escape_cannot_inject_karaoke_commands(self):
        tags = ass_word_tags(segment([(r'{\kf1}x', 1, 2)]))
        self.assertEqual(len(re.findall(r'\\kf', tags)), 1)

    def test_full_pasted_text_reaches_aligner(self):
        text = ' '.join(['kelime'] * 100)
        words = [{'word': w, 'start': i, 'end': i + .5, 'probability': .99} for i, w in enumerate(text.split())]
        result = SimpleNamespace(to_dict=lambda: {'segments': [{'words': words}]})
        with patch.dict('sys.modules', {'stable_whisper.alignment': SimpleNamespace(align=lambda model, audio, supplied, **kw: result if supplied == text else None)}):
            actual = align_lyrics(None, 'local.wav', text, 'tr')
        self.assertEqual(len(actual[0]['words']), 100)

    def test_missing_transcript_word_fails_without_silent_truncation(self):
        result = SimpleNamespace(to_dict=lambda: {'segments': [{'words': [{'word': 'a', 'start': 1, 'end': 2}]}]})
        with patch.dict('sys.modules', {'stable_whisper.alignment': SimpleNamespace(align=lambda *a, **kw: result)}):
            with self.assertRaises(ValueError): align_lyrics(None, 'local.wav', 'a b', 'tr')


if __name__ == '__main__': unittest.main()
