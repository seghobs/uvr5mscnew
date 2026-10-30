"""Boundary evaluation with explicit reference provenance and recording identity."""
import math
import statistics
from karaoke_syllable_timing import text_key


def score_alignment(reference,prediction,tolerance=.08):
    kind=reference.get('reference_kind')
    if kind not in ('human_verified','acoustic_consensus','synthetic'):
        raise ValueError('Reference provenance is required')
    if not math.isfinite(tolerance) or tolerance<=0:raise ValueError('Invalid tolerance')
    expected_hash=reference.get('audio_sha256');actual_hash=prediction.get('audio_sha256')
    if kind=='human_verified' and (not expected_hash or not actual_hash):raise ValueError('Verified references require recording hashes')
    if expected_hash!=actual_hash:raise ValueError('Different audio recordings cannot share a timing benchmark')
    def indexed(document):
        result={}
        for ri,row in enumerate(document.get('segments',[])):
            for wi,word in enumerate(row.get('words') or []):
                identity=(row.get('id') or f'row:{ri}',wi)
                if identity in result:raise ValueError('Duplicate reference/prediction identity')
                result[identity]=word
        return result
    expected=indexed(reference);actual=indexed(prediction)
    starts=[];ends=[];misses=[];wrong=[];within=0
    for key,word in expected.items():
        if not all(isinstance(word.get(k),(int,float)) and math.isfinite(word[k]) for k in ('start','end')) or not 0<=word['start']<word['end']:
            raise ValueError('Reference contains an unlocated or invalid word')
        found=actual.get(key)
        if found is None or not all(isinstance(found.get(k),(int,float)) and math.isfinite(found[k]) for k in ('start','end')) or not 0<=found['start']<found['end']:
            misses.append(list(key));continue
        if text_key(found['word'])!=text_key(word['word']):wrong.append(list(key));continue
        a=abs(found['start']-word['start']);b=abs(found['end']-word['end'])
        starts.append(a);ends.append(b);within+=int(a<=tolerance and b<=tolerance)
    errors=sorted(starts+ends)
    return {'reference_kind':kind,'human_accuracy_measured':kind=='human_verified','accuracy_guaranteed':False,
            'reference_words':len(expected),'matched_words':len(starts),'missing_words':misses,'wrong_words':wrong,
            'extra_words':[list(k) for k in actual if k not in expected],
            'onset_mae_seconds':statistics.mean(starts) if starts else None,
            'offset_mae_seconds':statistics.mean(ends) if ends else None,
            'boundary_p95_seconds':errors[max(0,math.ceil(.95*len(errors))-1)] if errors else None,
            'tolerance_seconds':tolerance,'words_within_tolerance':within,
            'within_tolerance_fraction':within/len(expected) if expected else None}
