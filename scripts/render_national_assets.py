"""Render PDF page context for TikZ references without executing untrusted TeX."""

import bootstrap  # noqa: F401
import subprocess, json
from gaokao import ROOT, read_lines, digest
from storage import atomic_json


def main():
    folder = ROOT / ".private/national-reference"
    rows = list(read_lines(folder / "occurrences.jsonl"))
    q = {x["id"]: x for x in read_lines(folder / "questions.jsonl")}
    previews = {}
    for row in rows:
        for asset in q[row["question_id"]]["asset_refs"]:
            if not asset["path"].endswith(".tex"):
                continue
            source = folder / row["source_locator"]["pdf"]["path"]
            page = row["source_locator"]["pdf"]["page"]
            target = folder / "derived" / (row["paper_id"] + f"-p{page}.png")
            target.parent.mkdir(exist_ok=True)
            if not target.exists():
                subprocess.run(
                    [
                        "pdftoppm",
                        "-f",
                        str(page),
                        "-l",
                        str(page),
                        "-r",
                        "125",
                        "-png",
                        "-singlefile",
                        str(source),
                        str(target.with_suffix("")),
                    ],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
            previews[asset["path"]] = {
                "path": target.relative_to(folder).as_posix(),
                "sha256": digest(target),
                "kind": "pdf_page_context",
                "pdf_source_sha256": digest(source),
                "pdf_page": page,
                "note": "完整源PDF页，可看题图；不是执行或逐像素验证重绘TeX",
            }
    atomic_json(folder / "figure-previews.json", previews)
    print(json.dumps({"tikz_previews": len(previews)}))


if __name__ == "__main__":
    main()
