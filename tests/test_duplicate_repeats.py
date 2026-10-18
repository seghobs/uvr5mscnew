import copy
import unittest
from karaoke_duplicate_repeats import archive_excess_repeats
from tests.test_repeat_spotting import VOCAB, evidence


class DuplicateRepeatsTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{'id': str(i), 'text': text, 'start': i, 'end': i+.5, 'words': []}
                     for i, text in enumerate(['BASLA', 'GEL BANA', 'DON YINE', 'GEL BANA', 'DON YINE', 'SON'])]
        self.hits = [{'source_index': i, 'kind': 'original', 'start': start, 'end': end, 'confidence': .9,
                      'words': [{'start': start, 'end': end, 'probability': .9}]}
                     for i, start, end in [(0, 0, 2), (3, 2.1, 4), (4, 4.1, 6), (5, 6.1, 8)]]

    def test_closed_gap_archives_only_exact_unmatched_block_losslessly(self):
        before = copy.deepcopy(self.rows)
        result, count = archive_excess_repeats(self.rows, self.hits, VOCAB)
        self.assertEqual(count, 2)
        self.assertEqual(self.rows, before)
        self.assertEqual([r['id'] for r in result], ['0', '3', '4', '5'])
        self.assertEqual([e['row'] for e in result[1]['repeat_cleanup']], before[1:3])
        self.assertEqual([e['matched_row_id'] for e in result[1]['repeat_cleanup']], ['3', '4'])

    def test_open_audio_gap_cannot_be_called_an_excess_repeat(self):
        self.hits[1]['start'] = 3
        self.assertEqual(archive_excess_repeats(self.rows, self.hits, VOCAB)[1], 0)

    def test_uncertain_boundary_cannot_authorize_removal(self):
        self.hits[0]['words'][-1]['probability'] = .2
        self.assertEqual(archive_excess_repeats(self.rows, self.hits, VOCAB)[1], 0)

    def test_unique_text_or_single_missing_line_is_preserved(self):
        self.rows[1]['text'] = 'BASKA BANA'
        self.assertEqual(archive_excess_repeats(self.rows, self.hits, VOCAB)[1], 0)
        self.rows[1]['text'] = 'GEL BANA'
        self.hits.append({'source_index': 1, 'kind': 'original', 'start': .3, 'end': 2})
        self.assertEqual(archive_excess_repeats(self.rows, self.hits, VOCAB)[1], 0)

    def test_manual_locked_and_existing_archive_are_never_removed(self):
        for change in [{'locked': True}, {'words': [{'word': 'GEL', 'start': 1, 'end': 2, 'timing_source': 'manual'}]},
                       {'repeat_cleanup': [{'row': {}}]}]:
            rows = copy.deepcopy(self.rows)
            rows[1].update(change)
            self.assertEqual(archive_excess_repeats(rows, self.hits, VOCAB)[1], 0)

    def test_actual_ctc_duplicate_removal_and_second_run_are_idempotent(self):
        from karaoke_repeat_spotting import expand_supplied_rows
        audio = evidence(['basla', 'gel bana', 'don yine', 'son'])
        # Small CTC silence between the anchors is required for this safeguard.
        # Use selected real occurrences to reproduce the observed closed gap.
        from unittest.mock import patch
        with patch('karaoke_repeat_spotting.select_occurrences', side_effect=[self.hits, []]):
            result, report, _ = expand_supplied_rows(self.rows, audio, VOCAB)
        self.assertEqual(report['archived_duplicate_rows'], 2)
        again, count = archive_excess_repeats(result, [], VOCAB)
        self.assertEqual(count, 0)
        self.assertEqual(again, result)

    def test_real_repeated_blocks_with_occurrences_are_all_retained(self):
        self.hits.extend([{'source_index': i, 'kind': 'original', 'start': i, 'end': i+.5} for i in (1, 2)])
        self.assertEqual(archive_excess_repeats(self.rows, self.hits, VOCAB), (self.rows, 0))
