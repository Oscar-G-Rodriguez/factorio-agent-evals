# One maintenance episode, read from retained evidence

The controller begins after a verified one-minute warm-up. A burner drill supplies a furnace; a chest is available for finished plates. Every action advances the game by 15 seconds, even when the action fails. Each number below is one complete 60-second production window. The target is 16 plates per window; two low windows in a row end the episode.

```text
game minute       01 02 03 04 05 06 07 08 09 10 11
Qwen plates       18 19 19 19 14 18 19 19 18 15 00
target            16 16 16 16 16 16 16 16 16 16 16
                                               low low → failure

scripted control  18 19 19 19 18 19 19 19 18 19 19 19 18 19 19 19 18 19 19 19
                 └──────────────────── survived 20 minutes ────────────────────┘
```

The fifth Qwen minute is low, but production recovers in minute six, so the episode continues. The last two minutes are low in succession. The endpoint is **11 game minutes and 44 decisions**, including **13 failed collection actions**. Qwen had filled its 100-plate carried inventory and never used the storage action. At the end, the chest was empty, the furnace held 95 plates, and the drill was unfueled while 461 coal remained in reserve. The 195 recorded plates reconcile as 100 carried plus 95 in the furnace. These observations show missed storage and fuel decisions; they do not establish one exclusive cause for every error.

The scripted controller used the same allowed actions and starting fixture. It stored plates six times, completed 80 decisions without a failed action, and reached the 20-minute limit with 18–19 plates in each measured minute. Its survival establishes that the task was reachable, not that Qwen should generalize from this single fixture.

To check the numbers from a clone, run `python scripts/verify_maintenance_evidence.py`. It reads the [Qwen summary and trace](../factorio-pilot/evidence/runs/maintenance-model-20261006T044058Z/summary.json), [scripted summary and trace](../factorio-pilot/evidence/runs/maintenance-scripted-20261006T043718Z/summary.json), and idle negative control. The [full maintenance report](../outputs/A04%20-%20Maintenance%20-%20Results.md) explains the fixture, controls, wall-time scope, and source snapshots. The [storage decision diagnostic](../outputs/A04%20-%20Maintenance%20-%20Storage%20Decision%20Diagnostic.md) proposes actions from saved context only; it did not improve this live episode.
