"""Encrypted backup/restore commands. Key material stays outside version control."""

import bootstrap
import argparse
from pathlib import Path

from gaokao import ROOT, dumps, read_json, relative_path, require
from storage import atomic_json, backup, restore, split_backup, resolve_archive


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    actions = parser.add_subparsers(dest="action", required=True)
    for name in ("backup", "restore"):
        command = actions.add_parser(name)
        command.add_argument("--key", required=True, type=Path)
        if name == "backup":
            command.add_argument("--source", required=True, type=Path)
        else:
            command.add_argument("--destination", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    config = read_json(root / "data/database.json")
    archive = relative_path(root, config["encrypted_backup"])
    index = relative_path(
        root, config.get("backup_inventory", ".private/backup/inventory.json")
    )
    if args.action == "backup":
        parts_manifest = relative_path(root, config["backup_parts_manifest"])
        require(
            not index.exists()
            and not parts_manifest.exists()
            and not (parts_manifest.parent / "parts").exists(),
            "备份库存或分片已存在，请配置新的备份目录，保留旧版本",
        )
        result = backup(args.source.resolve(), archive, args.key.resolve())
        split_backup(archive, parts_manifest)
        atomic_json(index, result)
    else:
        archive = resolve_archive(root, config, read_json(index)["cipher_sha256"])
        destination = args.destination or relative_path(root, config["reference_dir"])
        result = restore(archive, args.key, destination, read_json(index)["files"])
    print(dumps(result))


if __name__ == "__main__":
    main()
