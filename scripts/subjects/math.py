"""Stable adapter for the original mathematics Skill and archive."""

from gaokao import require
from national_db import query
import math_skill


def research(root, **filters):
    return query(root, subject="math", **filters)


def run(root, args):
    require(args and args[0] != "--root", "通过多学科入口设置仓库目录")
    return math_skill.main(["--root", str(root), *args])
