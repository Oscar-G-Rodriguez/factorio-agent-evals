# Qwen maintenance waiting diagnostic

The 172 wait labels in the A06 dataset are intentional choices by the scripted teacher, not measured Qwen waiting. Every wait was followed by 4–5 newly produced plates during its 900-tick interval. The retained A04 model and both A05 model episodes contain zero `wait` actions. These records do not establish unnecessary waiting by an A06 base or trained model; no such A06 model evaluation has occurred.

## Read only trace audit

[`diagnose_a06_waiting.py`](../scripts/diagnose_a06_waiting.py) checks the final r3 dataset checksum, resolves each wait to its original executed train trace and checks the trace checksum. It examines the actual pre-action state and following production-counter delta. It does not load a model or game, change examples, read held-out control actions, or execute native code. The [receipt](../factorio-pilot/evidence/artifacts/A06-waiting-diagnostic.json) preserves decision-level findings and input hashes.

| Teacher wait observation | Finding |
| --- | ---: |
| Wait labels | 172 / 320 |
| Waits matching the teacher's idle predicate | 172 / 172 |
| Waits followed by positive plate production | 172 / 172 |
| Minimum stored coal across both burners | 2 |
| Maximum furnace output before a wait | 57 plates |
| Carried plates before every wait | 0 |
| Newly produced plates over each following interval | 4–5 |
| Waits per training fixture | 43 |

The teacher first refuels a burner with at most one stored coal, then stores carried plates, then collects furnace output at 60 or more plates. Otherwise it waits. All wait states satisfy this recorded rule. Production continued through each wait and all four teacher episodes survived their horizon. This supports deliberate idle scheduling; it does not prove that this teacher is optimal or that waiting is always harmless in other states.

| Historical Qwen episode | Decisions | Explicit waits |
| --- | ---: | ---: |
| A04 ordinary maintenance | 44 | 0 |
| A05 automatic observations | 16 | 0 |
| A05 requested inspection | 60 | 0 |

Historical generation timing is retained in the receipt, but it is not a phase profile or evidence of a GPU bottleneck. Historical conditions differ from A06 and are not matched before/after training controls.

## Diagnostic to add before interpreting fine tuning

Distinguish an explicit `wait`, a rejected action that still advances game time, requested inspection, inference latency and an infrastructure stall. In this task, inference runs while the game is paused, so slower generation alone does not advance fuel consumption. It can cause a wall-budget endpoint. Numerical/backend, quantization, context/output-budget or timeout behavior may affect decisions indirectly; diagnose them separately.

For the unchanged A06 baseline, log the supplied state and its age, action validation outcome, fuel/remaining energy, output/carry/chest capacity, consecutive explicit waits and next-interval production. Flag missed maintenance for review using a rule frozen before comparison. Expired fuel with available coal and full output with available transfer capacity are observable candidates; teacher disagreement alone does not establish a wrong action.

Replay suspected failures on train fixtures from an exact pre-action save, preserving the original action history. First check whether the necessary facts were visible. Compare one context change at a time, then execute a repair and continuation to test whether it avoids the stall. Offline proposals are not executed repairs. Do not diagnose policy changes repeatedly on reserved test outcomes.

Compare unchanged 4-bit Qwen with the adapter under matched inputs. An increase in harmful waits after training implicates the learned changes as a candidate cause. Audit coverage and masking before any separately recorded rebalanced-data trial. The current 53.75% wait-label share is not itself evidence of a training defect; no training has occurred. Do not silently rebalance the immutable release.

Separately record rendering/tokenization, prompt processing, token generation, JSON validation, tool execution and simulation advancement times, with tokens and memory. A reviewed backend comparison on identical prompts can isolate timing changes from policy changes. Keep model/code, quantization and input contracts fixed when drawing that distinction.

Before comparison, define harmful waits per maintenance opportunity in addition to total wait rate, survival, new plates, failed actions and latency. Only executed continuation evidence supports a causal repair claim. Additional diagnostic replay runs need a declared time budget; they are not included in the earlier overnight estimates.

## Reproduce

From the repository root, with Python 3.10 or newer:

```bash
python scripts/diagnose_a06_waiting.py
```

To retain a new receipt, choose an unused output path:

```bash
python scripts/diagnose_a06_waiting.py --output /path/to/new-receipt.json
```

This is a CPU-only audit of retained traces. Frozen dataset, protocols and historical results remain unchanged. Future A06 model diagnostics and timing instrumentation are planned, not implemented or measured by this audit.
