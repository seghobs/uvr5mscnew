# Atlas V2: new expert and nonlinear ensemble experiment

Date: 2026-10-10. Production baseline: deployed six-model frequency recipe.

## Research and reproducibility

- [MVSEP algorithms](https://mvsep.com/en/algorithms): inspect BS RoFormer 124 bands, BS PolarFormer, SCNet XL IHF, HyperACE and MelBand Deux. Published service scores are not interchangeable with this experiment's waveform SDR.
- [MSST public checkpoints](https://github.com/ZFTurbo/Music-Source-Separation-Training/blob/main/docs/pretrained_models.md): the downloadable SCNet XL IHF is a four-stem MUSDB-trained checkpoint; do not assume it is the same checkpoint as the vocal-specialist service ensemble. PolarFormer has a public release and a distinct architecture; it was researched, not executed here.
- [HyperACE publisher](https://huggingface.co/pcunwa/BS-Roformer-HyperACE): requires a custom model implementation. Researched, not executed here.
- [SiameseRoformer publisher](https://huggingface.co/pcunwa/BS-EXP-SiameseRoformer) and [Large Inst publisher](https://huggingface.co/pcunwa/BS-Roformer-Large-Inst): reviewed as additional architecture experiments. Neither was executed or claimed superior here.
- [Deux publisher](https://huggingface.co/becruily/mel-band-roformer-deux): jointly predicts vocals and instrumental. Executed using pinned revision `2da74427d682a3df47a774378fc24d7a1a0cdaad`; checkpoint SHA-256 `10255c02295bf3e3865d4ee50ff752d7b19b124ed5fd93b147babc4333eda3aa`.
- [Leap Xe publisher files](https://huggingface.co/pcunwa/BS-Roformer-Leap/tree/4e47d6662ae82eaa8b4ac4329fe66099a843b48e/Xe): separate vocal and instrumental experts. Execute pinned revision `4e47d6662ae82eaa8b4ac4329fe66099a843b48e`; verify publisher LFS hashes before loading. Batch size one; architecture metadata translated through the existing compatibility helper.
- [MSST ensemble documentation](https://github.com/ZFTurbo/Music-Source-Separation-Training/blob/main/docs/ensemble.md): motivates testing alternatives to averages, without assuming they improve SDR.

The application's existing entry named `BS Roformer 124 bands (ver. 2026.07)` points to `pcunwa/BS-Roformer-Leap/main/model.safetensors` and `config.yaml`. Both filenames are absent from the inspected public repository; the weight URL returned HTTP 404. It is not evidence of an available MVSEP 124-band checkpoint. This experiment does not execute or relabel it as a new expert.

## Protocol

Eight previously inspected reference excerpts are DEVELOPMENT ONLY. These are not Turkish full-song ground truth and not unseen evaluation. All three new experts run on the identical padded audio, sample rate, headroom and overlap factor eight. New estimates are cached at indices 9/10/11, independently of the original nine-expert pool.

Instrumental experts are converted once to vocal estimates by `source - instrumental`; they are not inverted again. Every tested system's final instrumental is `source - vocal`, preserving the sum but not claiming correct stem assignment.

Compare waveform median, complex component median, median magnitude with baseline phase, magnitude-ranked complex trimmed mean, two local disagreement weighting functions, two source-phase Wiener masks, each new expert and an equal Xe pair. Each correction is blended with the deployed baseline at 10%, 25%, 50% and 100%. Inspect both stems' waveform SDR, SI-SDR, spectral deficit and spectral excess. Deficit/excess are proxies, not measured percentages of audible loss or bleed.

Separately fit nonnegative weights at ten frequency anchors with the existing constrained optimizer. Both stems' four content proxies constrain development fitting; full-resolution metrics decide eligibility. A development candidate is not automatically deployed. A meaningful superiority claim requires at least 0.2 dB mean gain, positive paired 95% confidence interval and no mean SI-SDR or content regressions on a fresh, frozen comparison.

Commands use the bundled environment:

```powershell
.\env\python.exe tools/atlas_alternative_screen.py infer
.\env\python.exe tools/atlas_alternative_screen.py infer_xe
.\env\python.exe tools/atlas_alternative_screen.py screen
.\env\python.exe tools/atlas_alternative_screen.py fit
.\env\python.exe tools/atlas_alternative_screen.py validate_infer
.\env\python.exe tools/atlas_alternative_screen.py validate
```

This tool does not change a production preset, launch web servers or modify installed model code. Checkpoint download and inference are real local operations. SDR is in dB; no 100% quality or zero-loss guarantee follows from these measurements.

Final measured results are recorded in the accompanying JSON report after all runs finish.

## Development findings

48 alternatives were screened (12 methods × four blend strengths). A 50% Leap Xe vocal blend improved mean SDR by 0.1781 dB with all mean content checks passing. A 50% Deux blend improved SDR by 0.1365 dB but worsened instrumental deficit; it was rejected. Median/adaptive improvements were small and did not satisfy the full gate.

Three constrained nine-expert fits improved DEVELOPMENT SDR by 0.3425, 0.3416 and 0.3258 dB. Full-resolution development content and SI-SDR checks passed. The first fit was frozen before selecting eight previously uncached recordings in a fixed SHA ordering. It is a candidate, not evidence of universal superiority. Confirmation uses 72 real model inferences.

The paired SDR gains of the two complementary stems are mathematically coupled: their waveform errors are negatives of each other when the reference stems sum to the mixture. Reporting both absolute scores is useful but does not create two independent pieces of evidence. Separate content proxies remain essential.

## First independent confirmation

Eight previously uncached recordings were scored only after weights were frozen. Two development-selected candidates were compared using conservative 97.5% paired bootstrap intervals.

| System | Vocal SDR dB | Instrumental SDR dB | Mean gain dB | Gain interval |
| --- | ---: | ---: | ---: | --- |
| Deployed Atlas V2 | 13.1082 | 15.6765 | — | — |
| Nine-expert frequency fit | 13.5990 | 16.1673 | +0.4908 | [0.1466, 0.9802] |
| Half baseline, half Leap Xe vocals | 13.5089 | 16.0772 | +0.4007 | [0.0482, 0.8330] |

Both candidates failed the full acceptance rule. The nine-expert candidate increased mean instrumental spectral deficit from 0.01274085 to 0.01353644 and vocal spectral excess from 0.00445684 to 0.00467063. The simple blend increased instrumental deficit to 0.01301949. These are normalized spectral error proxies, not percentages of missing audible music. Production was preserved. Full data: [first confirmation JSON](atlas-studio-v2-alternatives.json).

## Second development attempt

The first confirmation was explicitly reclassified as development, yielding 16 inspected recordings. Two additional margin plans targeted instrumental deficit reduction: 10% and 3%. The strict attempt did not finish its first optimization in over six minutes and was interrupted; no infeasibility or score is claimed for it. Three softer fits completed, passing full-resolution development content checks. The best yielded +0.2724 dB mean development gain, with lower mean deficit/excess for both stems.

This recipe was frozen for a second confirmation on eight additional previously uncached recordings. Their model inference began while development fitting finished; quality scores remained unopened until final selection was frozen. This distinction is recorded in the manifest. The second confirmation is independent of the 16 development recordings and uses a conservative 97.5% paired interval plus the same 0.2 dB and content requirements.

## Second independent confirmation and deployment

| System | Vocal SDR dB | Instrumental SDR dB |
| --- | ---: | ---: |
| Previous six-model Atlas V2 | 12.1050 | 17.6811 |
| Confirmed nine-model Atlas V2 | 12.3528 | 17.9289 |

Mean paired gain was **+0.2478 dB**, with a 97.5% bootstrap interval of
**[+0.1026, +0.4704] dB**. All eight recordings improved in SDR. Both
mean SI-SDR scores improved. Mean vocal spectral deficit decreased by
10.79%, vocal excess by 5.04%, instrumental deficit by 4.11% and
instrumental excess by 9.38%. These are relative reductions in normalized
spectral error proxies, not measured audible loss percentages.

The accepted recipe was applied to the application's Atlas V2 preset.
The existing six experts now include Deux and Leap Xe vocal/instrumental
experts, with nonnegative frequency-dependent weights summing to one.
The current experiment executed 168 real model inferences and screened
48 alternative recipes. The six completed constrained fits exclude the
interrupted strict attempt. Full provenance, weights and per-record scores:
[second confirmation JSON](atlas-studio-v2-alternatives-round-two.json).

Verification: 28 relevant unit tests passed, production build and TypeScript
passed, and the actual local API completed all nine models on a three-second
Turkish recording excerpt. Both stereo 44.1 kHz outputs had 132,300 frames;
their maximum sum error against the input was 3.7253e-08. This live export
check verifies operation and mixture consistency, not ground-truth Turkish
stem quality. Nine models take longer than the previous six-model preset.
Short reference excerpts, possible model-training overlap and the absence
of true Turkish full-song stems prevent universal superiority or zero-loss
claims. SDR is measured in dB, not percent.
