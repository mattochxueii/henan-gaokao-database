"""Download pinned, publicly accessible references without overwriting or bypassing access controls."""

import bootstrap  # noqa: F401
import concurrent.futures, hashlib, json, re, urllib.request, urllib.parse
from pathlib import Path
from gaokao import ROOT, read_json, require, digest
from storage import atomic_json


def fetch(repo, commit, item, destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    url = (
        "https://raw.githubusercontent.com/"
        + repo
        + "/"
        + commit
        + "/"
        + urllib.parse.quote(item["path"])
    )
    if destination.is_file():
        data = destination.read_bytes()
    else:
        with urllib.request.urlopen(
            urllib.request.Request(
                url, headers={"User-Agent": "GaokaoArchiveResearch/1.0"}
            ),
            timeout=45,
        ) as response:
            require(response.status == 200, "HTTP failure")
            data = response.read(15_000_001)
        require(len(data) <= 15_000_000, "reference too large")
        require(
            hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
            == item["sha"],
            "Git blob checksum mismatch",
        )
        destination.write_bytes(data)
    require(
        hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        == item["sha"],
        "cached file differs",
    )
    return {
        "url": url,
        "path": destination.relative_to(ROOT).as_posix(),
        "sha256": digest(destination),
        "bytes": len(data),
        "git_blob": item["sha"],
    }


def collect():
    config = read_json(ROOT / "data/national/acquisition.json")
    directory = ROOT / ".private/national-reference"
    directory.mkdir(parents=True, exist_ok=True)
    results = []
    failures = []

    def one(row):
        items = {}
        for kind in ("tex", "pdf"):
            item = row.get(kind)
            if not item:
                continue
            dest = (
                directory
                / "upstream"
                / kind
                / (item["path"] if kind == "tex" else row["id"] + ".pdf")
            )
            items[kind] = fetch(
                config[kind + "_repo"], config[kind + "_commit"], item, dest
            )
        text = (ROOT / items["tex"]["path"]).read_text(encoding="utf-8-sig")
        # Collect actual image dependencies and linked redraw sources; never invent a path.
        refs = set(
            re.findall(
                r"\\(?:bitmapfigure|texfigure|solutionfigure|includegraphics)(?:\[[^\]]*\])?\{([^{}]+)\}",
                text,
            )
        )
        refs.update(re.findall(r"\\input\{([^{}]+)\}", text))
        items["asset_refs"] = sorted(refs)
        return {**row, "files": items}

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        jobs = {pool.submit(one, row): row for row in config["records"]}
        for future, row in jobs.items():
            try:
                results.append(future.result())
            except Exception as e:
                failures.append({"id": row["id"], "reason": str(e)})
    asset_index = {
        r["path"]: r for r in read_json(ROOT / "data/national/asset-manifest.json")
    }
    needed = sorted({name for row in results for name in row["files"]["asset_refs"]})
    assets = []
    for name in needed:
        try:
            require(
                name in asset_index, "依赖图未登记固定blob；须先核查上游路径：" + name
            )
            destination = (directory / "upstream/tex" / name).resolve()
            require(
                destination.is_relative_to((directory / "upstream/tex").resolve()),
                "依赖路径越界",
            )
            assets.append(
                fetch(
                    config["tex_repo"],
                    config["tex_commit"],
                    asset_index[name],
                    destination,
                )
            )
        except Exception as e:
            failures.append({"asset": name, "reason": str(e)})
    atomic_json(directory / "assets.json", assets)
    atomic_json(
        directory / "acquisition-results.json",
        {"papers": results, "failures": failures},
    )
    print(
        json.dumps(
            {
                "acquired": len(results),
                "failures": failures,
                "downloaded_assets": len(assets),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    collect()
