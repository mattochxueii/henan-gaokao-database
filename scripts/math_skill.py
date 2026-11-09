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
    action.add_argument("--year-from", type=int)
    action.add_argument("--year-to", type=int)
    action.add_argument("--region")
    action.add_argument("--subject", default="math")
    action.add_argument("--series")
    action.add_argument("--difficulty", type=int)
    action.add_argument("--method")
    action.add_argument("--capability")
    action.add_argument("--target-region")
    action.add_argument("--target-year", type=int, default=2027)
    action.add_argument("--limit", type=int)
    action.add_argument("--legacy-only", action="store_true")
    action.add_argument("--verified-only", action="store_true")
    actions.add_parser("rules")
    action = actions.add_parser("study-split")
    action.add_argument("--holdout-paper", action="append", required=True)
    action.add_argument("--output", type=Path, required=True)
    packet = actions.add_parser("study-packet")
    packet.add_argument("--evaluation-split", type=Path, required=True)
    packet.add_argument("--topic", action="append")
    packet.add_argument("--output", type=Path, required=True)
    planning = actions.add_parser("plan")
    planning.add_argument(
        "--mode",
        choices=("sequence", "derivative", "mixed", "full", "acceptance"),
        required=True,
    )
    planning.add_argument("--profile", default="balanced")
    planning.add_argument("--seed", type=int, default=0)
    planning.add_argument("--output", type=Path)
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
    action.add_argument("--engine", choices=("template", "ai"), default="template")
    action.add_argument("--candidates", type=Path)
    action.add_argument("--model")
    action.add_argument("--allow-template-fallback", action="store_true")
    action.add_argument("--pilot-certificate", type=Path)
    action.add_argument("--specialty-certificate", type=Path, action="append", default=[])
    action.add_argument("--evaluation-split", type=Path)
    action = actions.add_parser("publish")
    action.add_argument("output", type=Path)
    action.add_argument("--student-review", type=Path, required=True)
    action.add_argument("--math-comparison", type=Path, required=True)
    action = actions.add_parser("solution-edition")
    action.add_argument("source", type=Path)
    action.add_argument("--scoring", type=Path, required=True)
    action.add_argument("--output", type=Path, required=True)
    action = actions.add_parser("writing-request")
    action.add_argument("candidates", type=Path)
    action.add_argument("--output", type=Path, required=True)
    action = actions.add_parser("attach-writing")
    action.add_argument("candidates", type=Path)
    action.add_argument("writing", type=Path)
    action.add_argument("--output", type=Path, required=True)
    action = actions.add_parser("verify")
    action.add_argument("run", type=Path)
    action = actions.add_parser("review")
    action.add_argument("run", type=Path)
    action.add_argument("--report", type=Path, required=True)
    action.add_argument("--blind-report", type=Path)
    action.add_argument("--no-export", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        if args.action == "research":
            import national_db
            from local_archive import public_edition

            require(
                not (args.legacy_only and (public_edition(root) or args.verified_only)),
                "公开版使用标准数据包，请省略 --legacy-only",
            )

            extended = any(
                getattr(args, k) is not None
                for k in (
                    "year_from",
                    "year_to",
                    "region",
                    "series",
                    "difficulty",
                    "method",
                    "capability",
                    "target_region",
                )
            )
            if not args.legacy_only and national_db.available(root):
                result = national_db.query(
                    root,
                    topic=args.topic,
                    year=args.year,
                    kind=args.kind,
                    year_from=args.year_from,
                    year_to=args.year_to,
                    region=args.region,
                    subject=args.subject,
                    series=args.series,
                    difficulty=args.difficulty,
                    method=args.method,
                    capability=args.capability,
                    target_region=args.target_region,
                    target_year=args.target_year,
                    limit=args.limit,
                    verified_only=args.verified_only,
                )
            elif extended and not args.legacy_only:
                raise ValueError(
                    "全国历史题面未恢复，无法执行跨年筛选；请先national_cli.py restore"
                )
            else:
                require(
                    args.subject == "math",
                    "旧库适配器仅包含数学，不能将其他学科请求转为数学",
                )
                if not args.legacy_only:
                    logging.warning(
                        "全国历史题面未恢复，本次仅返回已恢复的旧库候选；不代表全国检索完成"
                    )
                result = research(root, args.topic, args.year, args.kind)
            if args.output:
                from storage import atomic_json

                atomic_json(args.output, result)
                result = {
                    "output": str(args.output),
                    "records": len(result),
                    "full_questions_written": True,
                }
        elif args.action == "plan":
            from mathgen.planner import plan

            result = plan(root, args.mode, args.profile, args.seed)
            if args.output:
                from storage import atomic_json

                atomic_json(args.output, result)
        elif args.action == "rules":
            result = rules(root)
        elif args.action == "study-split":
            from mathgen.evaluation import archive_split
            from storage import atomic_json

            split = archive_split(root, args.holdout_paper)
            atomic_json(args.output, split)
            result = {
                "sha256": split["sha256"], "reference": len(split["reference"]),
                "holdout": len(split["holdout"]),
            }
        elif args.action == "study-packet":
            from mathgen.evaluation import verify_split
            from mathgen.planner import context
            from storage import atomic_json

            split = verify_split(root, read_json(args.evaluation_split))
            packet = context(root, evaluation_split=split, strict=True, topics=args.topic)
            atomic_json(args.output, packet)
            result = {"output": str(args.output), "split_sha256": split["sha256"]}
        elif args.action == "generate":
            from mathgen.ai_provider import select_provider

            provider = select_provider(
                args.engine, args.candidates, args.model, args.allow_template_fallback
            )
            require(
                not args.evaluation_split or provider.name != "template",
                "留出集实验不能使用模板",
            )
            if provider.name != "template":
                from mathgen.dynamic import run_ai

                record = run_ai(
                    root,
                    provider,
                    args.output.resolve(),
                    not args.no_export,
                    pilot_certificate=args.pilot_certificate,
                    specialty_certificates=args.specialty_certificate,
                    evaluation_split=read_json(args.evaluation_split) if args.evaluation_split else None,
                )
                result = {
                    "output": str(args.output.resolve()),
                    "mode": "ai",
                    "provider": provider.name,
                    "structure": record["structure"],
                    "status": record["overall_status"],
                }
                print(dumps(result))
                return 0
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
                "generation_mode": "template",
                "fallback_from_ai": args.engine == "ai",
                "output": str(args.output.resolve()),
                "status": record["overall_status"],
                "structure": record["structure"],
                "files": record.get("files", {}),
                "attempts": len(record["events"]),
            }
        elif args.action in ("writing-request", "attach-writing"):
            from mathgen.writing_packet import request, attach
            from storage import atomic_json

            result = (
                request(
                    read_json(args.candidates),
                    read_json(root / "analysis/language-rules.json"),
                )
                if args.action == "writing-request"
                else attach(read_json(args.candidates), read_json(args.writing))
            )
            atomic_json(args.output, result)
            result = {
                "output": str(args.output),
                "status": "写作层请求已输出"
                if args.action == "writing-request"
                else "写作层已核查绑定",
            }
        elif args.action == "publish":
            from mathgen.exam_workflow import publish

            result = publish(args.output, args.student_review, args.math_comparison)
        elif args.action == "solution-edition":
            from mathgen.scoring import render_edition

            result = render_edition(args.source, read_json(args.scoring), args.output)
        elif args.action == "review":
            from mathgen.attestation import attest

            result = attest(
                args.run, args.report, args.blind_report, not args.no_export
            )
        else:
            if args.run.is_dir():
                from mathgen.exam_workflow import verify_certificate

                certificate = read_json(args.run / "publication.json")
                verify_certificate(args.run, certificate)
                print(
                    dumps(
                        {
                            "certificate_valid": True,
                            "questions": certificate["question_count"],
                            "status": certificate["status"],
                            "formal_proof": False,
                        }
                    )
                )
                return 0
            record = read_json(args.run)
            require(
                len(record["questions"]) == len(record["verifications"]),
                "题目与验证条数不符",
            )
            result = []
            for q, v in zip(record["questions"], record["verifications"]):
                assert_fresh(q, v)
                if record.get("generation_mode") == "ai":
                    from mathgen.dynamic import (
                        independent_solve,
                        review,
                        rendered_question,
                    )

                    canonical = rendered_question(q, q["order"])
                    require(
                        q["stem"] == canonical["stem"]
                        and q["options"] == canonical["options"],
                        "题面与数学规格不符",
                    )
                    solved = independent_solve(q["problem"])
                    fresh = {
                        "passed": review(q, solved)["passed"],
                        "status": "重新独立求解完成",
                    }
                else:
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
