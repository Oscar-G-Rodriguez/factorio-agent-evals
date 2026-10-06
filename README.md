# Factorio Agent Evals

This project tests whether a local language model can keep a small Factorio factory producing iron plates over repeated decisions. It also measures a project-authored C++/CUDA RMSNorm operator, both alone and inside Qwen on saved prompts. The repository retains the action traces, configurations, source snapshots, and hashes needed to inspect each result.

The agent loop uses [Factorio Learning Environment (FLE)](https://github.com/JackHopkins/factorio-learning-environment) to observe a CPU game server. Python presents the goal, current equipment and inventory, allowed tools, and action feedback to Qwen3-4B-Instruct-2507. The model returns one JSON action; the adapter validates it, executes it, advances the game, and logs the outcome. Qwen runs in BF16 on an RTX 5070 Ti. Factorio pauses during inference, so model latency affects wall time without changing the simulated decision interval.

## Start with the maintenance episode

The [trace walkthrough](docs/Maintenance%20Episode%20Walkthrough.md) follows the measured plate windows and the storage/fuel failures. The fixture starts with a burner drill, furnace, empty chest, and three coal in each machine. Every decision, including an invalid one, advances exactly 15 game seconds. Two consecutive 60-second windows below 16 plates end the episode. The 20-minute horizon is recorded as survival if the controller reaches it.

| Controller | Result on this fixture |
| --- | --- |
| Scripted control | Survived 20 game minutes at 18–19 plates in every measured minute |
| Qwen with ordinary history | Failed after 11 game minutes and 44 decisions, including 13 failed collection attempts |

Qwen never stored its 100 carried plates. At the endpoint the drill was unfueled, although 461 coal remained in reserve. The scripted result shows this fixture is reachable with the permitted tools. These are single-fixture development runs, not a model ranking. [Methods and full results](outputs/A04%20-%20Maintenance%20-%20Results.md) preserve the logs and timing scope.

## Other experiments and their boundaries

Result filenames use `A##` for Factorio agent iterations and `K##` for kernel experiments. The number identifies an experiment stage, not a claim that the two tracks ran sequentially. The Day 1 snapshot and final construction-pilot report both belong to `A01`; the maintenance report and its offline storage diagnostic both belong to `A04`.

| Record | What it established |
| --- | --- |
| [Day 1 construction snapshot](outputs/A01%20-%20Construction%20Pilot%20-%20Day%201%20Snapshot.md) | An early status record from the construction pilot; later reports supersede its pending-work statements. |
| [Original four-run context pilot](outputs/A01%20-%20Construction%20Pilot%20-%20Final%20Results.md) | Two history and two structured-memory runs produced zero plates under the original construction setup. |
| [Guided construction](outputs/A02%20-%20Guided%20Construction%20-%20Results.md) | A corrected tool interface and explicit factory procedure produced 19 plates in each measured minute with eight decisions and no failed actions. |
| [Plate logistics and expansion](outputs/A03%20-%20Storage%20and%20Expansion%20-%20Results.md) | Separate development checks tested transfers and construction; they are not maintenance scores. |
| [Offline storage probe](outputs/A04%20-%20Maintenance%20-%20Storage%20Decision%20Diagnostic.md) | Replaying a saved decision with an explicit storage subgoal produced the correct proposed action. It was not executed in the game. |
| [Observation delivery](outputs/A05%20-%20Observation%20Policy%20-%20Pilot%20Results.md) | One executed model episode per condition: failure at 4 game minutes with automatic stats versus 15 with requested inspection (14 checks). The scripted inspection controller survived 20 minutes. This is a one-fixture pilot. |
| [Integrated RMSNorm](outputs/K02%20-%20RMSNorm%20-%20Integrated%20Inference%20Results.md) | 73 full-width norms used the custom kernel; five saved states retained identical greedy tokens/actions. Warm timing yielded 1.11–1.17× eager/custom paired median ratios across five frozen prompts. The compiled baseline varied by prompt. |
| [Reviewed RMSNorm](outputs/K01%20-%20RMSNorm%20-%20Reviewed%20Benchmark.md) | 25 correctness cases and bounded memcheck, racecheck, initcheck, and synccheck passed. The standalone operator was 5.21× faster for a captured 1,006-row prompt and 4.80× faster for a one-row token than the installed eager CUDA reference. |

The custom operator is integrated through an opt-in adapter. K02 measures offline response latency, including tokenization and JSON validation, with 90 samples per backend and prompt. It does not measure executed episode improvement. The [continuation guide](docs/Continuing%20the%20Study.md#k02-integrated-rmsnorm-evidence) maps the implementation; the [acceleration design](docs/Inference%20Acceleration%20Design.md) specifies a separate proposed prefix-cache comparison. A maintenance history/structured-memory/retrieval comparison remains future work, with no result claimed yet. The [native source review](outputs/CUDA%20and%20C%2B%2B%20Source%20Review.md) records the reviewed implementation.

## Next experiment

The [Qwen fine tuning protocol](outputs/A06%20-%20Qwen%20Fine%20Tuning%20-%20Protocol.md) fixes four training, two validation and three test fixture recipes before data collection. It specifies automatic observations, at most two historical decision pairs, the action-only supervised target and fresh unchanged BF16/4-bit baselines. The [first fixture control](outputs/A06%20-%20Qwen%20Fine%20Tuning%20-%20Fixture%20Control.md) verifies the low-drill-fuel training recipe: scripted maintenance survived 20 game minutes with 375 new plates, while idle failed at two minutes. Both restored the same physical state. The [low-furnace-fuel control](outputs/A06%20-%20Qwen%20Fine%20Tuning%20-%20Furnace%20Fixture%20Control.md) also passed. Seven recipes still require these controls. No A06 dataset or trained adapter exists yet. `python scripts/verify_a06_protocol.py` checks design consistency without running the game or GPU; it does not establish fixture solvability or dataset isolation.

## Inspect or reproduce

The portable, CPU-only entry point is `python scripts/verify_maintenance_evidence.py`. Run it from any clone with Python 3.10 or newer; it checks the retained summaries and trace counts, then prints the measured plate windows. It needs no game, model, GPU, or private host paths. `python scripts/verify_k02_evidence.py` separately audits K02 export/source hashes, frozen prompts, custom coverage and all retained response samples without inference. The [saved-run index](factorio-pilot/evidence/runs/README.md) explains the staged folder names and which records support each report; run-specific configurations and snapshots determine the evaluated code. The [tool map](factorio-pilot/tools/README.md) identifies current controllers, supporting checks, and one-off historical helpers. [Provenance of this public snapshot](PROVENANCE.md) records what was preserved and omitted.

For continued work, [Continuing the study](docs/Continuing%20the%20Study.md) maps the active code, frozen evidence, checks, and the path from a private experiment to a public result.

For a new live experiment, follow [runtime setup and pinned versions](factorio-pilot/README.md). The launchers under `factorio-pilot/setup/` locate source relative to the clone and use `FACTORIO_PILOT_HOME` for the Linux runtime directory. Root launchers also accept `FACTORIO_PILOT_USER` for the ordinary account that runs the agent. A new machine still needs the pinned model, FLE installation, Factorio server, Python environment, and CUDA toolkit. Run only one controller against a server at a time because each controller resets its world. Before any GPU execution, inspect every project-authored C++/CUDA source and verify the exact source hashes as required by [AGENTS.md](AGENTS.md) and [factorio-pilot/AGENTS.md](factorio-pilot/AGENTS.md). Do not treat a fresh manifest as approval.

## Credit and reuse

This work builds on [FLE](https://github.com/JackHopkins/factorio-learning-environment) and its [paper](https://arxiv.org/abs/2503.09617), [Factorio](https://factorio.com/), [Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507), PyTorch, and Transformers. FLE supplies the game interface; the Factorio game, model weights, FLE installation, downloaded binaries, and a captured FLE system prompt are not bundled here. The maintenance fixture, adapter, evaluation records, and RMSNorm experiment were developed for this project. Upstream components retain their own licenses and terms.

Contributions should keep the pilot, guided construction, logistics, maintenance, and offline probes separate; preserve original traces and exact evaluated source hashes; and document new configurations before interpreting results. Native changes require a new full source inspection before GPU runs. [Engineering conventions](CONVENTIONS.md) describe the validation gate. Project-authored repository contents are released under the [MIT License](LICENSE); external components retain their own terms.
