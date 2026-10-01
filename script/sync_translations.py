"""Regenerate English strings while retaining resolved Home Assistant references."""

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent / "custom_components" / "myuplink"


def resolve(source: Any, previous: Any) -> Any:
    """Reuse existing resolved common strings and copy integration-owned strings."""
    if isinstance(source, dict):
        return {
            key: resolve(
                value, previous.get(key) if isinstance(previous, dict) else None
            )
            for key, value in source.items()
        }
    if isinstance(source, str) and source.startswith("[%key:"):
        if not isinstance(previous, str) or previous.startswith("[%key:"):
            raise ValueError(
                f"Provide an English value for the new common reference {source}"
            )
        return previous
    return source


def main() -> None:
    """Write English translations or verify they match strings.json."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    target = ROOT / "translations" / "en.json"
    source = json.loads((ROOT / "strings.json").read_text())
    previous = json.loads(target.read_text())
    generated = (
        json.dumps(resolve(source, previous), indent=2, ensure_ascii=False) + "\n"
    )
    if args.check:
        if target.read_text() != generated:
            raise SystemExit(
                "English translations differ; run python3 script/sync_translations.py"
            )
    else:
        target.write_text(generated)


if __name__ == "__main__":
    main()
