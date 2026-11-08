"""Content-aware credential checks; findings contain paths and codes, never secret values."""

import re
from pathlib import PurePosixPath


def scan_blob(path, data, forbidden_tokens=()):
    issues = []
    parts = PurePosixPath(path.replace("\\", "/")).parts
    if any(p in (".private", ".deps", ".git") for p in parts) or path.endswith(
        (".key", ".env")
    ):
        issues.append("private_path")
    for token in forbidden_tokens:
        if token and token in data:
            issues.append("credential_content")
            break
    if re.search(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", data):
        issues.append("private_key_content")
    if re.search(rb"(?<![A-Za-z0-9_-])sk-(?:proj-)?[A-Za-z0-9_-]{32,}", data):
        issues.append("api_key_shape")
    return {"path": path, "passed": not issues, "codes": issues}
