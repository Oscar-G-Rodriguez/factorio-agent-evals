# Storage tool-selection diagnostic

The maintenance agent had the storage tool in its system instructions, an observed wooden chest handle e1 with 1600 free plate capacity, 100 carried plates, zero benchmark carrying space, and feedback from a failed collection. The system message remained present despite history trimming. Tool visibility was verified from the exact recorded prompt at decision 23.

Three offline greedy generations used the same pinned Qwen revision and the same recorded current observation/feedback. No game actions were executed and no factory was reset.

| Condition | Input tokens | Proposed tool |
| --- | ---: | --- |
| recorded_history | 7487 | `collect_output` |
| fresh_context | 1417 | `fuel` |
| explicit_storage_subgoal | 1450 | `store_plates` |

The recorded-history replay exactly reproduced the original failed collection action. Removing history changed the proposal to fuel, but did not elicit storage. Adding an explicit diagnostic subgoal—free carrying space by storing carried plates in the observed chest—elicited `store_plates` with chest e1 and quantity 100. That proposal matches the exposed tool contract and observed available capacity. It is an assisted capability check, not an executed transfer or autonomous maintenance improvement.

The result shows that this model can select the storage command when the subgoal is stated explicitly. The autonomous problem concerns selecting and prioritizing that subgoal while maintaining production and recovering from failures. The history change affected its choice; these single-state probes do not isolate history length from historical action content or establish a general explanation for every failure. Timing is a single unwarmed sample in a fixed order and is not a performance benchmark.

Next experiments should compare factual memory of carrying capacity and recent failures against ordinary history, while retaining storage as a model-selected action. More specific transfer failure codes can be developed separately and frozen for all scored conditions. Do not silently add the explicit storage hint to one memory condition or count an automatic transfer as a model decision.

Evidence: `factorio-pilot/evidence/artifacts/storage-context-probe.json` and `storage-subgoal-probe.json`. Exact probe source snapshots were verified against each artifact's SHA-256. The probe imports the native-source review gate before GPU execution; no native sources changed. To reproduce under the current project layout, run `tools/probe_storage_context.py`, then run it with `--storage-subgoal-only`, using the existing WSL virtual environment. The referenced maintenance run and model snapshot must remain available.
