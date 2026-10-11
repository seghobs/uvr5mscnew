# Atlas V2 — new architectures and ensemble methods

11 October 2026. This experiment compares against the deployed **nine-model**
Atlas Studio V2, SHA256
`dd8d1d265455b88843414ad6b4e341c15d54655bda05c469bced7748f7ccc7d6`.
The first independent confirmation failed. The more conservative refit passed a
second independent 16-record confirmation and is applied to Atlas Studio V2.

## Publisher research and actual model tests

| Expert | Pinned publisher revision | Runtime |
|---|---|---|
| [HyperACE V2 vocals](https://huggingface.co/pcunwa/BS-Roformer-HyperACE) | `5b1f8283125d5e4a3614d0e3635a636e09c84059` | Publisher HyperACE architecture |
| HyperACE V2 instrumental | Same revision | Publisher HyperACE architecture |
| [Large Inst V2](https://huggingface.co/pcunwa/BS-Roformer-Large-Inst) | `94ea5d723ef7aceeeb211472a7bb42ad6ce4ee0d` | Publisher mask-transformer architecture |
| [Siamese Roformer](https://huggingface.co/pcunwa/BS-EXP-SiameseRoformer) | `2042531f6f98ff5070124fec89dffbdd185877f9` | Publisher Siamese architecture |
| [MelBand Big beta7](https://huggingface.co/pcunwa/Mel-Band-Roformer-big) | `1508d1ed7c54cb0017b2cbfaabdaf3ca87d2cf74` | Compatible installed MelBand architecture |

All five were actually downloaded, checked against their published checkpoint
SHA256 and run on 16 development reference recordings: **80 completed expert
outputs**. Publisher code/configuration digests are recorded in local provenance.
Custom architectures retain every publisher model parameter; the only source
translation is the equivalent local `Attend` import location. Strict state-dict
loading rejects missing or unexpected weights. No installed package is modified.
Inference uses native model windows, batch one, overlap eight and float WAV.
An instrumental expert is converted to a vocal estimate exactly once by
subtracting its instrumental output from the original source.

Publisher scores on a different corpus cannot establish superiority here.
The Big model was substantially worse standalone on this development set;
additional model size alone did not produce higher quality.
The [MVSEP ensemble description](https://hk.mvsep.com/algorithms/10) also includes
SCNet XL IHF alongside BS and MelBand families. Its service recipe and scores
are research context, not models or results executed in this local experiment.

## Development methods

The first pool contains the four new BS experts. The second adds Big beta7.
For each pool, seven blend strengths were tried for new-expert mean, complex
median, magnitude median retaining baseline phase, disagreement weighting with
two powers, conservative local consensus, and energy-weighted mixture consistency.
Individual experts were also blended at those strengths.

The two screens evaluate **77 and 84 recipes**, respectively. These counts overlap:
the four individual-expert blends are reused. Neither screen produced a recipe
passing both stems' SDR/SI-SDR and all four mean spectral-content checks.

Four full-resolution constrained frequency fits followed: three regularization
strengths for 13 experts and one for 14 experts. Nonnegative weights sum to one
at every frequency anchor; the instrumental output remains `source - vocals`.
The optimization targets 1% lower values for all four spectral proxies and caps
each development recording's SDR regression at 0.03 dB. Actual reconstructed
waveform scores are checked after optimization; analytical spectral constraints
alone are not treated as final evidence.

The strongest eligible development recipe uses 13 experts and regularization
0.001. Mean SDR rises **0.1260 dB**. Vocal deficit changes **-9.31%**, instrumental
deficit **-1.02%**, vocal excess **-0.97%**, and instrumental excess **-5.15%**.
Instantaneous two-reference projection crosstalk proxies fall approximately
**6.40% for vocals and 9.38% for instrumental**. These are development results,
not an independent improvement claim. Big's 14-expert fit does not outperform it.

## Frozen independent acceptance

The selected recipe is frozen before selecting eight previously uncached
[MUSDB18 reference excerpts](https://github.com/sigsep/sigsep-mus-db).
Selection follows a fixed SHA256 order. The only eligibility filter is a
non-silent ground-truth reference for both stems (energy above 1e-8 of mixture);
no candidate quality is used in selection. The selected eight all pass this filter.

Acceptance requires:

- A positive lower endpoint of the paired **97.5% SDR bootstrap interval**.
- No mean SI-SDR regression in either channel.
- At least **1% lower mean spectral deficit in each channel**.
- No higher mean spectral excess in either channel.
- No higher mean instantaneous reference-projection crosstalk in either channel.

The last measure fits the estimate to both correlated true reference stems;
it measures the energy attributable to the opposite reference. It is an
additional crosstalk proxy, not a claim of perfect separation or a replacement
for BSS Eval. Candidate weights are never adjusted using this confirmation group.

## Limits

SDR is measured in **dB**, not percent. Relative deficit/excess reductions are
changes in error indicators, not percentages of audible words or instruments
recovered. Source-sum preservation does not prove correct source assignment.
Short excerpts and unknown pretrained-model training overlap do not establish
superiority on Turkish full songs. The local Turkish recordings have no true
studio stems and cannot serve as ground truth. No zero-loss guarantee is made.

## First independent confirmation — rejected

Eight fresh excerpts required 104 completed model outputs. Vocal SDR changes
from **13.9915 to 14.1732 dB** and instrumental SDR from **19.0702 to 19.2519 dB**:
mean gain **+0.1818 dB**, with seven of eight recordings improving. The paired
97.5% bootstrap interval is **[-0.0025, +0.4619] dB**, which includes zero.
Vocal deficit falls **6.61%**, instrumental deficit **2.15%**, and instrumental
excess **4.83%**, but vocal excess **increases 5.34%**. Reference-projection
crosstalk improves for both channels; that does not override the excess failure.
The candidate is rejected and the deployed preset is preserved.
[Complete first-round results](atlas-studio-v2-new-models.json).

These eight opened recordings are now explicitly development, giving 24 records.
The next full-resolution fit targets 5% lower mean vocal excess, 1% lower mean
instrumental excess and 1% lower mean deficit in each channel, using stronger
regularization 0.01 and a development-only warm start. A separate residual
shrinkage screen also checks both development groups individually. Any new
confirmation must use further previously uncached references and the same
predeclared independent acceptance criteria. Before selecting or generating any
second-round confirmation outputs, its fixed sample size was increased to **16**
to provide a more precise independent assessment. This size is not adjusted
based on second-round results.

The 24-record refit passes development checks: SDR **+0.1340 dB**, vocal deficit
**-6.47%**, instrumental deficit **-1.01%**, vocal excess **-4.94%**, and instrumental
excess **-4.41%**. Reference-projection crosstalk also improves in both channels.
All seven scalar residual shrinkage candidates failed the development checks;
they are not carried into independent confirmation.

## Second independent confirmation — accepted

Sixteen further previously uncached, non-silent two-stem references required
208 model outputs. No weights changed after these references were selected.

| Mean metric | Previous nine-expert V2 | Frozen thirteen-expert V2 | Change |
| --- | ---: | ---: | ---: |
| Vocal SDR | 13.0626 dB | 13.2936 dB | +0.2310 dB |
| Instrumental SDR | 17.0724 dB | 17.3034 dB | +0.2310 dB |
| Vocal SI-SDR | 12.8183 dB | 13.0627 dB | +0.2444 dB |
| Instrumental SI-SDR | 16.9647 dB | 17.2009 dB | +0.2362 dB |
| Vocal spectral deficit | 0.03424595 | 0.03213040 | -6.18% |
| Instrumental spectral deficit | 0.00964464 | 0.00935451 | -3.01% |
| Vocal spectral excess | 0.00648548 | 0.00585954 | -9.65% |
| Instrumental spectral excess | 0.00283931 | 0.00259255 | -8.69% |

The paired 97.5% SDR interval is **[+0.0775, +0.4207] dB**. Thirteen of sixteen
recordings improve; three have small SDR regressions, so this is an average
improvement, not a per-song guarantee. Mean reference-projection crosstalk falls
from 0.00191956 to 0.00188178 for vocals and 0.00325967 to 0.00312444 for instrumental.
All predeclared acceptance guards pass.
[Full second-round results and exact deployed recipe](atlas-studio-v2-new-models-round-two.json).

The accepted recipe retains the exact frozen expert order and frequency weights,
including small nonzero contributions. Four pinned publisher experts are added
to the previous nine. Expect longer processing and additional model downloads;
MelBand Big is not included. In total this research produced **392 valid expert
outputs**, completed **five constrained fits**, and screened seven additional
residual shrinkage candidates. The two simple/nonlinear screens evaluated 77 and
84 candidates, with overlap between screens; neither yielded an eligible recipe.

Production verifies publisher checkpoint, configuration, and architecture
SHA256 values before loading. Custom architecture parameters are retained;
only the Attend import path and inference metadata/output labels are translated.
Model construction uses a shared lock and restores the library class even when
loading fails. The stock library installation is unchanged.

## Production verification

All **42 relevant unit tests** passed, including checksum rejection, preservation
of custom architecture kwargs, restoration after loading errors, and the exact
deployed recipe's independent acceptance checks. The production build and
TypeScript check passed. The running frontend proxy reports all thirteen experts.

A three-second Turkish clip was processed through the real API with the actual
thirteen-expert preset. All experts loaded and completed; both float WAV outputs
have the correct rate, length, stereo channels, and finite samples. Maximum
source-sum error is **2.9802322387695312e-08**. This is an integration/preservation
check, not a Turkish quality score: the recording has no true reference stems.
