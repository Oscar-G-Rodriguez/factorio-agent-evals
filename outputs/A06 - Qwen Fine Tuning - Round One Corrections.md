# A06 — Round one corrections

All 16 planned candidates were examined, at most four per training factory. The release audit accepted 13 distinct examples across all four factories; three replays failed the full-horizon requirement. Round two has begun from round one's selected checkpoint 40 with a fresh optimizer. It uses 160 original examples plus 160 explicitly sampled corrections. No final test factory has been opened.

Accepted corrections were executed from exact saved pre-action states, preserving the model's actual preceding decisions. They cleared blocked storage and survived scripted continuation through the original 20-minute horizon. This verifies labels and recovery potential; it does not show that Qwen learned the repairs or performed better.

Rejected repairs are retained as evidence and excluded from training. They transferred plates successfully but could not prevent two consecutive low-production windows given the preceding model decisions. Repairing storage late in an episode is therefore insufficient under the frozen failure rule. We did not erase the earlier failure streak or restart the clock to make these labels qualify.

## Evidence

[Execution and audit receipts](../factorio-pilot/evidence/artifacts/A06-round1-correction-results.json) preserve accepted and rejected replay proofs. [Immutable correction release](../factorio-pilot/evidence/datasets/A06-corrections-round1-20261007T140230Z/manifest.json) records its hashes and fixture coverage. The release contains model-visible messages and executed corrective labels; binary saves and model weights remain outside Git. Full source and continuation traces will be included in final experiment packaging.

Round-two checkpoint validation remains pending. Lower training loss and successfully scripted repairs are not model-improvement evidence.
