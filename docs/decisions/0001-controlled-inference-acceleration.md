# 0001 - Separate inference acceleration from policy changes

- Status: Proposed
- Date: 2026-10-06

## Context

K01 measures a standalone RMSNorm kernel, while the maintenance agent still uses Qwen's original forward path. The next experiment needs to establish application value and compare against an optimized reference. At the same time, context-memory improvements and possible training can change the model's actions. Combining all of these at once would make a faster or more successful episode difficult to explain.

## Decision drivers

The design must preserve recorded evidence, retain supported-input bounds, make fallback visible and connect operator work to complete response timing. The agreed scope uses sequential experiments with the acceleration design settled before further runs.

## Options considered

A global replacement of every norm is simple to describe but affects unsupported attention-head norms and makes restoration harder. An immediate switch to another serving stack could add batching or caching, but also changes several implementation variables before the existing application has an integrated baseline. A guarded adapter on the existing model permits a smaller comparison and retains the current game loop.

## Decision

Propose instance-local replacement of compatible full-width Qwen norms, with the original forward retained for known unsupported calls. Compare eager reference, custom RMSNorm and compiled reference independently. Evaluate exact-prefix caching afterward with one fixed backend. Keep context compression, memory policy, parallel serving and training outside the first acceleration comparison. The canonical mechanism and planned measurement boundaries are in [Inference acceleration design](../Inference%20Acceleration%20Design.md).

## Consequences

This approach preserves the model weights and action interface while making custom dispatch auditable. It requires restoration logic, explicit unsupported-call reporting and a separate optimized-baseline implementation. Compilation may remove much of the eager-reference overhead, and prefix copying may cost more than its saved work. Either outcome is useful evidence. The design is proposed; runtime compatibility and speed remain unmeasured.

## Evidence

[K01](../../outputs/K01%20-%20RMSNorm%20-%20Reviewed%20Benchmark.md) provides operator measurements and correctness evidence. [A04](../../outputs/A04%20-%20Maintenance%20-%20Results.md) separates generation time from other episode costs. Those reports do not establish integrated acceleration. Implementation and eventual results must preserve their evaluated sources and the [native review requirements](../../CONVENTIONS.md).
