# Factorio maintenance development results

The earlier construction/expansion success check stopped before recurring fuel and storage demands were tested. Its final machines still held 38–44 coal, with 300 in reserve; one furnace held 94/100 plates. Those results remain preserved and are not pooled with this maintenance task.

## Methods

The new maintenance runner starts from a scripted one-drill/one-furnace/one-chest fixture, using the same validated placement and fueling tools. No ore or plates are injected. Each machine receives three coal. A 60-second warm-up must produce at least 16 plates before evaluation begins; fixture construction and warm-up are excluded from model decisions and measured production windows.

The maintenance controller can refill a machine with 1–3 coal, collect up to 100 finished plates, store up to 100 carried plates, check, or wait. Fuel per action and the 100 carried-plate limit are disclosed benchmark rules. The chest has its real 1600-plate capacity. All equipment is within transfer range. Movement, construction, expansion and external disruptions are not part of this first maintenance fixture.

Every decision, including invalid actions, consumes exactly 900 simulation ticks (15 seconds). The world pauses during inference and runs at 10× during advancement. Nonoverlapping windows contain exactly 3600 ticks. Two consecutive windows below 16 plates constitute sustained production failure. Meeting the target does not stop the episode. Limits are 20 game minutes, 80 decisions and 600 wall seconds; reaching a limit is recorded honestly as survival through the horizon or an incomplete budget-limited run. The first low window and terminal failure are distinct from the physical instant an outage began.

The model condition uses pinned Qwen3-4B-Instruct-2507 with BF16 PyTorch SDPA, greedy generation, an 8192-token total context and 256 generated-token budget. Its prompt teaches the game mechanics and tool syntax but does not prescribe a complete maintenance action sequence. Ordinary history is trimmed when needed; model logs retain the assembled prompts and cumulative trimming count. Full current equipment observations make this a maintenance decision test, not yet a test of remembering unseen equipment. Structured memory and RAG comparisons are pending.

## Results

| Controller | Game minutes after warm-up | Decisions | Failed actions | Endpoint | Wall seconds, excluding load/setup |
| --- | ---: | ---: | ---: | --- | ---: |
| idle | 2 | 8 | 0 | sustained_production_failure | 21.18 |
| model | 11 | 44 | 13 | sustained_production_failure | 179.76 |
| scripted | 20 | 80 | 0 | survived_simulation_limit | 181.58 |

Qwen reached sustained failure after 11 game minutes (179.76 wall seconds, excluding model loading and setup). It made 13 failed actions. Its final state contains expired burners ['e2'] and 461 coal still in reserve. Inspect the saved trace to distinguish missed refueling from output/storage errors; the fixture did not force resource exhaustion. This single-chain maintenance task already exposes model failures, so further complexity can wait until the memory/backend comparisons use a frozen baseline.

`A04-maintenance-idle-20261006T043628Z`: plate windows [10, 0]; successful actions {'wait': 8}; failed actions {}; final failure indicators {'empty_and_expired_burners': ['e2'], 'full_furnace_outputs': [], 'reserve_coal': 494, 'note': 'Observed bottleneck indicators, not a causal proof; fuel reserve exhaustion is distinct from missed refueling.'}. Timed generation: 0.00s; other evaluation wall time: 21.18s. History pairs trimmed: None. First observed expired burner: 30.0 game seconds; first full carrying inventory: None game seconds.

`A04-maintenance-model-20261006T044058Z`: plate windows [18, 19, 19, 19, 14, 18, 19, 19, 18, 15, 0]; successful actions {'fuel': 21, 'collect_output': 10}; failed actions {'collect_output': 13}; final failure indicators {'empty_and_expired_burners': ['e2'], 'full_furnace_outputs': [], 'reserve_coal': 461, 'note': 'Observed bottleneck indicators, not a causal proof; fuel reserve exhaustion is distinct from missed refueling.'}. Timed generation: 73.91s; other evaluation wall time: 105.85s. History pairs trimmed: 36. First observed expired burner: 270.0 game seconds; first full carrying inventory: 300.0 game seconds.

