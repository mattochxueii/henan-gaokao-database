"""National archive command line; full questions, provenance, filters and version-bound answers."""

import bootstrap  # noqa: F401
import argparse, json
from gaokao import ROOT
from storage import atomic_json
import national_db as db


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=__import__("pathlib").Path, default=ROOT)
    a = p.add_subparsers(dest="action", required=True)
    for name in ("query", "research"):
        q = a.add_parser(name)
        for flag, kind in (
            ("year", int),
            ("year-from", int),
            ("year-to", int),
            ("number", int),
            ("difficulty", int),
            ("limit", int),
            ("target-year", int),
        ):
            q.add_argument(
                "--" + flag, type=kind, default=2027 if flag == "target-year" else None
            )
        for flag in (
            "region",
            "series",
            "topic",
            "kind",
            "method",
            "capability",
            "target-region",
        ):
            q.add_argument("--" + flag)
        q.add_argument("--subject", default="math")
        q.add_argument("--include-candidate-usage", action="store_true")
        q.add_argument("--include-quarantined", action="store_true")
        q.add_argument("--output", type=__import__("pathlib").Path)
    q = a.add_parser("reference-pack")
    q.add_argument("--topic")
    q.add_argument("--kind")
    q.add_argument("--limit", type=int, default=12)
    q.add_argument("--target-region", default="河南")
    q.add_argument("--target-year", type=int, default=2027)
    q.add_argument("--output", type=__import__("pathlib").Path)
    for name in ("stats", "validate", "build-index"):
        a.add_parser(name)
    q = a.add_parser("sqlite-query")
    q.add_argument("--year", type=int, required=True)
    q.add_argument("--series", required=True)
    q.add_argument("--number", type=int, required=True)
    q = a.add_parser("restore")
    q.add_argument("--key", type=__import__("pathlib").Path, required=True)
    q.add_argument("--destination", type=__import__("pathlib").Path)
    args = p.parse_args()
    try:
        if args.action in ("query", "research"):
            filters = {
                k: v
                for k, v in vars(args).items()
                if k not in ("root", "action", "output")
            }
            result = db.query(args.root, **filters)
            if args.output:
                atomic_json(args.output, result)
                result = {
                    "output": str(args.output),
                    "records": len(result),
                    "full_questions_written": True,
                }
        elif args.action == "reference-pack":
            result = db.reference_pack(
                args.root,
                topic=args.topic,
                kind=args.kind,
                limit=args.limit,
                target_region=args.target_region,
                target_year=args.target_year,
            )
            if args.output:
                atomic_json(args.output, result)
                result = {
                    "output": str(args.output),
                    "references": len(result["references"]),
                    "full_questions_written": True,
                }
        elif args.action == "stats":
            result = db.statistics(args.root)
        elif args.action == "validate":
            result = db.validate(args.root)
        elif args.action == "build-index":
            result = db.rebuild_index(args.root)
        elif args.action == "sqlite-query":
            result = db.sqlite_query(args.root, args.year, args.series, args.number)
        else:
            from national_backup import restore_national

            result = restore_national(args.root, args.key, args.destination)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError) as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    if hasattr(__import__("sys").stdout, "reconfigure"):
        __import__("sys").stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
