"""Versioned holdout groups for reference-grounded generation."""

from collections import defaultdict

from analysis_db import fingerprint
from gaokao import require
from math_calibration import grade

VERSION = "paper-holdout-v1"


def build_split(rows, held_papers, adaptation_pairs=()):
    by_id = {r["occurrence_id"]: r for r in rows}
    parent = {r["paper_id"]: r["paper_id"] for r in rows}

    def group(paper):
        while parent[paper] != paper:
            paper = parent[paper]
        return paper

    def join(first, second):
        a, b = sorted((group(first), group(second)))
        parent[b] = a

    related = defaultdict(list)
    for row in rows:
        related["master", row["question_id"]].append(row["paper_id"])
        if alias := row.get("calibration", {}).get("equivalence_id"):
            related["equivalent", alias].append(row["paper_id"])
    for papers in related.values():
        for paper in papers[1:]:
            join(papers[0], paper)
    for first, second in adaptation_pairs:
        join(by_id[first]["paper_id"], by_id[second]["paper_id"])

    require(held_papers and set(held_papers) <= set(parent), "留出卷不存在")
    held_groups = {group(p) for p in held_papers}
    split = {
        "version": VERSION,
        "requested_holdout_papers": sorted(set(held_papers)),
        "held_groups": sorted(held_groups),
        "groups": {p: group(p) for p in sorted(parent)},
        "reference": {},
        "holdout": {},
        "scope": "按试卷、共享主记录、已知等价与指定改编关系分组。预训练接触无法确认。",
    }
    for oid, row in sorted(by_id.items()):
        if grade(row) != "source_and_solution_reviewed":
            continue
        partition = "holdout" if group(row["paper_id"]) in held_groups else "reference"
        split[partition][oid] = row["version_sha256"]
    require(split["reference"] and split["holdout"], "缺少已复核的训练或评测题")
    split["sha256"] = fingerprint(split)
    return split


def archive_split(root, held_papers):
    from national_db import rows
    from national_duplicates import compare

    archive = rows(root)
    # Treat candidate adaptations conservatively as a shared component.
    first_occurrence = {row["id"]: row["occurrence_id"] for row in archive}
    pairs = [
        (first_occurrence[r["left_id"]], first_occurrence[r["right_id"]])
        for r in compare(archive)["adaptation_suggestions"]
    ]
    return build_split(archive, held_papers, pairs)


def verify_split(root, split):
    fresh = archive_split(root, split["requested_holdout_papers"])
    require(fresh == split, "留出集内容、版本或分组已变化")
    return fresh


def verify_candidate_references(document, split):
    require(
        document.get("evaluation_split_sha256") == split["sha256"],
        "候选未绑定当前留出集",
    )
    for question in document["questions"]:
        for ref in question.get("research_design", {}).get("references", ()):
            require(
                split["reference"].get(ref["occurrence_id"]) == ref["version_sha256"],
                "命题候选引用了留出题或过期题面",
            )


def blind_pairs(split, student, archive, assignments):
    """Produce student prompts and a separate answer-free provenance key."""
    archive = {r["occurrence_id"]: r for r in archive}
    student = {q["order"]: q for q in student["questions"]}
    pairs, key = {}, {}
    for index, (number, oid) in enumerate(assignments, 1):
        old = archive[oid]
        new = student[number]
        require(
            split["holdout"].get(oid) == old["version_sha256"]
            and grade(old) == "source_and_solution_reviewed",
            "对照题须属于当前已复核留出集",
        )
        require(not old.get("asset_refs") and not new.get("figure"), "本评测包仅支持纯文字题")
        original = {k: old[k] for k in ("stem", "points", "kind", "options")}
        generated = {k: new[k] for k in ("stem", "points", "kind", "options", "parts")}
        pair_id = f"pair-{index}"
        swap = int(fingerprint([split["sha256"], oid, new["id"]])[-1], 16) % 2
        pairs[pair_id] = dict(zip(("left", "right"), (original, generated) if swap else (generated, original)))
        key[pair_id] = {
            "heldout_occurrence": oid, "heldout_version_sha256": old["version_sha256"],
            "generated_id": new["id"], "historical_side": "left" if swap else "right",
        }
    require(pairs, "对照包不得为空")
    return {"pairs": pairs}, key
