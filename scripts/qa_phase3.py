"""Render all final AI/template PDFs; visual review is a separate, explicit step."""

import bootstrap
from pathlib import Path
import subprocess
from PIL import Image, ImageDraw, ImageChops
from pypdf import PdfReader
from gaokao import ROOT, require, digest
from storage import atomic_json


def main():
    target = ROOT.parents[1] / "work/phase3/pdf-qa"
    target.mkdir(parents=True, exist_ok=True)
    sources = [
        ROOT / "experiments" / n for n in ("sequence", "derivative", "mixed", "full")
    ]
    sources += [
        ROOT / "experiments/phase3/deliveries" / n
        for n in (
            "sequence10",
            "derivative10",
            "mixed50",
            "fullA",
            "fullB",
            "acceptance5",
        )
    ]
    results = []
    for source in sources:
        for name in ("paper", "solutions"):
            pdf = source / (name + ".pdf")
            sha = digest(pdf)
            label = source.name + "-" + name
            folder = target / (label + "-" + sha[:10])
            folder.mkdir(exist_ok=True)
            subprocess.run(
                ["pdftoppm", "-r", "110", "-png", str(pdf), str(folder / "page")],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            pages = sorted(
                folder.glob("page-*.png"), key=lambda p: int(p.stem.split("-")[-1])
            )
            reader = PdfReader(pdf)
            require(len(reader.pages) == len(pages), "渲染缺页")
            page_metrics = []
            for i, path in enumerate(pages):
                with Image.open(path).convert("RGB") as im:
                    ink = (
                        ImageChops.difference(im, Image.new("RGB", im.size, "white"))
                        .convert("L")
                        .point(lambda p: 255 if p > 35 else 0)
                    )
                    box = ink.getbbox()
                    require(box is not None, "空白页")
                    page_metrics.append(
                        {
                            "page": i + 1,
                            "raster_size": list(im.size),
                            "ink_box": list(box),
                            "text_characters": len(reader.pages[i].extract_text()),
                        }
                    )
            sheets = []
            for start in range(0, len(pages), 2):
                sheet = Image.new("RGB", (1420, 1030), "#dce2e5")
                draw = ImageDraw.Draw(sheet)
                for j, path in enumerate(pages[start : start + 2]):
                    with Image.open(path) as im:
                        im.thumbnail((700, 990))
                        sheet.paste(im, (5 + 710 * j, 30))
                    draw.text(
                        (10 + 710 * j, 8),
                        label + " page " + str(start + j + 1),
                        fill="black",
                    )
                dest = target / (label + "-sheet-" + str(start // 2 + 1) + ".png")
                sheet.save(dest)
                sheets.append(dest.name)
            results.append(
                {
                    "file": pdf.relative_to(ROOT).as_posix(),
                    "sha256": sha,
                    "pages": len(pages),
                    "rendered_all_pages": True,
                    "page_metrics": page_metrics,
                    "contact_sheets": sheets,
                    "visual_review": "awaiting_AI_visual_review",
                    "human_review": False,
                }
            )
    atomic_json(
        ROOT / "reports/phase3-pdf-qa.json",
        {
            "files": results,
            "total_pages": sum(r["pages"] for r in results),
            "visual_review": "awaiting_AI_visual_review",
            "docx": "本轮未要求Word，未生成",
        },
    )
    print("PDF files:", len(results), "pages:", sum(r["pages"] for r in results))


if __name__ == "__main__":
    main()
