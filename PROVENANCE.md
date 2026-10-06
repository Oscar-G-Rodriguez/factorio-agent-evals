# Provenance of the public snapshot

This public repository was exported from the private project state at commit `6c1254abb3216b5c7820c56f300996f3cb4e1990` on October 6, 2026. It starts with a clean public history so internal correspondence from earlier development commits is not distributed.

The export preserves every included run configuration, JSONL action trace, source snapshot, native source-review record, numerical result, captured tensor, benchmark sample, and measurement report byte-for-byte. The public README was revised for this export. An internal release-review note, a host-readiness inventory, and a captured FLE system prompt were omitted. The latter belongs to the [Factorio Learning Environment](https://github.com/JackHopkins/factorio-learning-environment) and is not needed to inspect the retained results.

The pinned model revision, FLE revision, server version, and package versions are in [runtime setup](factorio-pilot/README.md). Individual run configurations and source snapshots identify the code evaluated in each experiment. The [native review](outputs/CUDA%20and%20C%2B%2B%20Source%20Review.md) and [reviewed benchmark](outputs/Reviewed%20RMSNorm%20Benchmark.md) record the C++/CUDA source hashes and measurement conditions. Rebuilding a manifest does not approve altered native source for GPU execution.

The repository is public for inspection. No license for project-authored source or evidence has been granted yet; upstream packages, model weights, and the Factorio game retain their own terms.
