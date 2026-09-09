import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from karaoke_reference import compare_reference, youtube_id, search_reference, align_changed_rows


class ReferenceTests(unittest.TestCase):
    def test_repeated_chorus_is_not_deleted(self):
        rows = compare_reference([{'text': 'BİR GÜN GELİR'}, {'text': 'BİR GÜN GELİR'}], 'Bir gün gelir')
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(not r['changed'] for r in rows))

    def test_missing_verse_is_not_inserted_and_unmatched_stays(self):
        rows = compare_reference([{'text': 'abcdefgh xyz'}], 'Bir gün gelir sonra yeni bir gün doğar')
        self.assertEqual(rows[0]['proposed'], 'abcdefgh xyz')
        self.assertFalse(rows[0]['changed'])

    def test_split_word_correction(self):
        row = compare_reference([{'text': 'BİLMEM DERDİNE'}], 'bilmem derdi ne')[0]
        self.assertTrue(row['changed'])
        self.assertEqual(row['proposed'], 'bilmem derdi ne')

    def test_case_only_is_not_correction(self):
        self.assertFalse(compare_reference([{'text': 'İÇİM IŞIK'}], 'içim ışık')[0]['changed'])

    def test_url_restrictions(self):
        self.assertEqual(youtube_id('https://youtu.be/abcdefghijk'), 'abcdefghijk')
        for url in ('http://localhost/x', 'https://youtube.com.evil/x', 'https://youtube.com/watch?v=x'):
            with self.assertRaises(ValueError): youtube_id(url)

    def test_search_resolves_title_and_ignores_lrc_timestamps(self):
        search_reference.cache_clear()
        with patch('karaoke_reference._get_json', side_effect=[{'title': 'Artist - Track | Official Visualizer'},
                  [{'id': 1, 'artistName': 'Artist', 'trackName': 'Track', 'syncedLyrics': '[00:01.00]Bir gün'}]]) as get:
            result = search_reference('https://youtu.be/abcdefghijk')
            self.assertEqual(result['title'], 'Track')
            self.assertEqual(result['candidates'][0]['text'], 'Bir gün')
            self.assertIn('artist_name=Artist', get.call_args.args[0])
        search_reference.cache_clear()

    def test_local_alignment_preserves_neighbours_and_failure_is_atomic(self):
        import numpy as np
        import soundfile as sf
        def row(text, start, end):
            return {'text': text, 'start': start, 'end': end, 'words': [{'word': text, 'start': start, 'end': end, 'timing_source': 'manual'}]}
        segments = [row('bir', .1, .5), row('yanlis', 1, 1.5), row('son', 2, 2.5)]
        before = copy.deepcopy(segments)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'vocal.wav'; sf.write(path, np.zeros(3000), 1000)
            result = align_changed_rows(path, segments, {1: 'dogru'}, lambda p, t: [row(t, .1, .4)])
            self.assertEqual(result[0], before[0]); self.assertEqual(result[2], before[2])
            self.assertAlmostEqual(result[1]['start'], .75)
            with self.assertRaises(ValueError):
                align_changed_rows(path, segments, {1: 'dogru'}, lambda p, t: [row(t, .1, 99)])
            self.assertEqual(segments, before)


if __name__ == '__main__': unittest.main()
