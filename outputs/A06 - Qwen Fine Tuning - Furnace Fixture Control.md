# Low furnace fuel fixture control

The second A06 training fixture, `train_furnace`, passed scripted and idle controls. Scripted maintenance survived twenty game minutes with 375 new iron plates and zero failed actions. Idle failed after 2 game minutes, with minute outputs of [3, 0]. Both started from the same native save and exactly matching physical snapshots. These are environment controls; Qwen and training were not run.

## Methods and measured outcomes

The unchanged [A06 protocol](A06%20-%20Qwen%20Fine%20Tuning%20-%20Protocol.md) prescribes three stored coal and 3 MJ burning energy in the drill, zero stored coal and 1 MJ burning energy in the furnace, twenty output plates, zero carried/chest plates and 400 reserve coal. Preparation applied these values after a verified warm-up, read them back and saved the paused world. Preloaded plates do not count as newly produced plates.

One action advances exactly 900 ticks (15 game seconds); four actions make a 3,600-tick production window. Two consecutive windows below sixteen new plates end the episode. The horizon remains twenty minutes. The scripted policy and game tools are unchanged from the first A06 control. Only the frozen starting recipe differs. Controls execute sequentially at game speed ten, with simulation paused between decisions.

| Control | Game seconds | Decisions | New plates | Failed actions | Episode wall seconds | Endpoint |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Scripted | 1200 | 80 | 375 | 0 | 163.64 | Survived horizon |
| Idle | 120 | 8 | 3 | 0 | 17.09 | Sustained production failure |

Scripted action counts are `{"collect_output": 6, "fuel": 25, "store_plates": 6, "wait": 43}`. Its first executed action was `{"args": {"building_handle": "e3", "coal_count": 3}, "tool": "fuel"}`. Every scripted window produced at least sixteen new plates. The trace recorded 420 newly mined ore and 375 newly consumed ore with no manual ore insertion. Episode wall time excludes preparation, saving, server restarts and helper restoration; no inference latency or acceleration is measured.

The [idle endpoint](../factorio-pilot/evidence/runs/A06-train_furnace-controls-20261006T223803Z/idle/summary.json) retains burner energy, coal, machine status, input ore and plate capacity. Interpret its failure from these fields rather than the stopping label alone. Zero failed tool calls means the allowed wait actions executed; it does not mean the factory was maintained successfully.

At the first observation after fifteen game seconds, the idle furnace reported `NO_FUEL`, with zero stored coal and zero burning energy, while the drill still reported `WORKING` with three stored coal and 750,000 burning joules. Output had risen from twenty preloaded plates to twenty-three and did not rise again. The drill remained working through the ninety-second observation and first reported no fuel at 105 seconds. At termination the furnace still held 35 ore and had 77 free output slots, while the actor retained 400 coal. This supports missed furnace refueling as the first observed production bottleneck; both machines had exhausted fuel by the endpoint. The two-minute failure time is the detection rule, not the exact time the furnace stopped.

## Evidence and reproduction

[Full control record](../factorio-pilot/evidence/runs/A06-train_furnace-controls-20261006T223803Z/) includes evaluated source hashes, readback, scripted and idle traces, minute windows and exact restoration receipts. The native ZIP passed integrity checks: 1,079,441 bytes, SHA-256 `1d3948c9293e62eb1fae43bbd6a86265975a9c73b4b6ea6101fedf5744fbb548`. It remains outside Git at the runtime-relative path recorded by `native_save.json`. Original compose bytes were preserved and the default server command restored afterward.

The runner and helper scripts now accept fixtures from the unchanged frozen registry and validate the selected recipe. Resume additionally checks fixture identity and protocol hash. Supporting all recipe names is not evidence that the remaining seven passed. Both old and new control exports pass the portable verifier; earlier raw evidence is unchanged.

Forty CPU tests and the unchanged exact-hash native gate passed before gameplay. All project-authored C++/CUDA sources were inspected; no native source or GPU setting changed. The portable audit checks export and evaluated-source hashes, protocol identity, matching snapshots, every decision interval, production windows and plate conservation. [Audit receipt](../factorio-pilot/evidence/artifacts/A06-train-furnace-control-audit.json) records the check.

An earlier setup attempt, `A06-train_furnace-controls-20261006T223740Z`, lost stdin at the save acknowledgment and stopped before gameplay; it remains in external runtime storage and is excluded. During the completed run, the first helper-restore connection attempted authentication before server startup completed. Retrying helper restoration passed before the controller advanced any game ticks. This infrastructure event is not a policy failure.

Follow the [two-terminal native-save procedure](A06%20-%20Qwen%20Fine%20Tuning%20-%20Fixture%20Control.md#reproduction), substituting `--fixture train_furnace`, its printed run ID and native save basename. Wait for server readiness before helper restoration, require exact restore checks and `FIXTURE_CONTROL_PASS`, and restore the default server command at the end. Source executes from this public checkout; the Linux environment and save directory remain external runtime storage.

```bash
python scripts/verify_a06_controls.py A06-train_furnace-controls-20261006T223803Z
```

Two of nine fixtures are now validated. Seven controls, the compact shared renderer, dataset construction/audit, a separate QLoRA compatibility and memory probe, and matched model evaluations remain. No training examples have yet been released or used by an optimizer.
