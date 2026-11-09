"""Conservative, balanced-brace importer for pinned LaTeX compilations; no TeX execution."""

import re, unicodedata
from analysis_db import fingerprint
from gaokao import require

KINDS = {
    "单选题": "single_choice",
    "多选题": "multiple_choice",
    "填空题": "fill_in",
    "解答题": "constructed_response",
    "选考题：解答题": "optional_response",
}
MACROS = {
    r"\R": r"\mathbb{R}",
    r"\N": r"\mathbb{N}",
    r"\C": r"\mathbb{C}",
    r"\Z": r"\mathbb{Z}",
    r"\i": "i",
    r"\e": "e",
    r"\bs": r"\boldsymbol",
}
ASSET = re.compile(
    r"\\(?:bitmapfigure|texfigure|solutionfigure|includegraphics)(?:\[[^\]]*\])?\{([^{}]+)\}"
)


def braces(text, at):
    while at < len(text) and text[at].isspace():
        at += 1
    require(at < len(text) and text[at] == "{", "选项参数缺失")
    depth = 1
    start = at + 1
    at += 1
    while at < len(text) and depth:
        if text[at] == "\\":
            # Escaped braces are literal; other commands leave their argument braces active.
            if at + 1 < len(text) and text[at + 1] in "{}%":
                at += 2
                continue
        if text[at] == "{":
            depth += 1
        elif text[at] == "}":
            depth -= 1
        at += 1
    require(depth == 0, "选项括号未闭合")
    return text[start : at - 1], at


def readable(text):
    text = re.sub(r"(?m)(?<!\\)%[^\n]*", "", text)
    text = re.sub(r"\\FigureLayoutDeclare\{[^{}]*\}\{[^{}]*\}\{[^{}]*\}", "", text)
    text = ASSET.sub(lambda m: "[图：" + m[1] + "]", text)
    text = re.sub(r"\\fillinblank\{[^{}]*\}", "________", text)
    text = re.sub(
        r"\\(?:begin|end)\{(?:center|enumerate|circlelist|itemize)\}(?:\[[^\]]*\])?",
        "",
        text,
    )
    text = re.sub(r"\\item(?:\[[^\]]*\])?", lambda m: "\n（子项）", text)
    for source, target in MACROS.items():
        text = re.sub(re.escape(source) + r"(?![A-Za-z])", lambda m: target, text)
    return re.sub(r"[ \t]+", " ", text).strip()


def answer_blocks(text):
    blocks = []
    at = 0
    pattern = re.compile(
        r"\\begin\{(answer|solution)\}|\\(answer|solution)(?![A-Za-z])(?=\s*\{)"
    )
    while (m := pattern.search(text, at)) is not None:
        kind = m[1] or m[2]
        if m[1]:
            closing = r"\end{" + kind + "}"
            end = text.find(closing, m.end())
            require(end >= 0, "答案环境未闭合")
            value = text[m.end() : end]
            stop = end + len(closing)
        else:
            value, stop = braces(text, m.end())
        blocks.append((kind, value, m.start(), stop))
        at = stop
    return blocks


def subquestion_tree(text):
    roots = []
    stack = []
    pattern = re.compile(
        r"\\begin\{enumerate\}|\\end\{enumerate\}|\\item(?![A-Za-z])(?:\[[^\]]*\])?"
    )
    for m in pattern.finditer(text):
        token = m[0]
        if token.startswith(r"\begin"):
            children = []
            if stack and stack[-1].get("current"):
                stack[-1]["current"]["children"] = children
            else:
                children = roots
            stack.append({"items": children, "current": None})
        elif token.startswith(r"\item") and stack:
            frame = stack[-1]
            if frame["current"] is not None:
                frame["current"]["text"] = readable(
                    text[frame["current"].pop("start") : m.start()]
                )
            item = {"number": len(frame["items"]) + 1, "start": m.end(), "children": []}
            frame["items"].append(item)
            frame["current"] = item
        elif token.startswith(r"\end"):
            require(stack, "子问结束无开始")
            frame = stack.pop()
            if frame["current"] is not None:
                frame["current"]["text"] = readable(
                    text[frame["current"].pop("start") : m.start()]
                )
    require(not stack, "子问列表未闭合")
    return roots


