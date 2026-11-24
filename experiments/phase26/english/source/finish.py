"""Assemble the final visual record from three already-completed, file-bound readings."""
import argparse
from pathlib import Path
import shutil

from author import OUT, digest, read_json, save


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("solutions_reading",type=Path)
    parser.add_argument("listening_reading",type=Path)
    parser.add_argument("--folder",type=Path,default=OUT/"final")
    args=parser.parse_args()
    folder=args.folder
    archive=folder/"print-evidence"
    archive.mkdir(exist_ok=True)
    card=read_json(folder/"board/decision.json")
    assert card["state"]=="eligible" and not card["fatal_count"]
    record=read_json(folder/"board"/f"round{card['round']}.json")
    visual=next(r for r in record["reports"] if r["role"]=="visual")
    assert visual["pdf_sha256"]==digest(folder/"paper.pdf")
    artifacts={"paper":{"reviewer":visual["identity"],"sha256":visual["pdf_sha256"],
                        "pages":[p["note"] for p in visual["pages"]]}}
    for name,path in (("solutions",args.solutions_reading),("listening-script",args.listening_reading)):
        item=read_json(path)
        assert item["sha256"]==digest(folder/f"{name}.pdf") and item["reviewer"]
        assert all(isinstance(x,str) and x.strip() for x in item["pages"])
        retained=archive/f"{name}.json"
        if retained.resolve()!=path.resolve():
            if retained.exists():
                assert retained.read_bytes()==path.read_bytes()
            else:
                shutil.copyfile(path,retained)
        artifacts[name]=item
    identities=list(dict.fromkeys(x["reviewer"] for x in artifacts.values()))
    output={"reviewer":" / ".join(identities),"paper_version":read_json(folder/"blind-packet.json")["paper_version"],
            "artifacts":artifacts}
    save(folder/"visual-check.json",output)

if __name__=="__main__":
    main()
