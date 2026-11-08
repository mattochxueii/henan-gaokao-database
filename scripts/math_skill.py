"""Research and generation entry point used by the installable Skill."""

import bootstrap
import argparse
import json
import logging
from pathlib import Path
import sys
from gaokao import ROOT, dumps, read_json, require
from analysis_db import research, rules
from mathgen.pipeline import run, custom_blueprint
from mathgen.quality import verify, assert_fresh


def main(argv=None):
    parser = argparse.ArgumentParser(description="河南数学真题研究与命题原型")
    parser.add_argument("--root", type=Path, default=ROOT)
    actions = parser.add_subparsers(dest="action", required=True)
    action = actions.add_parser("research")
    action.add_argument("--topic")
    action.add_argument("--year", type=int)
    action.add_argument("--kind")
    action.add_argument("--output", type=Path)
    actions.add_parser("rules")
    action = actions.add_parser("generate")
    action.add_argument("--mode", choices=("sequence", "derivative", "mixed", "full"))
    action.add_argument("--topic")
    action.add_argument("--count", type=int, default=1)
    action.add_argument(
        "--kind",
        choices=("single_choice", "multiple_choice", "fill_in", "constructed_response"),
        default="constructed_response",
    )
    action.add_argument("--difficulty", type=int, choices=range(1, 6))
    action.add_argument("--seed", type=int, default=20261107)
    action.add_argument("--output", type=Path, required=True)
    action.add_argument("--no-export", action="store_true")
    action = actions.add_parser("verify")
    action.add_argument("run", type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        if args.action == "research":
            result = research(root, args.topic, args.year, args.kind)
            if args.output:
                from storage import atomic_json

                atomic_json(args.output, result)
        elif args.action == "rules":
            result = rules(root)
        elif args.action == "generate":
            require(bool(args.mode) != bool(args.topic), "请选择--mode或--topic之一")
            plan = (
                custom_blueprint(
                    root, args.topic, args.count, args.kind, args.difficulty
                )
                if args.topic
                else None
            )
            record = run(
                root,
                args.mode or "custom",
                args.seed,
                args.output.resolve(),
                not args.no_export,
                plan,
            )
            result = {
                "output": str(args.output.resolve()),
                "status": record["overall_status"],
                "structure": record["structure"],
                "files": record.get("files", {}),
                "attempts": len(record["events"]),
            }
        else:
            record = read_json(args.run)
            require(
                len(record["questions"]) == len(record["verifications"]),
                "题目与验证条数不符",
            )
            result = []
            for q, v in zip(record["questions"], record["verifications"]):
                assert_fresh(q, v)
                fresh = verify(q)
                require(fresh["passed"], "重新验证失败 " + q["id"])
                result.append(
                    {"id": q["id"], "passed": True, "status": fresh["status"]}
                )
        print(dumps(result))
        return 0
    except Exception as error:
        logging.error("%s", error)
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
