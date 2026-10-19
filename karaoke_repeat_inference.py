"""Bounded, explicitly labelled timing estimates from this song's measured words.

This is a playback fallback, not acoustic verification. Frozen references prevent
estimates from becoming evidence for further estimates in this or later runs.
"""
import copy
import math
import statistics
import unicodedata

from karaoke_tail_recovery import confirmed


def token_key(text):
    # Preserve Kurdish circumflexes and Turkish dotless i; ignore punctuation.
    text = unicodedata.normalize('NFC', text).replace('İ', 'i').replace('I', 'ı').casefold()
    return ''.join(c for c in text if unicodedata.category(c)[0] in 'LMN')


def measured(word):
    probability = word.get('probability')
    return (confirmed(word) and word['end'] - word['start'] <= 3 and
            (word.get('timing_source') == 'manual' or
             isinstance(probability, (int, float)) and math.isfinite(probability) and probability >= .5))


def pace(words):
    # Median centre-to-centre word spacing is less brittle than tiny CTC spans.
    values = []
    for left, right in zip(words, words[1:]):
        if measured(left) and measured(right):
            delta = (right['start'] + right['end'] - left['start'] - left['end']) / 2
            if .08 <= delta <= 1.5:
                values.append(delta)
    return statistics.median(values) if values else None


