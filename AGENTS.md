# Factorio Agent Evals

Read `CONVENTIONS.md`, `factorio-pilot/AGENTS.md`, and the selected result/protocol before continuing. The user requires full review of all project-authored C++/CUDA sources before GPU runs; the exact-hash gate must remain in place. Never approve changed native code by regenerating a manifest without inspection.

Keep original pilot, guided construction, logistics, maintenance and offline diagnostic results distinct. Preserve source hashes, numerical checks and previous evidence. Offline proposed actions are not executed gameplay results. Do not claim whole-model acceleration before integration and matched measurement.

Existing host run scripts target the original Codex development checkout. The Second Brain Repository checkout is a separately versioned copy of the same GitHub repository. Confirm which checkout a command executes before changing or running it, and commit/push the intended checkout's work explicitly. Do not assume the other checkout updates automatically.

Keep model weights, game executables, environments, unrelated projects and scratch downloads outside Git. Never add the entire original workspace indiscriminately. The adjacent Second Brain project notes hold durable context; live tasks and scheduling remain in their existing owning systems.
