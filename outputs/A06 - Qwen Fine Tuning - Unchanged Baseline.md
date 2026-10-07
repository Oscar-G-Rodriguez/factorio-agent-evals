# A06 unchanged Qwen baseline

Six executed development episodes establish the unchanged 4-bit reference for the three-round QLoRA experiment. Four factories belong to training and two to validation. Final test factories remain reserved.

| Factory | Partition | Survival seconds | New plates | Failed actions | Median generation seconds | Endpoint |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| train_drill | train | 360 | 80 | 0 | 0.847 | sustained_production_failure |
| train_furnace | train | 1140 | 312 | 1 | 0.969 | sustained_production_failure |
| train_output | train | 540 | 149 | 4 | 0.999 | sustained_production_failure |
| train_carry | train | 120 | 10 | 0 | 0.834 | sustained_production_failure |
| validation_fuel | validation | 1200 | 327 | 7 | 0.975 | survived_simulation_limit |
| validation_storage | validation | 1200 | 353 | 1 | 1.013 | survived_simulation_limit |

## Observed behavior

The low-drill-fuel run made 24 fueling decisions, no collection or storage actions, and failed at six simulated minutes after the furnace reached its 100-plate limit. The full-carry run made eight fueling decisions and failed after two minutes. Their valid commands did not maintain production. Other runs used collection and storage, so this is not evidence that Qwen never understands those tools.

The low-furnace-fuel run lasted nineteen minutes, while the high-output run lasted nine. The fuel-validation run reached the twenty-minute cap with seven failed actions. Further root-cause analysis must use their decision traces, not failure counts alone.

## Measurement boundary

Each episode used the frozen guide, automatic observations, at most two history pairs, greedy decoding and one action per fifteen simulated seconds. Inference paused the world. Survival is capped at 1,200 seconds; generation timing is separate from context preparation, tool calls and simulation. New plate counters exclude preloaded stock. The custom RMSNorm was not loaded.

The [machine-readable baseline](../factorio-pilot/evidence/artifacts/A06-three-round-baseline.json) retains run IDs, source hashes, trace hashes and numerical measurements. These development results are not final-test evidence or a fine-tuning improvement claim.
