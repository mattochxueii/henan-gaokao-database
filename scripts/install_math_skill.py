"""Install the project Skill using a relative database link."""

import argparse
import json
import os
from pathlib import Path
import shutil
from gaokao import ROOT, require


def install(root, destination):
    require(
        not destination.exists(), "技能目标目录已存在，请选择新的目录并保留既有安装"
    )
    source = root / "skills/henan-math"
    require((source / "SKILL.md").is_file(), "技能源缺失")
    relative = os.path.relpath(root, destination)
    shutil.copytree(source, destination)
    (destination / "database-link.json").write_text(
        json.dumps({"relative_database_root": relative}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return {
        "skill_path": str(destination),
        "database_link_type": "relative",
        "installed": True,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--destination", type=Path, default=ROOT / ".agents/skills/henan-math"
    )
    args = parser.parse_args()
    print(json.dumps(install(ROOT, args.destination.resolve()), ensure_ascii=False))
