"""Mathematical-object and response-format checks shared by both providers."""

import re
import sympy as s
from .quality import expression

CHOICE_INSTRUCTIONS = ("选择所有正确命题", "判断下列命题", "选择所有正确选项")
MODULES = {
    "数列",
    "函数与导数",
    "集合与复数",
    "三角与向量",
    "解析几何",
    "概率统计",
    "立体几何",
    "排列组合",
}


def audit_item(question):
    errors = []
    stem = question.get("stem", "")
    if not stem.strip():
        errors.append("missing_stem")
    kind = question.get("kind")
    options = question.get("options")
    if kind in ("single_choice", "multiple_choice"):
        if not isinstance(options, dict) or set(options) != set("ABCD"):
            errors.append("missing_options")
    if kind == "single_choice" and any(
        word in stem for word in ("另请", "并证明", "说明理由", "写出完整范围")
    ):
        errors.append("response_kind_conflict")
    if sum(stem.count(word) for word in CHOICE_INSTRUCTIONS) > 2 or (
        stem.count("选择所有") > 1
    ):
        errors.append("duplicate_instructions")
    values = []
    for key, option in (options or {}).items():
        if not option.get("text", "").strip():
            errors.append("missing_option_text")
        if kind == "single_choice":
            if not option.get("error_path"):
                errors.append("missing_distractor_rationale")
            try:
                value = expression(option["semantic_value"])
                values.append(value)
                domain = question.get("answer_domain")
                if domain and value.is_real is True:
                    lower = expression(str(domain[0]))
                    upper = expression(str(domain[1]))
                    if bool(value < lower) or bool(value > upper):
                        errors.append("option_out_of_range:" + key)
            except (ValueError, KeyError, TypeError):
                errors.append("invalid_option:" + key)
    if len(values) > 0 and len({str(s.simplify(v)) for v in values}) != len(values):
        errors.append("equivalent_options")
    if question.get("module") not in MODULES:
        errors.append("curriculum_module_unapproved")
    if stem.count(r"\(") != stem.count(r"\)"):
        errors.append("formula_delimiter_missing")
    return {
        "passed": not errors,
        "errors": errors,
        "reviewer": "deterministic-quality-v2",
        "coverage": "可计算范围、必要字段与格式。语义歧义、课程逐条匹配和教育测量仍须独立审题。",
    }


def misconception_options(question, target):
    p = question["parameters"]
    a, b, m = (p[k] for k in ("a", "b", "m"))
    family = question["family"]
    N = a + b
    if family == "urn_pair":
        question["answer_domain"] = [0, 1]
        pool = [
            (2 * s.Rational(a * b, N * N), "误按有放回抽样"),
            (s.Rational(a * b, N * (N - 1)), "只计红蓝一种顺序"),
            (s.Rational(a, N), "把联合事件误作一次取红"),
            (s.Rational(b, N), "把联合事件误作一次取蓝"),
            (s.Rational(a * (a - 1), N * (N - 1)), "误求两次均红"),
            (s.Rational(b * (b - 1), N * (N - 1)), "误求两次均蓝"),
        ]
    elif family == "trig_square":
        question["answer_domain"] = [-1, 1]
        pool = [
            (-target, "和角转化时符号错误"),
            (s.Rational(3, 4), "平方后漏去常数项"),
            (s.sqrt(6) / 4, "把和直接除以2"),
            (s.Rational(1, 4), "二倍角系数遗漏"),
        ]
    elif family == "complex_norm":
        pool = [
            ((a - b) ** 2 + m, "把模平方当虚部平方"),
            ((a - b) ** 2, "只保留实部平方"),
            (s.sqrt(m), "把虚部平方误作虚部绝对值"),
            (a * a, "把实部平方当虚部平方"),
        ]
    elif family == "integer_set":
        pool = [
            (m + 1, "未剔除倍数"),
            (sum(t % b == 0 for t in range(a, a + m + 1)), "只数被剔除元素"),
            (sum(t % b != 0 for t in range(a + 1, a + m)), "误把闭区间当开区间"),
            (m, "仅剔除一个端点"),
        ]
    elif family == "vector_sum":
        pool = [
            (a * a + 1, "漏加第二向量长度平方"),
            ((a + 1) ** 2 + (a + 1) ** 2, "垂直条件解t时丢负号"),
            ((a + 1) + (1 - a), "把分量和当模平方"),
            (s.sqrt(2 * (a * a + 1)), "只求模"),
        ]
    elif family == "ellipse_chord":
        pool = [
            (a * s.sqrt(3) / 2, "只取一个端点到纵轴距离"),
            (2 * a, "误把该弦当长轴"),
            (b * s.sqrt(3), "混用长短半轴"),
            (a, "把纵坐标比例当弦长比例"),
        ]
    elif family == "positive_roots":
        pool = [
            (0, "仅用根的和、积为正"),
            (-1, "判别式移项符号错误"),
            (s.Rational(1, 2), "遗漏判别式中的因子2"),
        ]
    elif family == "trig_count":
        pool = [
            (2, "忽略自变量倍角"),
            (8, "把正负三角值混计"),
            (3, "漏掉最后半周期的一个交点"),
        ]
    elif family == "binomial":
        pool = [
            (s.binomial(2 * b, b), "误求常数项"),
            (2 * b, "只选择一个倒数项"),
            (s.binomial(2 * b, b - 2), "指数方程下标偏一"),
            (1, "仅计首末项系数"),
        ]
    elif family == "variance":
        pool = [
            (m * b, "方差只乘缩放系数"),
            (b, "认为线性变换不改变方差"),
            (m * m * b - a, "把平移常数带入方差"),
            (m * s.sqrt(b), "混淆标准差和方差"),
        ]
    elif family == "exp_peak":
        pool = [
            (a, "只求极大点横坐标"),
            (1 / s.E, "漏掉函数的线性因子"),
            (a * s.E, "指数代入符号错误"),
            (0, "把右侧极限当最大值"),
        ]
    elif family == "seq_interlace":
        pool = [
            (m * (2 * a + b), "忽略两子列的递增"),
            (m * (2 * a + b) + m * (m - 1), "只累加一个子列的增长"),
            (2 * m * a + 2 * m * (2 * m - 1), "误把整个数列当公差2"),
        ]
    else:
        raise ValueError("该模板尚无经审查的干扰项模型")
    choices = [(target, "正确解")]
    for value, reason in pool:
        value = s.simplify(value)
        if value.is_real is False or any(
            s.simplify(value - old) == 0 for old, _ in choices
        ):
            continue
        domain = question.get("answer_domain")
        if domain and (bool(value < domain[0]) or bool(value > domain[1])):
            continue
        choices.append((value, reason))
        if len(choices) == 4:
            return choices
    raise ValueError("无法产生三个不同且合理的干扰项")
