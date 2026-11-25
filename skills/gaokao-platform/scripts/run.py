"""Launch the unified platform through the installed relative project link."""

import argparse
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--database", type=Path)
    args, commands = parser.parse_known_args()
    skill = Path(__file__).resolve().parents[1]
    try:
        link = skill / "database-link.json"
        if args.database:
            root = args.database.resolve()
        elif link.is_file():
            data = json.loads(link.read_text(encoding="utf-8"))
            if "absolute_database_root" in data:
                root = Path(data["absolute_database_root"]).resolve()
            else:
                root = (skill / data["relative_database_root"]).resolve()
        else:
            root = skill.parents[1]
        entry = root / "scripts/gaokao_platform.py"
        if not entry.is_file():
            raise ValueError("请用 --database 指向项目根目录")
        return subprocess.run(
            [sys.executable, str(entry), "--root", str(root), *commands], check=False
        ).returncode
    except (OSError, ValueError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
