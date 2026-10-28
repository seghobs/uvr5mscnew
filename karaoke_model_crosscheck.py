"""Corroborate weak word boundaries on the vocal AND the original recording."""
from karaoke_ctc import has_timed_row
import copy
import math
from pathlib import Path


def original_for_stem(stem, records):
    """Use recorded separation provenance, never guess from a song title."""
    paths = set()
    for task in records.values():
        if Path(stem).name not in [Path(s).name for s in task.get('stems', [])]:
            continue
        request = task.get('separation_request') or {}
        path = request.get('audio_path') or (request.get('request') or {}).get('audio_path')
        if path and Path(path).is_file():
            paths.add(Path(path).resolve())
    return next(iter(paths)) if len(paths) == 1 else None


def apply_crosscheck(rows, candidates, duration, targets=None, allow_manual=False):
    """Accept >= .5 evidence on both audio views within target neighbours."""
    repaired = []
    for ri, row in enumerate(rows):
        if row.get('locked'):
            continue
        words = row.get('words') or []
        for wi, word in enumerate(words):
            key = (row.get('id') or f'row:{ri+1}', wi)
            if targets is not None and key not in targets:
                continue
            if not word.get('needs_review') or (word.get('timing_source') == 'manual' and not allow_manual):
                continue
            # Even an interior word must stay inside the neighbouring rows.
            lower = max([0.] + [r['end'] for r in rows[:ri] if has_timed_row(r)] +
                        [w['end'] for w in words[:wi] if w['end'] > w['start']])
            upper = min([duration] + [r['start'] for r in rows[ri+1:] if has_timed_row(r)] +
                        [w['start'] for w in words[wi+1:] if w['end'] > w['start']])
            usable = []
            for proposal in candidates.get(key, []):
                a, b, p = proposal.get('start'), proposal.get('end'), proposal.get('probability')
                if (proposal.get('word') == word['word'] and not proposal.get('needs_review') and
                    all(isinstance(t, (int, float)) and math.isfinite(t) for t in (a, b, p)) and
                    p >= .5 and lower <= a < b <= upper and b-a <= 3 and
                    proposal.get('audio_source') in ('vocals', 'original')):
                    usable.append(proposal)
            pairs = [(a, b) for a in usable for b in usable
                     if a['audio_source'] == 'vocals' and b['audio_source'] == 'original'
                     and abs(a['start']-b['start']) <= .16 and abs(a['end']-b['end']) <= .16]
            if not pairs:
                continue
            pair = max(pairs, key=lambda pair: min(w['probability'] for w in pair))
            a, b = pair
            words[wi] = {**word, 'start': (a['start']+b['start'])/2, 'end': (a['end']+b['end'])/2,
                         'probability': min(a['probability'], b['probability']),
                         'timing_source': 'ctc', 'needs_review': False,
                         'timing_reference': {'method': 'dual_audio_model_consensus',
                            'row_ids': [key[0]], 'anchor_words': 2,
                            'bounds': [lower, upper], 'acoustically_verified': True,
                            'previous_start': word['start'], 'previous_end': word['end'],
                            'previous_probability': word.get('probability'),
                            'evidence': [copy.deepcopy(w) for w in pair]}}
            repaired.append(key)
        valid = [w for w in words if w['end'] > w['start']]
        if valid:
            row['start'] = min(row['start'], valid[0]['start'])
            row['end'] = max(row['end'], valid[-1]['end'])
    return repaired


def recover_model_reviews(vocal_path, original_path, rows, progress=lambda *args: None,
                          targets=None, allow_manual=False, diagnostics=None, language='tr'):
    import soundfile as sf
    from karaoke_ctc import refine_ctc
    from karaoke_alignment_models import model_spec
    report = {'dual_audio_repaired_words': 0, 'original_audio_crosscheck': False}
    if not original_path or not Path(original_path).is_file():
        return report
    duration = sf.info(str(vocal_path)).duration
    # A different edit/version cannot corroborate absolute song positions.
    if abs(sf.info(str(original_path)).duration-duration) > .05:
        report['original_audio_crosscheck_skipped'] = 'different_audio_duration'
        return report
    pending = {(r.get('id') or f'row:{ri+1}', i) for ri,r in enumerate(rows) if not r.get('locked') for i, w in enumerate(r.get('words') or [])
               if w.get('needs_review') and (allow_manual or w.get('timing_source') != 'manual')}
    if targets is not None:
        pending &= set(targets)
    if not pending:
        return report
    report['original_audio_crosscheck'] = True
    frozen = copy.deepcopy(rows)
    for ri,row in enumerate(frozen):row['_crosscheck_row_key']=row.get('id') or f'row:{ri+1}'
    candidates = {}
    failed_models = set()
    models = {'tr': ('tr_cv8', 'tr_mms'), 'kmr': ('kmr_mms', 'kmr'), 'az': ('az',), 'en': ('en_lv60', 'en')}[language]
    from karaoke_inference import RefinementSession
    with RefinementSession() as session:
        for local in (False, True):
            for language in models:
                if language in failed_models:
                    continue
                for padding in ((.15, .35, .7) if local else (.25, 1.4)):
                    for channel in (('left', 'right') if local else ('mix', 'left', 'right')):
                        if not pending or language in failed_models:
                            break
                        selected = []
                        for row in frozen:
                            indices = [j for j in range(len(row.get('words') or [])) if (row['_crosscheck_row_key'], j) in pending]
                            if not indices:
                                continue
                            first, last = (max(0, min(indices)-1), min(len(row['words']), max(indices)+2)) if local else (0, len(row['words']))
                            item = copy.deepcopy(row)
                            item['words'] = item['words'][first:last]
                            item['_crosscheck_indices'] = list(range(first, last))
                            if local:
                                item['text'] = ' '.join(w['word'] for w in item['words'])
                                good = [w for w in item['words'] if w['end'] > w['start']]
                                if good:
                                    item['start'], item['end'] = good[0]['start'], good[-1]['end']
                            selected.append(item)
                        for name, path in (('vocals', vocal_path), ('original', original_path)):
                            label=f'İkinci model · {language} · {name} · {channel} · {len(pending)} belirsiz kelime'
                            progress(.99,label)
                            try:
                                refined = refine_ctc(str(path), selected, language,
                                                     progress=lambda p,message:progress(.99,label+' · '+message),context_padding=padding,
                                                     channel=channel, independent_rows=True,session=session)
                            except Exception as exc:
                                # This supplementary check must not discard an
                                # otherwise completed alignment when unavailable.
                                failed_models.add(language)
                                report.setdefault('model_crosscheck_errors', []).append({
                                    'model': model_spec(language)[1], 'error': str(exc)})
                                break
                            for row in refined:
                                for wi, word in enumerate(row.get('words') or []):
                                    key = (row['_crosscheck_row_key'], row['_crosscheck_indices'][wi])
                                    if key in pending:
                                        candidates.setdefault(key, []).append({**word, 'audio_source': name,
                                            'model': model_spec(language)[1], 'model_revision': model_spec(language)[2],
                                            'channel': channel, 'padding': padding, 'local_phrase': local})
                        fixed = apply_crosscheck(rows, candidates, duration, pending, allow_manual)
                        pending -= set(fixed)
                        report['dual_audio_repaired_words'] += len(fixed)
    if diagnostics is not None:
        diagnostics['model_crosscheck_candidates'] = [
            {'row_id': key[0], 'word_index': key[1], 'candidates': value} for key, value in candidates.items()]
    report['dual_audio_review_words_remaining'] = len(pending)
    return report
