"""Archive an excess supplied repeat only inside an acoustically closed gap."""
import copy
import math


def archive_excess_repeats(rows, selected, vocab):
    from karaoke_repeat_spotting import text_key
    from karaoke_supplied_alignment import protected
    matched = {h['source_index']: h for h in selected if h['kind'] == 'original'}
    keys = [text_key(r, vocab) for r in rows]
    removed = set()
    archives = {}
    i = 0
    while i < len(rows):
        if i in matched:
            i += 1
            continue
        first = i
        while i < len(rows) and i not in matched:
            i += 1
        last = i
        # Missing recognition alone is not evidence of an excess verse. Require
        # a complete repeated block trapped between two touching acoustic hits.
        if not (2 <= last-first <= 8 and first-1 in matched and last in matched):
            continue
        left, right = matched[first-1], matched[last]
        edges = [(left.get('words') or [{}])[-1], (right.get('words') or [{}])[0]]
        if any((w.get('probability') or 0) < .5 or not 0 < w.get('end', 0)-w.get('start', 0) <= 3 for w in edges):
            continue
        bounds = [left['end'], right['start']]
        if not all(math.isfinite(t) for t in bounds) or not -.4 <= bounds[1]-bounds[0] <= .25:
            continue
        candidates = rows[first:last]
        if any(protected(r) or r.get('repeat_cleanup') or any(
                w.get('timing_source') == 'manual' and w['end'] > w['start']
                for w in r.get('words') or []) for r in candidates):
            continue
        # Each missing line must have a distinct, ordered acoustic counterpart
        # in another complete block. Neither a single-word match nor a fuzzy
        # text similarity can authorize removing supplied text.
        reference = next((j for j in range(len(rows)-(last-first)+1)
                          if (j+last-first <= first or j >= last)
                          and keys[j:j+last-first] == keys[first:last]
                          and all(k in matched and matched[k].get('confidence', 0) >= .5
                                  for k in range(j, j+last-first))), None)
        if reference is None or any(not r.get('id') for r in candidates + rows[reference:reference+last-first]):
            continue
        entries = []
        for offset, row in enumerate(candidates):
            snapshot = {k: copy.deepcopy(v) for k, v in row.items() if not k.startswith('_')}
            entries.append({'row': snapshot, 'matched_row_id': rows[reference+offset].get('id'),
                            'bounds': bounds, 'reason': 'duplicate_block_without_audio_gap'})
        archives.setdefault(last, []).extend(entries)
        removed.update(range(first, last))
    result = []
    for index, row in enumerate(rows):
        if index in removed:
            continue
        row = copy.deepcopy(row)
        if index in archives:
            row['repeat_cleanup'] = list(row.get('repeat_cleanup') or []) + archives[index]
        result.append(row)
    return result, len(removed)
