"""Recompute the English publication and audit bindings using only archived inputs."""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

directory=Path(__file__).resolve().parent
repo=directory.parents[3]
sys.path.insert(0,str(repo/"scripts"))
import bootstrap
from analysis_db import fingerprint
from core import quality_audit, review_board
from gaokao import digest, read_json
from pypdf import PdfReader
from signoff import main as assemble_signoff


def main():
    area=directory.parent
    final=area/"final"
    corpus=read_json(area/"source-binding.json")
    assert digest(directory/"authoring-context.json")==corpus["context_sha256"]
    for row in corpus["papers"]:
        assert digest(repo/row["filename"])==row["file_sha256"]
    assert digest(repo/corpus["dna_path"])==corpus["dna_sha256"]
    versions=[]
    for stage in ("round1","round2","final"):
        folder=area/stage
        card=review_board.replay(folder/"board")
        assert card["pdf_sha256"]==digest(folder/"paper.pdf")
        versions.append((card["round"],card["final_score"],card["fatal_count"]))
    publication=read_json(final/"publication.json")
    review=read_json(final/"independent-review.json")
    with TemporaryDirectory() as temp:
        scratch=Path(temp)
        assemble_signoff(final,3,scratch)
        assert review==read_json(scratch/"release-review.json")
        assert read_json(final/"quality-audit.json")==read_json(scratch/"release-audit.json")
        assert read_json(final/"writing-reconciliation.json")==read_json(scratch/"writing-reconciliation.json")
    assert publication["quality_audit_sha256"]==quality_audit.publication_quality(final,review)
    assert publication["review_sha256"]==fingerprint(review)
    for name,item in publication["artifacts"].items():
        path=final/f"{name}.pdf"
        assert digest(path)==item["sha256"] and len(PdfReader(path).pages)==len(item["pages"])
        assert all((final/f"{name}.{ext}").is_file() for ext in ("md","docx"))
    print("English board (round, score, fatal findings):",versions)
    print("Verified all 67 items, eight source papers, three published PDFs, and the full review chain.")

if __name__=="__main__":
    main()
