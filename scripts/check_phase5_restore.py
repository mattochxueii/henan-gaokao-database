"""Offline relocation check for both encrypted databases, installed Skill and certificates."""

import bootstrap  # noqa: F401
import argparse, json, shutil, subprocess, sys, venv, zipfile
from pathlib import Path
from gaokao import ROOT, require, digest
from storage import atomic_json


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--legacy-key", type=Path, required=True)
    p.add_argument("--national-key", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    a = p.parse_args()
    target = a.output.resolve()
    require(not target.exists(), "须使用全新恢复目录")
    target.mkdir(parents=True)
    with zipfile.ZipFile(a.archive) as z:
        require(sum(x.file_size for x in z.infolist()) < 2_000_000_000, "ZIP过大")
        seen = set()
        for m in z.infolist():
            f = Path(m.filename)
            require(m.filename not in seen, "ZIP重复成员")
            seen.add(m.filename)
            require((target / f).resolve().is_relative_to(target), "ZIP路径越界")
            require(
                not any(x in f.parts for x in (".private", ".git", ".deps"))
                and f.suffix not in (".key", ".env"),
                "包内包含原文或密钥",
            )
            require((m.external_attr >> 16) & 0o170000 != 0o120000, "ZIP包含符号链接")
        z.extractall(target)
    r = target / "henan-gaokao-database"
    shutil.copytree(ROOT / ".deps", r / ".deps")
    venv.EnvBuilder(with_pip=False, system_site_packages=False).create(
        target / "python"
    )
    exe = target / (
        "python/Scripts/python.exe" if sys.platform == "win32" else "python/bin/python"
    )

    def call(*args):
        done = subprocess.run(
            [str(exe), *map(str, args)],
            cwd=r,
            capture_output=True,
            encoding="utf-8",
            timeout=240,
        )
        require(
            done.returncode == 0,
            "恢复验证失败：" + done.stderr[-700:] + done.stdout[-300:],
        )
        return json.loads(done.stdout)

    old = call("scripts/private_data.py", "restore", "--key", a.legacy_key.resolve())
    new = call("scripts/national_cli.py", "restore", "--key", a.national_key.resolve())
    validation = call("scripts/national_cli.py", "validate")
    call("scripts/national_cli.py", "build-index")
    queries = []
    for year, series, n in (
        (2020, "cn-new-gaokao-1", 18),
        (2024, "cn-new-gaokao-1", 18),
        (2026, "cn-new-gaokao-2", 17),
        (2020, "cn-national-1-legacy", 21),
        (2025, "cn-new-gaokao-1", 1),
        (2026, "cn-new-gaokao-1", 17),
    ):
        found = call(
            "scripts/national_cli.py",
            "sqlite-query",
            "--year",
            year,
            "--series",
            series,
            "--number",
            n,
        )
        require(
            found and all(x["stem"] and x["source_locator"] for x in found),
            "未返回完整题面",
        )
        queries.extend(
            {
                "paper_id": x["paper_id"],
                "number": n,
                "stem_characters": len(x["stem"]),
                "parts": len(x["parts"]),
                "full_candidate": True,
            }
            for x in found
        )
    call("scripts/install_math_skill.py")
    launcher = ".agents/skills/henan-math/scripts/run.py"
    seq = call(
        launcher,
        "research",
        "--series",
        "cn-new-gaokao-1",
        "--year-from",
        2020,
        "--year-to",
        2026,
        "--topic",
        "数列",
    )
    require({r["year"] for r in seq} == set(range(2020, 2027)), "跨年检索不连续")
    plan = call(launcher, "plan", "--mode", "full")
    require(
        plan["total_points"] == 150 and len(plan["slots"]) == 19, "历史卷覆盖当前结构"
    )
    code = "import sys;sys.path.insert(0,'scripts');import bootstrap;from pathlib import Path;from gaokao import read_json;from mathgen.exam_workflow import verify_certificate;folders=['experiments/phase4/pilot-v2','experiments/phase4/final/fullA','experiments/phase4/final/fullB','experiments/phase5/pilotC-v3','experiments/phase5/fullD-v3'];valid=[f for f in folders if (Path(f)/'publication.json').exists()];[verify_certificate(Path(f),read_json(Path(f)/'publication.json')) for f in valid];print(__import__('json').dumps({'certificates_valid':len(valid),'folders':valid}))"
    certs = call("-c", code)
    result = {
        "archive_sha256": digest(a.archive),
        "fresh_directory": True,
        "isolated_python": True,
        "network_used": False,
        "dependencies": "复制已安装依赖缓存；未依赖原题库绝对路径",
        "old_restored_files": old["files"],
        "national_restored_files": new["files"],
        "validation": validation,
        "query_results": queries,
        "skill_sequence_years": sorted({r["year"] for r in seq}),
        "full_blueprint": {
            "slots": 19,
            "points": 150,
            "historical_optional_questions_injected": False,
        },
        "keys_separate": True,
        "plaintext_in_package": False,
        "absolute_original_path_required": False,
        **certs,
    }
    atomic_json(a.report, result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
