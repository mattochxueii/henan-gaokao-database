"""Allow an optional repository-local dependency directory."""

import sys
from pathlib import Path

local = Path(__file__).resolve().parents[1] / ".deps"
if local.is_dir():
    sys.path.insert(0, str(local))
