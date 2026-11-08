"""Package reviewable source, encrypted data, and delivered experiments."""

import bootstrap
from pathlib import Path
import subprocess
import zipfile
from gaokao import ROOT, require
from storage import atomic_json


def package():
    paths = (
        subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
        .decode("utf-8")
        .split("\0")
    )
    paths = [path for path in paths if path]
    require(paths, "需要先审阅并暂存项目文件")
    for value in paths:
        path = Path(value)
        require(
            not any(
                part in (".private", ".deps", ".git", ".agents") for part in path.parts
            )
            and path.suffix not in (".key", ".env"),
            "暂存区包含私有目录或密钥",
        )
    target = ROOT.parent / "henan-gaokao-database-phase2.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for value in paths:
            archive.write(ROOT / value, "henan-gaokao-database/" + value)
        # Reproducible formula PNGs are omitted from Git but retained in the user package.
        staged = set(paths)
        for path in (ROOT / "experiments").glob("*/assets/*.png"):
            relative = path.relative_to(ROOT).as_posix()
            if relative not in staged:
                archive.write(path, "henan-gaokao-database/" + relative)
    skill = ROOT / "skills/henan-math"
    skill_target = ROOT.parent / "henan-math-skill.zip"
    with zipfile.ZipFile(skill_target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in skill.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                archive.write(path, "henan-math/" + path.relative_to(skill).as_posix())
    print(target)
    print(skill_target)


if __name__ == "__main__":
    package()
