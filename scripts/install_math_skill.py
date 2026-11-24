"""Historical installer retained for existing math and chemistry workflows."""
import argparse
from pathlib import Path

from gaokao import ROOT, dumps
from install_skill import SKILLS, install as install_shared


def install(root, destination, skill_name="henan-math"):
    return install_shared(root, destination, skill_name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", choices=SKILLS, default="henan-math")
    parser.add_argument("--destination", type=Path)
    args = parser.parse_args()
    destination = args.destination or ROOT/".agents"/"skills"/args.skill
    print(dumps(install(ROOT,destination,args.skill)))
