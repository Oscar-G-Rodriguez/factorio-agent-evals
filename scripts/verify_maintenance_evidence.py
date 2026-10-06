#!/usr/bin/env python3
"""Read retained maintenance runs without starting Factorio or loading a model."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "factorio-pilot" / "evidence" / "runs"
CASES = {
    "idle": ("maintenance-idle-20261006T043628Z", 8, 120, "sustained_production_failure"),
    "model": ("maintenance-model-20261006T044058Z", 44, 660, "sustained_production_failure"),
    "scripted": ("maintenance-scripted-20261006T043718Z", 80, 1200, "survived_simulation_limit"),
}


def inspect(name, folder, decisions, seconds, endpoint):
    run = RUNS / folder
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    steps = [json.loads(line) for line in (run / "steps.jsonl").read_text(encoding="utf-8").splitlines() if line]
    windows = summary["measurement_windows"]
    plates = [window["iron_plates"] for window in windows]
    assert summary["controller"] == name, folder
    assert summary["steps"] == decisions == len(steps), folder
    assert summary["simulated_seconds"] == seconds, folder
    assert summary["stop_reason"] == endpoint, folder
    assert len(windows) == seconds // 60, folder
    assert all(window["actual_ticks"] == 3600 and window["target"] == 16 for window in windows), folder
    assert sum(bool(step["failed_action"]) for step in steps) == summary["failed_actions"], folder
    if endpoint == "sustained_production_failure":
        assert windows[-1]["consecutive_low_windows"] == 2, folder
    else:
        assert all(window["consecutive_low_windows"] < 2 for window in windows), folder
    return plates, summary["failed_actions"]


def main():
    for name, (folder, decisions, seconds, endpoint) in CASES.items():
        plates, failures = inspect(name, folder, decisions, seconds, endpoint)
        print(f"{name:8} {seconds // 60:2} min | {decisions:2} decisions | {failures:2} failed | {endpoint}")
        print("         plates/min: " + " ".join(f"{n:2}" for n in plates))
    print("Verified retained summaries and trace counts; no live game or GPU run.")


if __name__ == "__main__":
    main()
