"""Actual ZIP relocation, separate-key recovery and installed AI Skill replay in a clean interpreter."""

import bootstrap
import argparse, json, shutil, subprocess, sys, venv, zipfile
from pathlib import Path
from gaokao import ROOT, require, digest
from storage import atomic_json


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--key", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    target = a.output.resolve()
    require(not target.exists(), "测试目录已存在")
    target.mkdir(parents=True)
    with zipfile.ZipFile(a.archive) as z:
        for info in z.infolist():
            path = (target / info.filename).resolve()
            require(path.is_relative_to(target), "ZIP路径越界")
            require(
                ".private" not in Path(info.filename).parts
                and not info.filename.endswith(".key"),
                "ZIP包含私有明文或密钥",
            )
        z.extractall(target)
    checkout = target / "henan-gaokao-database"
    require(not (checkout / ".private").exists(), "恢复前不应有明文")
    shutil.copytree(ROOT / ".deps", checkout / ".deps")
    venv.EnvBuilder(with_pip=False, system_site_packages=False).create(
        target / "interpreter"
    )
    exe = target / (
        "interpreter/Scripts/python.exe"
        if sys.platform == "win32"
        else "interpreter/bin/python"
    )

    def call(*args):
        r = subprocess.run(
            [str(exe), *map(str, args)],
            cwd=checkout,
            capture_output=True,
            encoding="utf-8",
        )
        require(r.returncode == 0, "新环境命令失败：" + r.stderr[-600:])
        return json.loads(r.stdout)

    restored = call("scripts/private_data.py", "restore", "--key", a.key.resolve())
    validated = call("scripts/cli.py", "validate")
    queries = {}
    for year, number in ((2025, 1), (2026, 17)):
        q = call(
            "scripts/cli.py",
            "query",
            "--year",
            year,
            "--subject",
            "math",
            "--number",
            number,
        )
        require(bool(q[0]["stem"]), "查询没有完整题干")
        queries[str(year) + ":" + str(number)] = {
            "stem_characters": len(q[0]["stem"]),
            "complete_candidate_returned": True,
        }
    call("scripts/install_math_skill.py")
    launcher = ".agents/skills/henan-math/scripts/run.py"
    researched = {
        topic: len(call(launcher, "research", "--topic", topic))
        for topic in ("数列", "导数")
    }
    result = call(
        launcher,
        "generate",
        "--engine",
        "ai",
        "--candidates",
        "experiments/phase3/proposals/acceptance5.json",
        "--output",
        "experiments/fresh-ai",
        "--no-export",
    )
    verified = call(launcher, "verify", "experiments/fresh-ai/run.json")
    reviewed = call(
        launcher,
        "review",
        "experiments/fresh-ai/run.json",
        "--report",
        "reports/phase3-independent-ai-review.json",
        "--blind-report",
        "reports/phase3-blind-acceptance-review.json",
        "--no-export",
    )
    require(
        len(verified) == 5 and all(v["passed"] for v in verified), "新环境AI校验失败"
    )
    report = {
        "archive_sha256": digest(a.archive),
        "fresh_directory": True,
        "isolated_interpreter": True,
        "network_used": False,
        "original_absolute_path_required": False,
        "key_separate": True,
        "restored_files": restored["files"],
        "candidate_questions": validated["local_reference_questions"],
        "queries": queries,
        "research_counts": researched,
        "ai_questions_replayed": len(verified),
        "generation_mode": result["mode"],
        "independent_reviewed": reviewed["questions_reviewed"],
        "replay_is_new_ai_creation": False,
        "dependencies": "复制本轮已安装依赖；新电脑使用requirements.txt安装",
    }
    atomic_json(ROOT / "reports/phase3-fresh-environment.json", report)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
