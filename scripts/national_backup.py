"""Reuse authenticated, chunked backup mechanics; never store recovery keys in the repository."""

import bootstrap  # noqa: F401
import argparse, re
from pathlib import Path
from gaokao import ROOT, read_json, require
from storage import backup, restore, split_backup, resolve_archive, atomic_json
from national_db import private_folder, validate


def create_national(root, key_file, version="national-v1"):
    require(
        not key_file.resolve().is_relative_to(root.resolve()),
        "恢复密钥必须保存在仓库外",
    )
    require(
        re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", version) is not None,
        "备份版本名称无效",
    )
    validate(root)
    archive = root / ".private" / (version + ".enc")
    metadata = backup(private_folder(root), archive, key_file)
    parts = root / "private-data" / version / "backup-parts.json"
    chunks = split_backup(archive, parts, chunk_bytes=512000)
    config = {
        "encrypted_backup": archive.relative_to(root).as_posix(),
        "backup_parts_manifest": parts.relative_to(root).as_posix(),
        "cipher_sha256": metadata["cipher_sha256"],
        "files": metadata["files"],
        "encryption": metadata["encryption"],
        "dataset": "national-reference",
        "key_in_repository": False,
        "version": version,
    }
    atomic_json(root / "national/backup.json", config)
    return {
        "files": len(metadata["files"]),
        "parts": len(chunks["parts"]),
        "key_separate": True,
        "version": version,
    }


def restore_national(root, key_file, destination=None):
    cfg = read_json(root / "national/backup.json")
    archive = resolve_archive(root, cfg, cfg["cipher_sha256"])
    destination = destination or private_folder(root)
    return restore(archive, key_file, destination, cfg["files"])


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--key", type=Path, required=True)
    p.add_argument("--version", default="national-v1")
    a = p.parse_args()
    print(
        __import__("json").dumps(
            create_national(ROOT, a.key, a.version), ensure_ascii=False
        )
    )
