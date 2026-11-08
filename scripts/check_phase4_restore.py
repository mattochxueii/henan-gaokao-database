"""Relocate an archive, recover private data with a separate key, run the installed v2 Skill."""

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
    p.add_argument("--report", type=Path, required=True)
    a = p.parse_args()
    target = a.output.resolve()
    require(not target.exists(), "使用全新目录")
    target.mkdir(parents=True)
    with zipfile.ZipFile(a.archive) as z:
        require(sum(x.file_size for x in z.infolist()) < 2_000_000_000, "ZIP过大")
        for info in z.infolist():
            item = Path(info.filename)
            require((target / item).resolve().is_relative_to(target), "ZIP路径越界")
            require(
                ".private" not in item.parts and item.suffix not in (".key", ".env"),
                "密钥或原文不应打包",
            )
        z.extractall(target)
    checkout = target / "henan-gaokao-database"
    require(not (checkout / ".private").exists(), "恢复前已有原文")
    shutil.copytree(ROOT / ".deps", checkout / ".deps")
    venv.EnvBuilder(with_pip=False, system_site_packages=False).create(
        target / "python"
    )
    exe = target / (
        "python/Scripts/python.exe" if sys.platform == "win32" else "python/bin/python"
    )

    def call(*args):
        result = subprocess.run(
            [str(exe), *map(str, args)],
            cwd=checkout,
            capture_output=True,
            encoding="utf-8",
            timeout=240,
        )
        require(result.returncode == 0, "新环境运行失败：" + result.stderr[-800:])
        return json.loads(result.stdout)

    restored = call("scripts/private_data.py", "restore", "--key", a.key.resolve())
    validated = call("scripts/cli.py", "validate")
    queries = {}
    for year, number in ((2025, 1), (2026, 17)):
        rows = call(
            "scripts/cli.py",
            "query",
            "--year",
            year,
            "--subject",
            "math",
            "--number",
            number,
        )
        require(rows and rows[0]["stem"], "缺少完整候选题面")
        queries[f"{year}:{number}"] = {
            "stem_characters": len(rows[0]["stem"]),
            "full_candidate": True,
        }
    call("scripts/install_math_skill.py")
    launcher = ".agents/skills/henan-math/scripts/run.py"
    research = {
        topic: len(call(launcher, "research", "--topic", topic))
        for topic in ("数列", "导数")
    }
    generated = call(
        launcher,
        "generate",
        "--engine",
        "ai",
        "--candidates",
        "experiments/phase4/proposals/pilot.json",
        "--output",
        "experiments/relocated-pilot",
    )
    require(generated["structure"]["questions"] == 5, "重放题量错误")
    code = "import sys;sys.path.insert(0,'scripts');import bootstrap;from pathlib import Path;from gaokao import read_json;from analysis_db import fingerprint;from mathgen.exam_workflow import verify_certificate; folders=['pilot-v2','final/fullA','final/fullB'];[verify_certificate(Path('experiments/phase4')/f,read_json(Path('experiments/phase4')/f/'publication.json')) for f in folders]; assert fingerprint(read_json(Path('experiments/relocated-pilot/student-text.json')))==fingerprint(read_json(Path('experiments/phase4/pilot-v2/student-text.json')));print('{\"certificates_valid\":3,\"replayed_text_same\":true}')"
    certificates = call("-c", code)
    report = {
        "archive_sha256": digest(a.archive),
        "fresh_directory": True,
        "isolated_interpreter": True,
        "network_used": False,
        "key_separate": True,
        "original_absolute_path_required": False,
        "restored_files": restored["files"],
        "candidate_questions": validated["local_reference_questions"],
        "queries": queries,
        "research_counts": research,
        "v2_ai_questions_replayed": 5,
        "replay_is_new_ai_creation": False,
        "fresh_render_status": "新渲染仅为待审草稿；沿用的冻结成品证书逐字节验证",
        **certificates,
        "dependencies": "复制已安装依赖；全新电脑按requirements.txt安装，PDF需要Poppler及中文字体",
    }
    atomic_json(a.report, report)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
