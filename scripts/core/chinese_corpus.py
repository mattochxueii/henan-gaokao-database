
"""Byte-bound offline sources for Chinese recitation and classical passages."""
from pathlib import Path
import re

from gaokao import digest, read_json

LOCATION=Path("data/corpus/chinese")
FILES=("required-memorization.json","classical-unfamiliar-pool.json")
AUTHOR_ALIASES={"陶潜":"陶渊明","陶淵明":"陶渊明","曹孟德":"曹操","苏子瞻":"苏轼"}
CHARACTERS=re.compile(r"[^\u3400-\u9fff\U00020000-\U0002ebef]")


def plain(text):
    return CHARACTERS.sub("",re.sub(r"<[^>]+>","",text))


def catalog(root, filename):
    pathname=root/LOCATION/filename
    return read_json(pathname)["entries"] if pathname.is_file() else []


def manifest(root):
    return {name:{"path":(LOCATION/name).as_posix(),"entries":len(catalog(root,name)),
                  "sha256":digest(root/LOCATION/name)}
            for name in FILES if (root/LOCATION/name).is_file()}


def recitation_findings(root, source_rows, answers):
    entries=catalog(root,FILES[0])
    if len(source_rows)!=3 or not isinstance(answers,list) or len(answers)!=6:
        yield "第17题须登记3组原篇与6个逐空答案"
        return
    seen_authors=set()
    seen_titles=set()
    for offset,source in enumerate(source_rows):
        raw_author=source.get("author","")
        author=AUTHOR_ALIASES.get(raw_author,raw_author)
        title=plain(source.get("title",""))
        if not author or not title or author in seen_authors or title in seen_titles:
            yield f"第17题第{offset+1}组作者或篇目重复、缺失"
            continue
        seen_authors.add(author)
        seen_titles.add(title)
        matches=[item for item in entries if plain(item["title"])==title and
                 AUTHOR_ALIASES.get(item["author"],item["author"])==author]
        if len(matches)!=1:
            yield f"第17题第{offset+1}组缺已登记的版本，须审核并补入校订底本"
            continue
        a,b=(plain(answer) for answer in answers[2*offset:2*offset+2])
        match=matches[0]
        original=plain(match["text"])
        variants={tuple(plain(word) for word in x) for x in match["variants"]}
        if not a or not b or (a+b not in original and (a,b) not in variants):
            yield f"第17题第{offset+1}组两个相邻空未通过底本逐字核验"
