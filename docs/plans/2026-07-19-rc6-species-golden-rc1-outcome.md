# RC6 species golden + RC1 RecognitionOutcome (thin)

Date: 2026-07-19 · Branch: `orin` · Source: `hub-recognition-software-critique.md`

## Decision

**First:** RC6 (CI truth) + thin RC1 type.  
**Not first:** full persist/visit/notify rewrite, Orin SSH, threshold loops.

Why RC6 before deep RC1: without a species gate, contract refactors ship green on track stubs.

## Goals

1. Detector golden ≠ taxonomy PASS.
2. Merge-local species gate over Hub-only labeled *cases* (JSON rows; no GPU/mp4 required).
3. Typed `RecognitionOutcome` as the single derivation surface for those cases (bridge from legacy `decision_kind`).

## Non-goals

- Replacing DecisionMaker / linear path in this slice.
- Labeled mp4 pack with ONNX regen (later; add `expected_species` when ready).
- Closed learning loop (RC5).

## Files

| Path | Role |
|------|------|
| `app/processor/src/recognition_outcome.py` | `OutcomeKind` + `RecognitionOutcome.from_persist_row` |
| `benchmarks/species_golden_cases.json` | Hub-only synthetic labeled rows |
| `scripts/species_golden_gate.py` | Enforce cases |
| `scripts/pipeline_golden_gate.py` | Report `product=detector`, taxonomy skipped |
| `Makefile` | `validate-detector-golden`, `validate-species-golden` |

## Done when

- `make validate-detector-golden` → detector unit OK, report says taxonomy not evaluated.
- `make validate-species-golden` → fails if Bird/Unknown mapped to `named_accept` or Frigate counted as hub win.
- Unit tests cover outcome mapping + both gates.
