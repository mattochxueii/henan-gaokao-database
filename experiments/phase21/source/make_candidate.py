"""Build reproducible candidate inputs from the Phase 21 authoring files."""

import argparse
import hashlib
import json
from pathlib import Path
import re

SOURCE = Path(__file__).parent
SPECS = {
    "physics": {
        "title": "河南新高考物理模拟试卷",
        "single": 7,
        "scores": [4]*7 + [6]*3 + [6, 9, 10, 12, 17],
        "key": ["B", "D", "A", "C", "B", "D", "A", "ACD", "AD", "BC",
            ["1.50 m/s", "+0.81 m/s²；+1.08 m/s²", "B 端低；0.135 N/kg"],
            ["4.80 V；-24 Ω", "I+U/120；6.00 V；30.0 Ω", "均偏小"],
            ["400 K；1.50×10^5 Pa", "120 J；+600 J"],
            ["4.0 m/s；(√65-1)/8 m", "v₀>2√2 m/s；等号时恰到 O 静止"],
            ["0<s<1；v√(1-s²)，-vs", "0<s≤1/√2；2L/[v(√(1-s²)+√(1/2-s²))]", "0<s≤1/2"]],
    },
    "chemistry": {
        "title": "河南新高考化学模拟试卷",
        "single": 14,
        "scores": [3]*14 + [14, 14, 15, 15],
        "key": ["C", "B", "D", "A", "B", "B", "C", "D", "D", "C", "B", "A", "C", "B",
            ["ZnO+2H⁺→Zn²⁺+H₂O；SiO₂", "H₂O₂+2Fe²⁺+2H⁺→2Fe³⁺+2H₂O；pH 4.5",
             "Zn+Cu²⁺→Zn²⁺+Cu；0.788 F", "2H₂O→O₂+4H⁺+4e⁻；0.630 mol；回用净生成的酸"],
            ["Mg²⁺+2OH⁻→Mg(OH)₂；酒红至蓝", "钙 1.70×10^-3 mol/L；镁 1.00×10^-3 mol/L",
             "镁偏大", "处理前后分别等量加标；前加标回收量更低"],
            ["T₂>T₁；T₂ 选择性更高；增压使两反应逆向移动", "25.0 kPa；25.0 kPa；0.250；0.0625",
             "不变；K₁/K₂=(n乙醛/n乙烯)²", "131.25 kPa"],
            ["酚羟基和醛基；水；保护醛基", "C 对位 R-C₆H₄-OCH₂COOC₂H₅；D 对位 R-C₆H₄-OCH₂COONa；酯基",
             "10 种", "间位缩醛保护→酚盐取代→短时稀酸脱保护；跳过皂化"]],
    },
    "biology": {
        "title": "河南新高考生物学模拟试卷",
        "single": 16,
        "scores": [3]*16 + [10, 11, 10, 10, 11],
        "key": ["C", "D", "B", "A", "C", "A", "D", "B", "B", "D", "C", "A", "D", "B", "A", "C",
            ["甲 100；乙 50；净吸收为零", "甲 11；乙 7；μmol CO₂·m⁻²·s⁻¹",
             "同光强和同其他条件比较常规与高 CO₂；高 CO₂ 净吸收更快",
             "ATP 提供能量；NADPH 提供还原力"],
            ["神经调节；体液调节", "乙/甲抑制；丙/甲接近；丁/乙恢复并与丙接近",
             "声刺激×受体阻断四组；测 C 和 M；阻断削弱 M 响应而 C 仍升高"],
            ["6.4 株/m²；按面积加权", "记录物种；匹配季节、面积和调查强度",
             "距离分层后随机割草或不割；以独立地段为重复；比较密度变化"],
            ["AAbb、aaBB、AaBb", "aabb；白色潜在类少一份", "1/9", "aaBB 全紫；aaBb 紫:黄=1:1"],
            ["无酶空白凝胶；检验底物和载体背景", "小颗粒；传质距离较短",
             "同批大颗粒等量切小与假处理；切小组初速较高",
             "收集滤液后另加新乳糖；相对无酶对照有新增产物"]],
    },
}


def parse_markdown(source):
    blocks = re.split(r"(?m)^## (\d+) ([^\n]+)\n", source)[1:]
    for i in range(0, len(blocks), 3):
        number, topic, body = blocks[i:i+3]
        stem, options, parts = [], {}, []
        figure_path = None
        for line in body.splitlines():
            if match := re.fullmatch(r"([ABCD])\. (.+)", line):
                options[match[1]] = match[2]
            elif match := re.fullmatch(r"(（\d+）)(.+)", line):
                parts.append({"label": match[1], "text": match[2]})
            elif match := re.fullmatch(r"!\[[^]]+\]\(([^)]+)\)", line):
                figure_path = match[1]
            elif line.strip():
                stem.append(line)
        yield int(number), topic, "\n".join(stem), options, parts, figure_path


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(subject, context_file, output):
    spec = SPECS[subject]
    context = json.loads(context_file.read_text(encoding="utf-8"))
    if context["subject"] != subject:
        raise ValueError("学科与命题上下文不一致")
    rows = list(parse_markdown((SOURCE / f"{subject}.md").read_text(encoding="utf-8")))
    questions = []
    for expected, ((number, topic, stem, options, parts, figure), score, key) in enumerate(
        zip(rows, spec["scores"], spec["key"], strict=True), 1
    ):
        if number != expected:
            raise ValueError(f"题号错位：{number}，应为 {expected}")
        proffered = dict(zip((p["label"] for p in parts), key, strict=True)) if parts else key
        questions.append({
            "id": f"orig:{subject}:phase21-q{number:02d}",
            "topic": topic,
            "kind": ("single_choice" if number <= spec["single"] else
                     "multiple_choice" if options else "constructed_response"),
            "points": score,
            "stem": stem,
            "options": options,
            "parts": parts,
            "figure": {"path": figure, "sha256": sha256(output.parent/figure)} if figure else None,
            "verification_mode": "independent_review",
            "independent_check": {
                "checks": {"derivation": f"命题预验范围为{topic}；以下预期结论交由独立验算再对照。"},
                "parts": proffered if parts else {"overall": f"命题预期选择 {key}。"},
            },
            "proposed_answer": proffered,
        })
    record = {
        "subject": subject,
        "title": spec["title"],
        "provenance": {"dna_sha256": context["dna_sha256"], "context_sha256": sha256(context_file)},
        "questions": questions,
    }
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("subject", choices=SPECS)
    parser.add_argument("context", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    build(args.subject, args.context, args.output)
