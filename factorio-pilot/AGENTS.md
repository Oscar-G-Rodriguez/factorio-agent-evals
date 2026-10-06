# Factorio project instructions

The user requires a full review of all project-authored C++ and CUDA code before any further runs, including subsequent revisions. Read `../outputs/CUDA and C++ Source Review.md` and validate `tools/cuda_review.py` before running GPU/model entry points. A new or changed native source invalidates the recorded review; do not regenerate the manifest automatically as a substitute for inspecting the code.

Review bounds, sizes, allocation ownership, synchronization, races, stream/device dispatch, numerical conversion and error reporting. Begin runtime validation with small correctness cases; benchmark or integrate custom code only after correctness evidence matches the reviewed hashes. Archive old evidence before replacing it. Do not execute historical source snapshots with known superseded defects.

Leave GPU clocks, voltage, power, firmware and Windows timeout settings unchanged. On October 6 the user explicitly authorized temporarily enabling NVIDIA's debugger-interface registry value for sanitizer checks. Preserve and restore its prior value and record both validation and restoration results. This permission does not cover other system settings. Record unavailable sanitizer validation accurately.

Continue the agreed Factorio agent, memory evaluation and integrated C++/CUDA project within the two-day scope. Keep frozen pilot results separate from revised interfaces and assisted development runs.
