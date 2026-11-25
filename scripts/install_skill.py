"""Install the project's unified six-subject skill."""
import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile

from gaokao import ROOT, dumps, read_json, require

OFFICIAL_SKILL = "gaokao-platform"
SKILLS = (OFFICIAL_SKILL,)
LINK = "database-link.json"


def install(root, destination, skill_name=OFFICIAL_SKILL):
    """Install to an exact skill directory; the old entry point keeps this contract."""
    require(skill_name in SKILLS, "未登记的项目技能")
    root, destination = root.resolve(), destination.resolve()
    source = root/"skills"/skill_name
    require((source/"SKILL.md").is_file(), "缺技能源文件")
    require(not destination.is_relative_to(source), "安装位置不能位于技能源目录内")
    try:
        link = {"relative_database_root":os.path.relpath(root,destination)}
    except ValueError:  # Windows skill home and cloned project can be on different drives.
        link = {"absolute_database_root":str(root)}
    link_type = "relative" if "relative_database_root" in link else "absolute"
    ignored = shutil.ignore_patterns("__pycache__", "*.pyc", LINK)
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temp:
        draft = Path(temp)/skill_name
        shutil.copytree(source,draft,ignore=ignored)
        (draft/LINK).write_text(json.dumps(link,ensure_ascii=False)+"\n",encoding="utf-8")
        if destination.exists():
            identical = destination.is_dir() and (destination/LINK).is_file() and read_json(destination/LINK) == link
            identical = identical and all((destination/rel).is_file() and (destination/rel).read_bytes()==src.read_bytes()
                                          for src in draft.rglob("*") if src.is_file() and (rel:=src.relative_to(draft)))
            require(identical, "该技能目录已有不同内容，请保留原目录并指定另一安装位置")
        else:
            draft.rename(destination)
    return {"skill_path":str(destination),"database_link_type":link_type,"installed":True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination",type=Path,help="宿主技能目录，或以 gaokao-platform 结尾的完整安装路径")
    args = parser.parse_args(argv)
    destination = args.destination or ROOT/".agents"/"skills"
    if destination.name != OFFICIAL_SKILL:
        destination /= OFFICIAL_SKILL
    try:
        print(dumps(install(ROOT,destination)))
    except (OSError,ValueError) as error:
        parser.exit(1,f"{error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
