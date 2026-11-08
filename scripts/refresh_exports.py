"""Re-solve each accepted draft after a solver/export revision."""

import bootstrap
from gaokao import ROOT, read_json, require
from storage import atomic_json
from mathgen.quality import verify
from mathgen.export import export_run
from mathgen.pipeline import blueprint, structure_check
from analysis_db import rules

for mode in ("sequence", "derivative", "mixed", "full"):
    folder = ROOT / "experiments" / mode
    record = read_json(folder / "run.json")
    record["blueprint"] = blueprint(ROOT, mode)
    record["rules_snapshot"] = rules(ROOT)
    record["structure"] = structure_check(record["blueprint"], record["questions"])
    record["verifications"] = [verify(q) for q in record["questions"]]
    require(all(v["passed"] for v in record["verifications"]), "重解失败，停止导出")
    for event in record["events"]:
        if event["passed"]:
            event["verification"] = next(
                v
                for q, v in zip(record["questions"], record["verifications"])
                if q["id"] == event["question_id"]
            )
    record["files"] = export_run(record, folder)
    record["export_revision"] = "v2-explicit-subscript-and-answer-labels"
    atomic_json(folder / "run.json", record)
    atomic_json(folder / "attempts.json", record["events"])
    print(mode, "re-solved and exported")
