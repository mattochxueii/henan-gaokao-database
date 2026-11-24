"""Scan publication inputs and reachable Git blobs; never emit credential values."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import os
import re
import subprocess


PATTERNS = {
    "private_key_header": rb"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----",
    "github_token": rb"(?<![\w-])(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{70,})(?![\w-])",
    "openai_key": rb"(?<![\w-])sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}(?![\w-])",
    "aws_key_id": rb"(?:AKIA|ASIA)[A-Z0-9]{16}",
    "slack_token": rb"xox[baprs]-[0-9]{9,}-[A-Za-z0-9-]{15,}",
    "credential_in_url": rb"https?://[^/@\s:'\"<>]{1,40}:[^/@\s'\"<>]{8,}@",
    "assigned_secret": rb"""(?im)^\s*(?:api_key|access_token|refresh_token|client_secret|recovery_key|gh_token|github_token)\s*[:=]\s*["']?([A-Za-z0-9+/_=.-]{24,})""",
}
CHECKS = {name:re.compile(pattern) for name,pattern in PATTERNS.items()}


def private_name(name):
    return name.lower().endswith(".key") or name.lower() == ".env" or bool(
        re.fullmatch(r"\.env\.(?:local|production|prod|development|dev|test|staging)(?:\.local)?",name,re.I))


def git(root,*args):
    return subprocess.check_output(["git","-c","core.quotepath=false",*args],cwd=root)


def scan(root):
    findings=[]
    ignored=[]
    paths=git(root,"ls-files","--cached","--others","--exclude-standard","-z").decode().split("\0")
    paths={p for p in paths if p}
    def inspect(data,where):
        for key,pat in CHECKS.items():
            if pat.search(data):
                findings.append({"location":where,"kind":key})
    for path in sorted(paths):
        file=root/path
        if private_name(file.name):
            findings.append({"location":path,"kind":"private_filename"})
        elif file.is_file() and not file.is_symlink():
            inspect(file.read_bytes(),path)
    for directory,subs,files in os.walk(root):
        subs[:] = [d for d in subs if d != ".git"]
        for name in files:
            if private_name(name):
                path=(Path(directory)/name).relative_to(root).as_posix()
                if path not in paths:
                    ignored.append(path)
    objects=git(root,"rev-list","--objects","--all").decode().splitlines()
    hashes=[]
    for line in objects:
        oid,_,path=line.partition(" ")
        hashes.append(oid)
        if path and private_name(Path(path).name):
            findings.append({"location":f"history:{oid[:12]}","kind":"private_filename"})
    blobs=0
    with subprocess.Popen(["git","cat-file","--batch"],cwd=root,stdin=subprocess.PIPE,stdout=subprocess.PIPE) as proc:
        for oid in hashes:
            proc.stdin.write(oid.encode()+b"\n")
            proc.stdin.flush()
            _,kind,size=proc.stdout.readline().split()
            data=proc.stdout.read(int(size))
            proc.stdout.read(1)
            if kind==b"blob":
                blobs+=1
                inspect(data,"history:"+oid[:12])
        proc.stdin.close()
    return {"checked_at_utc":datetime.now(timezone.utc).isoformat(),"head":git(root,"rev-parse","HEAD").decode().strip(),
            "worktree_files":len(paths),"reachable_blobs":blobs,"checks":list(CHECKS),
            "findings":findings,"ignored_private_filename_count":len(ignored),
            "ignored_private_filename_types":dict(Counter(Path(p).suffix for p in ignored)),
            "scope":"工作树及本地所有可达 Git 对象，忽略目录仅查敏感文件名；不读取或输出私人恢复密钥。",
            "pass":not findings}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    result=scan(args.root)
    encoded=json.dumps(result,ensure_ascii=False,indent=2)+"\n"
    if args.output:args.output.write_text(encoded,encoding="utf-8")
    print(encoded)
    raise SystemExit(0 if result["pass"] else 1)