`A04-maintenance-scripted-20261006T043718Z`: plate windows [18, 19, 19, 19, 18, 19, 19, 19, 18, 19, 19, 19, 18, 19, 19, 19, 18, 19, 19, 19]; successful actions {'fuel': 25, 'wait': 43, 'collect_output': 6, 'store_plates': 6}; failed actions {}; final failure indicators {'empty_and_expired_burners': [], 'full_furnace_outputs': [], 'reserve_coal': 419, 'note': 'Observed bottleneck indicators, not a causal proof; fuel reserve exhaustion is distinct from missed refueling.'}. Timed generation: 0.00s; other evaluation wall time: 181.58s. History pairs trimmed: None. First observed expired burner: None game seconds; first full carrying inventory: None game seconds.

The idle control is a negative control. The scripted controller uses only visible fuel/storage state and the same permitted actions; its result tests reachability, not model quality. These are single-fixture development runs, not independent statistical samples. Every logged decision interval and complete measurement window was audited. In every completed run, produced plates equal the plates in furnace output, carried inventory and chest.

## GPU work and limits

With explicit user authorization, the reviewed bounded RMSNorm suite passed memcheck, racecheck, initcheck and synccheck with zero reported errors. Each tool ran all 25 correctness cases. The temporary Windows debugger interface was restored to its previous absent state. See `factorio-pilot/evidence/artifacts/approved-sanitizer-validation.json`.

These maintenance runs use the original PyTorch inference backend. The custom C++/CUDA kernel is not yet integrated into Qwen, so no faster-agent claim follows from its standalone operator timings. The intended next measurement is original versus integrated inference on identical saved prompts: logits/token agreement, generation latency and total evaluation wall time. Model generation, controlled simulation and observation/transfer costs must be distinguished. Because the game pauses during inference, faster CUDA does not give the agent extra simulated reaction time.

If Qwen survives this fixture, increase difficulty in a separately versioned task—for example a second chain or a disclosed demand schedule—then repeat a scripted survivability control. Do not change difficulty mid-comparison to manufacture failures. Preserve limits and surviving episodes when estimating time to failure.

## Reproduction

Start the existing pinned 2.0.73 server. Run only one controller at a time because each resets the same factory. From PowerShell:

```powershell
wsl -d Ubuntu-24.04 -u osci2 -- bash -lc 'cd /mnt/c/Users/osci2/Documents/Codex/2026-10-05/igni/factorio-pilot/tools && /home/osci2/factorio-pilot/.venv/bin/python -m unittest test_maintenance test_logistics_tools test_cuda_review'
wsl -d Ubuntu-24.04 -u osci2 -- /home/osci2/factorio-pilot/.venv/bin/python /mnt/c/Users/osci2/Documents/Codex/2026-10-05/igni/factorio-pilot/tools/maintenance_agent.py --controller idle --minutes 20
wsl -d Ubuntu-24.04 -u osci2 -- /home/osci2/factorio-pilot/.venv/bin/python /mnt/c/Users/osci2/Documents/Codex/2026-10-05/igni/factorio-pilot/tools/maintenance_agent.py --controller scripted --minutes 20
wsl -d Ubuntu-24.04 -u osci2 -- /home/osci2/factorio-pilot/.venv/bin/python /mnt/c/Users/osci2/Documents/Codex/2026-10-05/igni/factorio-pilot/tools/maintenance_agent.py --controller model --minutes 20
wsl -d Ubuntu-24.04 -u osci2 -- /home/osci2/factorio-pilot/.venv/bin/python /mnt/c/Users/osci2/Documents/Codex/2026-10-05/igni/factorio-pilot/tools/export_evidence.py
```

Sources are preserved in the per-result snapshots above, with hashes verified against each configuration. Controls v1 and model v2 differ only in additional prompt/history logging and the first-low-window timestamp; the task, action cadence and endpoint are identical. Environment/model pins remain in the project README and saved artifacts. Previous construction, storage and kernel findings remain separate.
