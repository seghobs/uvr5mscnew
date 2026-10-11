# Atlas V2: additional content preservation experiment

11 October 2026. Baseline is the deployed nine-model frequency recipe, not
the earlier six-model preset. This experiment does not change production.

All 24 previously inspected recordings are development. The fit targets a
further 2% reduction in both mean spectral deficit proxies, while constraining
both excess proxies and checking full-resolution SDR and SI-SDR. Three
regularization strengths are predeclared. After that target failed, a 0.5%
deficit target was tried with unchanged excess limits, then with an extra
1% instrumental-excess margin. Full-resolution checks rejected those
sampled-spectrum candidates because instrumental excess increased.
The final attempt uses every spectral bin/frame, a 0.5% reduction target
for all four proxies and regularization 0.01. Ten bounded fits completed:
nine sampled fits and one full-spectrum fit. Two earlier incomplete runs
were interrupted to adjust computation settings; no scores are claimed
for them. Nonnegative weights sum to one at
each frequency anchor. No gate, vocal muting or original-region substitution
is introduced. The waveform statistics cache uses audio metadata, model
indices, frequency anchors and combiner hash to avoid stale reuse.

Only an eligible development candidate can enter fresh confirmation. Eight
previously uncached reference recordings are selected in a fixed SHA order
after freezing the candidate. Acceptance requires a positive paired 95%
SDR interval, no mean SI-SDR/excess regression, and at least 1% lower mean
deficit for each stem. Previously inspected confirmation recordings cannot
be used as fresh evidence. Model-training overlap is unknown.

SDR is in dB. Spectral deficit is a normalized error proxy, not the percentage
of audible content missing. Short reference excerpts do not establish quality
on Turkish full songs or a zero-loss guarantee. Unsuccessful candidates are
reported without replacing the production preset.

## First independent confirmation: rejected

The frozen full-spectrum candidate was tested on eight additional previously
uncached recordings, requiring 72 real model inferences. Vocal SDR improved
from 11.4975 to 11.5249 dB; instrumental SDR from 15.7300 to 15.7574 dB.
Mean gain was +0.0274 dB, with paired 95% interval [+0.0098, +0.0460] dB.
Seven of eight recordings improved in SDR. Mean vocal deficit fell 2.13%
and instrumental excess fell 1.16%, but instrumental deficit rose 0.37%
and vocal excess rose 1.42%. The candidate failed acceptance and was not
applied. These are relative proxy changes, not audible loss percentages.
[Complete scores and unsuccessful attempts](atlas-studio-v2-content-refinement.json).

The opened eight recordings were then explicitly reclassified as development,
giving 32 inspected recordings. The next full-spectrum fit targets 1% lower
deficit for both stems, 2% lower vocal excess and 0.5% lower instrumental
excess. Any confirmation of this refit must use additional unseen recordings.

The 32-record full-resolution development fit passed all mean checks:
SDR +0.0506 dB, vocal deficit -3.00%, instrumental deficit -0.99%, vocal
excess -1.97% and instrumental excess -0.49%. Its weights were frozen
before selecting eight more previously uncached recordings. These development
results do not establish an independent improvement.

## Second independent confirmation: rejected

The more conservative candidate was tested on eight further previously
uncached recordings. Vocal SDR changed from 13.7423 to 13.7382 dB;
instrumental SDR from 16.3706 to 16.3666 dB. Mean change was -0.0040 dB,
with conservative paired 97.5% interval [-0.0286, +0.0151] dB.
Four of eight recordings improved in SDR. Mean vocal deficit decreased
0.17%, instrumental deficit decreased 1.00% and vocal excess decreased
0.26%, but instrumental excess increased 1.18%. SI-SDR also declined
slightly. This candidate failed the predeclared acceptance rule.
[Second confirmation scores and frozen weights](atlas-studio-v2-content-refinement-round-two.json).

This task completed eleven bounded constrained fits and 144 model outputs
on sixteen fresh reference recordings across two independent confirmation
rounds. The second fit used the opened first confirmation as development;
its final eight recordings remained separate from all 32 development
recordings. Neither confirmation supports an additional overall improvement
over the deployed nine-model Atlas V2. The production preset was preserved
byte for byte (SHA-256 dd8d1d265455b88843414ad6b4e341c15d54655bda05c469bced7748f7ccc7d6).
This does not prove that further improvement is impossible; it rejects the
tested candidates. Thirty-one relevant unit tests and the diff whitespace
check passed. The application was not rebuilt because its recipe/code did
not change in this experiment. No GitHub push was performed for this task.

Run with the bundled environment:

```powershell
.\env\python.exe tools/atlas_content_refine.py fit
.\env\python.exe tools/atlas_content_refine.py fit_soft
.\env\python.exe tools/atlas_content_refine.py fit_balanced
.\env\python.exe tools/atlas_content_refine.py fit_full
.\env\python.exe tools/atlas_content_refine.py choose
.\env\python.exe tools/atlas_content_refine.py infer
.\env\python.exe tools/atlas_content_refine.py evaluate
```
