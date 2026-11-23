"""Record the actual draft screening and the evidence for each revised item."""
import argparse
from pathlib import Path
import sys

SOURCE = Path(__file__).resolve().parent
sys.path.insert(0,str(SOURCE.parents[2] / "scripts"))
from core.quality_audit import RULES, VERSION
from gaokao import digest, read_json
from analysis_db import fingerprint
from storage import atomic_json


def packet(subject, directory, candidate, draft):
    notes = read_json(SOURCE / f"{subject}-editorial.json")
    edits = read_json(SOURCE / "draft-edits.json")[subject]
    blind = read_json(directory / "blind-packet.json")
    reference = read_json(directory / "verification.json")["quality_benchmarks"]
    rows = []
    for n, (q, author, note) in enumerate(
        zip(blind["paper"]["questions"],candidate["questions"],notes,strict=True),1
    ):
        rejected = edits.get(str(n),{}).get("reasons",{}) if draft else {}
        starter = edits.get(str(n),{}) if draft else {}
        correct = author["proposed_answer"] if q["options"] else None
        errors = note.get("errors",{})
        paths = {}
        for option in set(q["options"]) - set(correct or ()):
            if rejected:
                paths[option] = {
                    "plausible": "distractors" not in rejected,
                    "misconception": "初稿试选路径",
                    "mechanism": rejected.get("distractors", "比较前后状态或错取图上的参照量。"),
                }
            else:
                misconception, mechanism = errors[option]
                paths[option] = {"plausible":True,"misconception":misconception,"mechanism":mechanism}
        applicability = {"distractors":bool(q["options"]), "figure":bool(q["figure"]),
                         "depth":True,"language":True}
        details = {
            "distractors":"；".join(f"{k}：{r['mechanism']}" for k,r in sorted(paths.items())) or "分步作答题。",
            "depth":" → ".join(note["steps"]),
            "figure":note.get("figure","本题为文字条件。"),
            "language":note["language"],
        }
        findings = {}
        for rule in RULES:
            findings[rule] = {
                "verdict":"return" if rule in rejected else "pass" if applicability[rule] else "not_applicable",
                "evidence":rejected.get(rule,details[rule]),
            }
        comparisons = {}
        for year, sample in reference["slots"][str(n)].items():
            comparisons[year] = {
                "version_sha256":sample["version_sha256"],
                "comparison":rejected["depth"] + " 参照：" + note["refs"][int(year)-2025]
                if "depth" in rejected else note["refs"][int(year)-2025],
            }
        rows.append({
            "number":n,"answer_key":correct,"benchmarks":comparisons,"findings":findings,
            "depth":{"reasoning_steps":[rejected["depth"]] if "depth" in rejected else note["steps"],
                     "linked_concepts":note["concepts"][:1] if "depth" in rejected else note["concepts"]},
            "required_figure_information":rejected.get("figure",note.get("figure")) if q["figure"] else None,
            "distractors":dict(sorted(paths.items())),
        })
        if "figure" in starter and not q["figure"]:
            raise ValueError(f"第{n}题漏掉初稿题图")
    return {
        "protocol":VERSION,"reviewer":"Work 宿主题位与命题质量审稿",
        "paper_version":blind["paper_version"],"paper_pdf_sha256":digest(directory/"paper.pdf"),
        "reference_sha256":fingerprint(reference),"items":rows,
        **({} if draft else {"revisions":{n:edit["changes"] for n,edit in edits.items()}}),
    }


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("subject",choices=("physics","chemistry"))
    parser.add_argument("directory",type=Path)
    parser.add_argument("candidate",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--draft",action="store_true")
    args=parser.parse_args()
    atomic_json(args.output,packet(args.subject,args.directory,read_json(args.candidate),args.draft))
