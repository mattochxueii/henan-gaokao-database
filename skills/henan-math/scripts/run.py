"""Portable installed-skill launcher."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def locate(explicit=None):
    skill = Path(__file__).resolve().parents[1]
    if explicit:
        roots = [Path(explicit)]
    elif os.environ.get("HENAN_MATH_DB"):
        roots = [Path(os.environ["HENAN_MATH_DB"])]
    elif (skill / "database-link.json").exists():
        link = json.loads((skill / "database-link.json").read_text(encoding="utf-8"))
        roots = [Path(link["absolute_database_root"])] if "absolute_database_root" in link else [
            skill / link["relative_database_root"]]
    else:
        roots = [Path.cwd(), *Path.cwd().parents, skill, *skill.parents]
    for root in roots:
        if (root / "database.json").is_file() and (
            root / "scripts/math_skill.py"
        ).is_file():
            return root.resolve()
    raise ValueError("数据库未定位，请用--database <仓库根目录>或重新安装相对配置")


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--database", type=Path)
    args, rest = parser.parse_known_args()
    try:
        root = locate(args.database)
        return subprocess.run(
            [
                sys.executable,
                str(root / "scripts/math_skill.py"),
                "--root",
                str(root),
                *rest,
            ],
            check=False,
        ).returncode
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
