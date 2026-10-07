"""Resolve local runtime storage independently of the source checkout."""

import os
from pathlib import Path


def runtime_home():
    return Path(os.environ.get("FACTORIO_PILOT_HOME", Path.home() / "factorio-pilot")).expanduser().resolve()
