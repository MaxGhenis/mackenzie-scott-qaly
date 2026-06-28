"""Export the parameter file as JSON so other runtimes (e.g. the TypeScript web
port at maxghenis.com) consume the exact same numbers — `parameters.yaml` stays
the single source of truth.

    uv run msqaly-export-params              # -> web/params.json
    uv run msqaly-export-params path.json    # custom path
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .model import DEFAULT_PARAMS, load_params

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "web" / "params.json"


def export(out: str | Path = DEFAULT_OUT) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    params = load_params(DEFAULT_PARAMS)
    # Stable, diff-friendly JSON. The structure mirrors parameters.yaml exactly,
    # so a TS port can read it with no transformation.
    out.write_text(json.dumps(params, indent=2, sort_keys=False) + "\n")
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    out = export(argv[0] if argv else DEFAULT_OUT)
    print(f"Wrote {out} ({out.stat().st_size} bytes) from {DEFAULT_PARAMS.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
