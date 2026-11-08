"""Render every delivered PDF and collect page-level QA metrics."""

import bootstrap
from pathlib import Path
import shutil
import subprocess
from PIL import Image, ImageOps, ImageDraw
from pypdf import PdfReader
from gaokao import ROOT, require, digest
from storage import atomic_json


def render_all(output):
    require(shutil.which("pdftoppm"), "需要Poppler渲染PDF")
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for mode in ("sequence", "derivative", "mixed", "full"):
        for name in ("paper", "solutions"):
            source = ROOT / "experiments" / mode / (name + ".pdf")
            folder = output / (mode + "-" + name + "-" + digest(source)[:10])
            folder.mkdir(exist_ok=True)
            subprocess.run(
                ["pdftoppm", "-r", "110", "-png", str(source), str(folder / "page")],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            pages = list(
                sorted(
                    folder.glob("page-*.png"), key=lambda p: int(p.stem.split("-")[-1])
                )
            )
            reader = PdfReader(source)
            require(len(pages) == len(reader.pages), "PDF页数和渲染页数不符")
            results.append(
                {
                    "file": source.relative_to(ROOT).as_posix(),
                    "sha256": digest(source),
                    "pages": len(pages),
                    "rendered_all_pages": True,
                    "text_nonempty": all(
                        bool(p.extract_text().strip()) for p in reader.pages
                    ),
                    "visual_review": "awaiting_AI_visual_review",
                }
            )
            for start in range(0, len(pages), 4):
                sheet = Image.new("RGB", (1000, 1460), "#dce2e5")
                draw = ImageDraw.Draw(sheet)
                for index, path in enumerate(pages[start : start + 4]):
                    with Image.open(path) as page:
                        page.thumbnail((490, 700))
                        col, row = index % 2, index // 2
                        sheet.paste(page, (5 + 500 * col, 25 + 730 * row))
                        draw.text(
                            (10 + 500 * col, 5 + 730 * row),
                            f"{mode}-{name} page {start + index + 1}",
                            fill="black",
                        )
                sheet.save(output / f"{mode}-{name}-sheet-{start // 4 + 1}.png")
    atomic_json(
        ROOT / "reports/pdf-qa.json",
        {
            "files": results,
            "total_pages": sum(r["pages"] for r in results),
            "docx": "未找到LibreOffice，未生成未核验DOCX",
        },
    )
    print(sum(r["pages"] for r in results), "pages rendered")


if __name__ == "__main__":
    render_all(ROOT.parents[1] / "work/pdf-qa")