def parse(text):
    starts = list(re.finditer(r"\\begin\{problem\}", text))
    rows = []
    for i, start in enumerate(starts):
        end = text.find(r"\end{problem}", start.end())
        require(end >= 0, "题目环境未闭合")
        next_start = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        require(end < next_start, "嵌套或缺失problem结束")
        raw = text[start.end() : end].strip()
        embedded_blocks = answer_blocks(raw)
        embedded_answers = [(kind, value) for kind, value, a, b in embedded_blocks]
        for kind, value, a, b in reversed(embedded_blocks):
            raw = raw[:a] + raw[b:]
        raw = raw.strip()
        sections = re.findall(r"\\section\{([^}]+)\}", text[: start.start()])
        require(sections and sections[-1] in KINDS, "未知题型章节")
        kind = KINDS[sections[-1]]
        options = {}
        choice = re.search(r"\\choices(?![A-Za-z])", raw)
        if choice:
            at = choice.end()
            for letter in "ABCD":
                value, at = braces(raw, at)
                options[letter] = readable(value)
            stem = raw[: choice.start()] + raw[at:]
        else:
            stem = raw
        require(
            bool(options) == (kind in ("single_choice", "multiple_choice")),
            "选项与题型不符",
        )
        after = text[end + len(r"\end{problem}") : next_start]
        answers = embedded_answers + [
            (kind, value) for kind, value, a, b in answer_blocks(after)
        ]
        answer_lines = [
            {
                "kind": kind,
                "start": text[: start.end() + a].count("\n") + 1,
                "end": text[: start.end() + b].count("\n") + 1,
            }
            for kind, value, a, b in answer_blocks(text[start.end() : next_start])
        ]
        require(len(answers) <= 2, "重复答案环境")
        answer = "\n".join(v.strip() for k, v in answers if k == "answer")
        solution = "\n".join(v.strip() for k, v in answers if k == "solution")
        tree = subquestion_tree(stem)
        parts = [r["text"] for r in tree]
        formulas = re.findall(r"\\\((.*?)\\\)|\\\[(.*?)\\\]", raw, re.S)
        require(
            raw.count(r"\(") == raw.count(r"\)")
            and raw.count(r"\[") == raw.count(r"\]"),
            "公式定界符不匹配",
        )
        rows.append(
            {
                "number": i + 1,
                "kind": kind,
                "stem": readable(stem),
                "options": options,
                "parts": parts,
                "subquestion_tree": tree,
                "formulas": [readable(a or b) for a, b in formulas],
                "assets": ASSET.findall(raw),
                "answer_assets": ASSET.findall(answer + "\n" + solution),
                "tables_latex": re.findall(
                    r"\\begin\{tabular\}.*?\\end\{tabular\}", raw, re.S
                ),
                "raw_problem_latex": raw,
                "reference_answer": readable(answer) or None,
                "explanation": readable(solution) or None,
                "raw_answer_latex": answer,
                "raw_solution_latex": solution,
                "answer_lines": answer_lines,
                "source_lines": {
                    "start": text[: start.start()].count("\n") + 1,
                    "end": text[:end].count("\n") + 1,
                },
            }
        )
    require(rows, "无完整题面")
    return rows


def content_signature(row, asset_hashes):
    # Conservative identity: do not merge same-method or changed-condition problems.
    def normal(value):
        value = unicodedata.normalize("NFKC", value)
        value = re.sub(r"\\(?:left|right)(?![A-Za-z])", "", value)
        value = re.sub(r"\\(?:geqslant|ge|geq)(?![A-Za-z])", lambda m: r"\geq", value)
        value = re.sub(r"\\(?:leqslant|le|leq)(?![A-Za-z])", lambda m: r"\leq", value)
        return (
            re.sub(r"\s+", "", value)
            .replace(r"\dfrac", r"\frac")
            .replace("，", ",")
            .replace("。", ".")
        )

    return fingerprint(
        {
            "stem": normal(ASSET.sub("", row["raw_problem_latex"])),
            "images": [asset_hashes[x] for x in row["assets"]],
        }
    )
