"""Portable configuration and authenticated private-data backups."""

import io
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import zipfile

from gaokao import atomic_write, digest, dumps, read_json, relative_path, require

MAX_SIZE = 64 * 1024 * 1024


def reference_directory(root, override=None):
    if override is not None:
        return override.resolve()
    config_path = root / "data/database.json"
    if not config_path.exists():
        return None
    config = read_json(config_path)
    target = relative_path(root, config["reference_dir"])
    if not (target / "manifest.json").is_file():
        return None
    index = relative_path(
        root, config.get("backup_inventory", ".private/backup/inventory.json")
    )
    if index.exists():
        for record in read_json(index)["files"]:
            path = relative_path(target, record["path"])
            require(
                path.is_file()
                and path.stat().st_size == record["bytes"]
                and digest(path) == record["sha256"],
                "私有题面或页图发生变化，请重新登记、复核和备份 " + record["path"],
            )
    return target


def inventory(directory):
    return [
        {
            "path": path.relative_to(directory).as_posix(),
            "sha256": digest(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    ]


def backup(directory, target, key_file):
    from cryptography.fernet import Fernet

    require(
        directory.is_dir() and (directory / "manifest.json").is_file(),
        "私有数据目录缺失",
    )
    require(
        not key_file.exists() and not target.exists(), "备份或密钥已存在，请选择新路径"
    )
    records = inventory(directory)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for row in records:
            path = directory / row["path"]
            require(
                not path.is_symlink()
                and path.resolve().is_relative_to(directory.resolve()),
                "不接受目录外链接",
            )
            archive.write(path, row["path"])
    require(len(buffer.getvalue()) <= MAX_SIZE, "私有数据超出备份大小限制")
    key = Fernet.generate_key()
    key_file.parent.mkdir(parents=True, exist_ok=True)
    with key_file.open("xb") as stream:
        stream.write(key)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        guard = target.parent / (target.name + ".lock")
        guard.mkdir()
        temporary = None
        try:
            require(not target.exists(), "备份目标已存在")
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(Fernet(key).encrypt(buffer.getvalue()))
            os.rename(temporary, target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            guard.rmdir()
    except Exception:
        key_file.unlink(missing_ok=True)
        raise
    return {
        "files": records,
        "cipher_sha256": digest(target),
        "encryption": "Fernet authenticated encryption",
    }


def restore(archive_path, key_file, destination, expected_inventory=None):
    from cryptography.fernet import Fernet

    require(
        not destination.exists(), "恢复目标已存在，请先检查现有数据或使用新的空目录"
    )
    data = Fernet(key_file.read_bytes()).decrypt(archive_path.read_bytes())
    require(len(data) <= MAX_SIZE, "恢复数据超过限制")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="restore-", dir=destination.parent))
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            require(
                sum(row.file_size for row in archive.infolist()) <= MAX_SIZE,
                "解压后数据超过限制",
            )
            names = set()
            for member in archive.infolist():
                require(member.filename not in names, "备份包含重复路径")
                names.add(member.filename)
                require(
                    (member.external_attr >> 16) & 0o170000 != 0o120000,
                    "备份包含符号链接",
                )
                path = relative_path(staging, member.filename)
                if member.is_dir():
                    path.mkdir(parents=True, exist_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(archive.read(member))
        require((staging / "manifest.json").is_file(), "备份缺少原始资料清单")
        records = inventory(staging)
        if expected_inventory is not None:
            require(
                records == expected_inventory,
                "恢复后的文件清单或 SHA-256 与版本记录不符",
            )
        os.replace(staging, destination)
        return {"files": len(records), "destination": str(destination)}
    finally:
        if staging.exists():
            require(
                staging.resolve().is_relative_to(destination.parent.resolve()),
                "暂存目录超出恢复目标父目录",
            )
            shutil.rmtree(staging)


def atomic_json(path, value):
    atomic_write(path, dumps(value) + "\n")


def split_backup(archive, manifest_path, chunk_bytes=64000):
    require(not manifest_path.exists(), "分片清单已存在，请选择新的备份目录")
    data = archive.read_bytes()
    require(len(data) <= MAX_SIZE, "备份超出大小限制")
    folder = manifest_path.parent / "parts"
    require(not folder.exists(), "分片目录已存在，拒绝覆盖旧备份")
    folder.mkdir(parents=True)
    parts = []
    for number, start in enumerate(range(0, len(data), chunk_bytes)):
        chunk = data[start : start + chunk_bytes]
        path = folder / f"{number:04d}.part"
        path.write_bytes(chunk)
        parts.append(
            {
                "path": path.relative_to(manifest_path.parent).as_posix(),
                "bytes": len(chunk),
                "sha256": digest(path),
            }
        )
    result = {
        "format": "ordered-encrypted-parts-v1",
        "bytes": len(data),
        "cipher_sha256": digest(archive),
        "parts": parts,
    }
    atomic_json(manifest_path, result)
    return result


def resolve_archive(root, config, expected_sha256):
    archive = relative_path(root, config["encrypted_backup"])
    if archive.exists():
        require(digest(archive) == expected_sha256, "密文校验值不符")
        return archive
    manifest_path = relative_path(root, config["backup_parts_manifest"])
    manifest = read_json(manifest_path)
    require(manifest["format"] == "ordered-encrypted-parts-v1", "未知分片格式")
    require(manifest["cipher_sha256"] == expected_sha256, "分片清单与文件库存不符")
    require(0 < manifest["bytes"] <= MAX_SIZE, "分片数据大小无效")
    pieces = []
    seen = set()
    for part in manifest["parts"]:
        require(part["path"] not in seen, "分片路径重复")
        seen.add(part["path"])
        path = relative_path(manifest_path.parent, part["path"])
        require(
            path.stat().st_size == part["bytes"] and digest(path) == part["sha256"],
            "备份分片缺失或损坏",
        )
        pieces.append(path.read_bytes())
    data = b"".join(pieces)
    require(
        len(data) == manifest["bytes"]
        and hashlib.sha256(data).hexdigest() == expected_sha256,
        "合并密文校验失败",
    )
    cache = root / ".private" / "cipher-cache"
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / (expected_sha256 + ".enc")
    with tempfile.NamedTemporaryFile(dir=cache, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(data)
    try:
        os.replace(temporary, archive)
    finally:
        temporary.unlink(missing_ok=True)
    return archive