def infer_repeated_words(rows, duration, energy, duration_only=False):
    """Mutate only uncertain isolated words; energy(a,b) returns vocal RMS.

    Same-phrase estimates use two measured neighbouring anchors. Otherwise use
    robust same-word duration/position statistics in a short bounded local gap.
    Leading/trailing words require two measured words on the available side.
    Never bridge a long break, rewrite lyrics, or clear a manual/locked timing.
    """
    from karaoke_supplied_alignment import instrumental, protected
    snapshot = copy.deepcopy(rows)
    references = {}
    for ri, row in enumerate(snapshot):
        if instrumental(row):
            continue
        words = row.get('words') or []
        for wi, word in enumerate(words):
            key = token_key(word['word'])
            if not key or not measured(word) or word['end'] > duration:
                continue
            level = energy(word['start'], word['end'])
            nearby = energy(max(0, word['start']-.1), min(duration, word['end']+.1))
            if math.isfinite(level) and math.isfinite(nearby) and level >= max(.0001, nearby*.12):
                references.setdefault(key, []).append((ri, wi, word))
    count = 0
    for ri, row in enumerate(rows):
        if protected(row) or instrumental(row):
            continue
        original = snapshot[ri].get('words') or []
        words = row.get('words') or []
        if len(words) != len(row['text'].split()):
            continue
        for wi, word in enumerate(original):
            if confirmed(word) or word.get('timing_source') in ('manual', 'repeat_inferred'):
                continue
            refs = references.get(token_key(word['word']), [])
            refs = [(r, j, w) for r, j, w in refs if (r, j) != (ri, wi)]
            if not refs:
                continue
            left = original[wi-1] if wi else None
            right = original[wi+1] if wi+1 < len(original) else None
            # Do not guess runs of missing words, or cross another uncertain word.
            if (left is not None and not measured(left)) or (right is not None and not measured(right)):
                continue
            anchor_count = int(left is not None) + int(right is not None)
            durations = [w['end']-w['start'] for _, _, w in refs]
            nominal = statistics.median(durations)
            if nominal <= 0:
                continue
            previous_row_end = max((r['end'] for r in snapshot[:ri]), default=0.)
            next_row_start = min((r['start'] for r in snapshot[ri+1:]), default=duration)
            if left is None:
                if len(original) < 3 or not all(measured(w) for w in original[1:3]):
                    continue
                anchor_count = 2
            if right is None:
                if len(original) < 3 or not all(measured(w) for w in original[-3:-1]):
                    continue
                anchor_count = 2
            lower = left['end'] if left else max(previous_row_end, right['start']-min(.65, nominal*2+.2))
            upper = right['start'] if right else min(next_row_start, duration, left['end']+min(.65, nominal*2+.2))
            # Borrow a duration, never a donor's position on the song clock.
            # Also bound interior words by neighbouring rows, even in stale drafts.
            lower = max(lower, previous_row_end)
            upper = min(upper, next_row_start, duration)
            max_gap = max(1.5, min(2., nominal*1.5)) if duration_only else 1.5
            if not (0 <= lower < upper <= duration) or not .02 <= upper-lower <= max_gap:
                continue
            proposals = []
            row_keys = [token_key(w['word']) for w in original]
            for r, j, ref in refs:
                if duration_only:
                    continue
                ref_words = snapshot[r].get('words') or []
                if (j != wi or [token_key(w['word']) for w in ref_words] != row_keys
                        or left is None or right is None
                        or not measured(ref_words[j-1]) or not measured(ref_words[j+1])):
                    continue
                a, b = ref_words[j-1]['end'], ref_words[j+1]['start']
                if b <= a:
                    continue
                scale = (upper-lower)/(b-a)
                if .65 <= scale <= 1.5 and a <= ref['start'] < ref['end'] <= b:
                    proposals.append((lower+(ref['start']-a)*scale, lower+(ref['end']-a)*scale, r))
            method = 'same_word_local_tempo'
            used = refs
            if proposals:
                starts, ends = [p[0] for p in proposals], [p[1] for p in proposals]
                if max(starts)-min(starts) > .20 or max(ends)-min(ends) > .25:
                    continue
                start, end = statistics.median(starts), statistics.median(ends)
                method = 'matching_phrase_anchors'
                used = [ref for ref in refs if ref[0] in {p[2] for p in proposals}]
            else:
                target_pace = pace(original[max(0, wi-3):wi+4])
                lengths, positions = [], []
                for r, j, ref in refs:
                    rw = snapshot[r]['words']
                    ref_pace = pace(rw[max(0, j-3):j+4])
                    scale = max(.7, min(1.4, target_pace/ref_pace)) if target_pace and ref_pace and not duration_only else 1.
                    lengths.append((ref['end']-ref['start'])*scale)
                    if 0 < j < len(rw)-1 and measured(rw[j-1]) and measured(rw[j+1]):
                        a, b = rw[j-1]['end'], rw[j+1]['start']
                        if a <= ref['start'] < ref['end'] <= b and .02 <= b-a <= 1.5:
                            positions.append(((ref['start']+ref['end'])/2-a)/(b-a))
                length = statistics.median(lengths)
                # Strongly differing pronunciations must not be averaged blindly.
                if len(lengths) > 2:
                    ordered = sorted(lengths)
                    if ordered[int(.75*(len(ordered)-1))] > 3*max(.02, ordered[int(.25*(len(ordered)-1))]):
                        continue
                # Do not squeeze a measured duration into an unrelated tiny gap.
                if length > upper-lower+1e-7:
                    continue
                length = min(length, upper-lower)
                if length < .019:
                    continue
                if lower <= word.get('start', -1) < word.get('end', -1) <= upper:
                    centre = (word['start']+word['end'])/2
                else:
                    fraction = statistics.median(positions) if positions and not duration_only else .5
                    centre = lower+(upper-lower)*fraction
                # Choose a voiced local window near the rhythmic prediction.
                # This locates sound, not a phoneme: it remains labelled inferred.
                radius = min(.16, (upper-lower)/3)
                candidates = []
                for step in range(-8, 9):
                    c = max(lower+length/2, min(upper-length/2, centre+step*radius/8))
                    a, b = c-length/2, c+length/2
                    level = energy(a, b)
                    if math.isfinite(level):
                        score = level*math.exp(-.5*((c-centre)/max(.04, radius))**2)
                        candidates.append((score, a, b))
                if not candidates:
                    continue
                _, start, end = max(candidates)
            start, end = max(lower, start), min(upper, end)
            local_level = energy(max(0, lower-.2), min(duration, upper+.2))
            level = energy(start, end)
            if not (all(math.isfinite(v) for v in (start, end, level, local_level)) and
                    .019 <= end-start <= 3 and level >= max(.0001, local_level*.12)):
                continue
            words[wi] = {**word, 'start':start, 'end':end, 'timing_source':'repeat_inferred',
                         'probability':None, 'needs_review':False,
                         'timing_reference':{'method':method, 'anchor_words':anchor_count,
                             'row_ids':list(dict.fromkeys(snapshot[r].get('id') or f'row:{r+1}' for r, _, _ in used)),
                             'bounds':[lower, upper], 'reference_count':len(used),
                             'acoustically_verified':False,
                             'duration_only':duration_only, 'reference_duration_seconds':nominal,
                             'previous_start':word.get('start'), 'previous_end':word.get('end')}}
            count += 1
        valid = [w for w in words if w['end'] > w['start']]
        if valid:
            row['start'] = min(row['start'], valid[0]['start'])
            row['end'] = max(row['end'], valid[-1]['end'])
    return count


def recover_from_song_repeats(audio_path, rows, duration_only=True):
    import numpy as np
    import soundfile as sf
    audio, rate = sf.read(str(audio_path), dtype='float32', always_2d=True)
    # Average channel power avoids stereo phase cancellation; invalid audio is not evidence.
    power = np.mean(np.square(audio.astype('float64')), axis=1)
    invalid = np.cumsum(np.r_[0, ~np.isfinite(power)])
    cumulative = np.cumsum(np.r_[0., np.where(np.isfinite(power), power, 0.)])
    def energy(start, end):
        a, b = max(0, round(start*rate)), min(len(audio), round(end*rate))
        if b <= a or invalid[b] != invalid[a]:
            return math.nan
        return math.sqrt(max(0., (cumulative[b]-cumulative[a])/(b-a)))
    return infer_repeated_words(rows, len(audio)/rate, energy, duration_only=duration_only)
