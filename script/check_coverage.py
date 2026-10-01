"""Require above 95% coverage per integration module and 100% for config flow."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    """Check unrounded branch and statement coverage from coverage.py's report."""
    report = json.loads((ROOT / "coverage.json").read_text())
    failures: list[str] = []
    for module in sorted((ROOT / "custom_components" / "myuplink").glob("*.py")):
        name = module.relative_to(ROOT).as_posix()
        measured = report["files"].get(name)
        if measured is None:
            failures.append(f"{name}: no coverage data")
            continue
        percent = measured["summary"]["percent_covered"]
        print(f"{name}: {percent:.2f}%")
        if module.name == "config_flow.py":
            if percent < 100:
                failures.append(f"{name}: config flow requires 100%")
        elif percent <= 95:
            failures.append(f"{name}: each module must exceed 95%")
    if failures:
        raise SystemExit("\n".join(failures))


if __name__ == "__main__":
    main()
