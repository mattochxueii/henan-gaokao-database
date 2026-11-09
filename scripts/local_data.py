"""Initialize, inspect and import portable local datasets using public-edition commands."""

import bootstrap  # noqa: F401
import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from analysis_db import fingerprint
from gaokao import ROOT, dumps, read_json, read_lines, require
from local_archive import (
    CONTENT,
    install,
    load,
    public_edition,
    read_bundle,
    write_bundle,
)
from national_db import rebuild_index, validate


def split_tables(papers, sources, regions, records, use_existing_versions=False):
    questions, occurrences, answers = {}, [], []
    for record in records:
        question = {"id": record["id"], **{field: record[field] for field in CONTENT}}
        prior = questions.setdefault(question["id"], question)
        require(prior == question, "一个主记录 ID 对应多个题面")
        occurrence = {
            field: value
            for field, value in record.items()
            if field not in (*CONTENT, "id", "answer", "occurrence_id")
        }
        occurrence_id = (
            record.get("occurrence_id")
            or f"{record['paper_id']}:q{record['number']:03d}"
        )
        version = (
            record["version_sha256"] if use_existing_versions else fingerprint(question)
        )
        answer_id = occurrence_id + ":answer"
        occurrence.update(
            id=occurrence_id,
            question_id=question["id"],
            answer_id=answer_id,
            version_sha256=version,
        )
        occurrences.append(occurrence)
        answers.append(
            {
                "id": answer_id,
                "occurrence_id": occurrence_id,
                "version_sha256": version,
                "payload": record.get("answer"),
            }
        )
    return {
        "papers": papers,
        "sources": sources,
        "paper-regions": regions,
        "questions": list(questions.values()),
        "occurrences": occurrences,
        "answers": answers,
    }


def copy_assets(source, target):
    for path in source.rglob("*"):
        require(
            not path.is_symlink() and path.resolve().is_relative_to(source.resolve()),
            "附件目录含链接或越界路径",
        )
        require(
            path.suffix.lower() not in (".key", ".env", ".enc", ".part"),
            "附件中包含密钥或备份",
        )
    shutil.copytree(source, target)


def prepare(document, output, assets=None):
    require(not output.exists(), "输出数据包已存在")
    output.parent.mkdir(parents=True, exist_ok=True)
    records = [
        {"options": {}, "formulas": [], "parts": [], "asset_refs": [], **row}
        for row in document["records"]
    ]
    tables = split_tables(
        document["papers"],
        document["sources"],
        document.get("paper_regions", []),
        records,
    )
    with tempfile.TemporaryDirectory(prefix=".prepare-", dir=output.parent) as folder:
        staging = Path(folder) / "bundle"
        staging.mkdir()
        if assets is not None:
            require(assets.is_dir() and not assets.is_symlink(), "附件目录无效")
            copy_assets(assets, staging / "files")
        write_bundle(staging, document["dataset_id"], "local-only", tables)
        staging.rename(output)
    return {"dataset_id": document["dataset_id"], "records": len(records)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("init")
    commands.add_parser("audit")
    sources = commands.add_parser("sources")
    sources.add_argument("--year", type=int)
    prepare_cmd = commands.add_parser("prepare")
    prepare_cmd.add_argument("input", type=Path)
    prepare_cmd.add_argument("output", type=Path)
    prepare_cmd.add_argument("--assets", type=Path)
    intake = commands.add_parser("import")
    intake.add_argument("bundle", type=Path)
    backup = commands.add_parser("backup")
    backup.add_argument("bundle", type=Path)
    backup.add_argument("output", type=Path)
    backup.add_argument("--key", type=Path, required=True)
    restore = commands.add_parser("restore")
    restore.add_argument("archive", type=Path)
    restore.add_argument("output", type=Path)
    restore.add_argument("--key", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        require(public_edition(root), "此入口面向经构建的公开候选版")
        if args.action == "init":
            result = {**validate(root), **rebuild_index(root)}
        elif args.action == "audit":
            result = validate(root)
        elif args.action == "sources":
            result = [
                row
                for row in read_lines(root / "national/source-catalog.jsonl")
                if args.year is None or row["year"] == args.year
            ]
        elif args.action == "prepare":
            result = prepare(read_json(args.input), args.output.resolve(), args.assets)
        elif args.action == "import":
            result = install(root, args.bundle.resolve())
        elif args.action == "backup":
            from storage import backup as encrypt

            bundle = args.bundle.resolve()
            require(
                not args.key.resolve().is_relative_to(bundle)
                and not args.output.resolve().is_relative_to(bundle),
                "密钥及备份必须位于待备份目录之外",
            )
            read_bundle(bundle, check_files=True)
            result = encrypt(bundle, args.output, args.key)
        else:
            from storage import restore as decrypt

            require(not args.output.exists(), "输出数据包已存在")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(
                prefix=".restore-local-", dir=args.output.parent
            ) as folder:
                staging = Path(folder) / "bundle"
                decrypt(args.archive, args.key, staging)
                manifest, _, _ = read_bundle(staging, check_files=True)
                staging.rename(args.output)
            result = {"dataset_id": manifest["dataset_id"], "restored": True}
        print(dumps(result))
        return 0
    except ImportError:
        print("个人加密备份需要安装 requirements-backup.txt", file=sys.stderr)
        return 1
    except (KeyError, TypeError, ValueError, OSError) as exc:
        print(dumps({"error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
