"""Install a project Skill using a relative database link."""

import argparse
import json
import os
from pathlib import Path
import shutil
from gaokao import ROOT, require

SKILLS = ("henan-math", "gaokao-platform", "chemistry-gaokao")


def install(root, destination, skill_name="henan-math"):
    require(skill_name in SKILLS, "未登记的项目技能")
    require(
        not destination.exists(), "技能目标目录已存在，请选择新的目录并保留既有安装"
    )
    source = root / "skills" / skill_name
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
    parser.add_argument("--skill", choices=SKILLS, default=SKILLS[0])
    parser.add_argument("--destination", type=Path)
    args = parser.parse_args()
    destination = args.destination or ROOT / ".agents/skills" / args.skill
    print(json.dumps(install(ROOT, destination.resolve(), args.skill), ensure_ascii=False))
