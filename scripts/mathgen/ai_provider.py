"""Replaceable AI proposal transports. Host-file mode performs no template generation."""

import json
import os
from pathlib import Path
import urllib.request
from analysis_db import fingerprint
from gaokao import read_json, require

MAX_BYTES = 700000
SCHEMA_VERSION = 1
PROTOCOL = {
    "schema_version": 1,
    "blueprint": {
        "mode": "full|mixed|sequence|derivative|acceptance",
        "slots": [{"module": "高中数学模块"}],
    },
    "question_fields": ["id", "slot", "kind", "points", "module", "problem", "design"],
    "problem": {
        "context": "中文语境",
        "tasks": "结构化数学任务数组",
        "options": "单选A-D，各含text(LaTeX)、semantic_value(表达式)、error_path(典型错因)",
        "assertions": "多选A-D的真值任务",
    },
    "design_fields": ["structure", "reasoning_path", "knowledge_combination"],
    "task_fields": {
        "evaluate": ["expression"],
        "equation": ["expression", "domain", "unique"],
        "system": ["variables", "expressions", "conditions"],
        "sum": ["expression", "index", "lower", "upper"],
        "product": ["expression", "index", "lower", "upper"],
        "recurrence": ["relation(用u(n),u(n+1)表示且移项为0)", "initial"],
        "recurrence_sum": ["relation", "initial", "weight(用k)", "upper"],
        "derivative": ["expression", "variable", "domain", "at(可选)"],
        "extrema": ["expression", "variable", "domain", "open"],
        "monotonicity": ["expression", "domain", "open"],
        "parameter_monotone": ["expression", "parameter", "domain", "open"],
        "parameter_bound": ["expression", "parameter", "domain", "open"],
        "nonnegative": ["expression", "domain", "open"],
        "probability": ["sample_space", "condition", "event"],
        "count": ["sample_space", "condition", "event"],
        "coefficient": ["expression", "power"],
    },
    "constraints": "所有数学条件显式进入规格。表达式只允许安全四则、幂、初等函数。单选只求一个标量；含证明的题目用constructed_response。",
}
LEGACY_PROTOCOL = PROTOCOL
PROTOCOL = {
    "schema_version": 2,
    "paper": {
        "mode": "pilot|full",
        "title": "规范中文数学模拟试卷标题",
        "total_points": "按已核实卷型",
        "minutes": 120,
    },
    "questions": "每题含id/order/kind/points/module/math_spec/writing/assessment/solution；禁止family",
    "math_spec": {
        "givens": "原始数学条件",
        "tasks": "安全数学操作，供独立求解；不得含命题者标准答案",
        "options": "数值选项语义或多选assertions",
    },
    "writing": {
        "stem": "AI单独写作的自然中文题面，用{{key}}引用公式",
        "parts": "递进中文设问与task_refs",
        "options": "A-D的中文/公式文本",
        "formulae": "source与given绑定，或常用高中notation；禁止AST、程序词和方法提示",
        "condition_anchors": "必须在题面出现的必要条件",
        "request_anchors": "明确设问",
        "definitions": "symbol/anchor定义",
        "used_symbols": "已定义符号",
        "spec_sha256": "本地绑定math_spec的校验值",
    },
    "assessment": "八维以上能力判断、具体分值依据、子问分值及递进关系、预计时间；不能按任务数套标签",
    "solution": "独立求解前保存的命题解答，不送入求解器或考生盲审者",
    "release_policy": "先5题pilot的PDF-only审查通过，再full；发布必须绑定全部PDF页、独立数学对照，程序通过不是高考风格通过",
    "supported_legacy_math_operations": LEGACY_PROTOCOL["task_fields"],
}


def validate_document(document):
    require(document.get("schema_version") in (1, 2), "候选协议版本无效")
    if document.get("schema_version") == 2:
        require(
            isinstance(document.get("paper"), dict)
            and isinstance(document.get("questions"), list)
            and 0 < len(document["questions"]) <= 60,
            "中文题面协议缺少试卷/题目",
        )
        for q in document["questions"]:
            require(
                "family" not in q
                and all(
                    key in q
                    for key in ("math_spec", "writing", "assessment", "solution")
                ),
                "缺少独立写作层或伪装模板",
            )
        return document
    require(
        isinstance(document.get("questions"), list)
        and 0 < len(document["questions"]) <= 60,
        "候选题量无效",
    )
    require(isinstance(document.get("blueprint"), dict), "缺少AI蓝图")
    for question in document["questions"]:
        require(
            "family" not in question and "parameters" not in question,
            "AI模式禁止模板题目族输入",
        )
        require(
            question.get("design", {}).get("structure")
            and question["design"].get("reasoning_path"),
            "缺少动态设计依据",
        )
        require(
            question.get("problem", {}).get("tasks") is not None, "缺少结构化数学任务"
        )
    return document


class ProviderError(ValueError):
    pass


class HostAIProvider:
    name = "host_ai"
    mode = "ai"

    def __init__(self, path):
        path = Path(path)
        require(path.stat().st_size <= MAX_BYTES, "宿主候选文件过大")
        self.raw = path.read_text(encoding="utf-8-sig")
        try:
            self.document = json.loads(self.raw)
        except ValueError as error:
            raise ProviderError("宿主候选JSON格式错误") from error
        validate_document(self.document)
        provenance = self.document.get("provenance", {})
        require(
            provenance.get("mode") == "ai" and provenance.get("provider") == "host_ai",
            "缺少宿主AI原始生成声明",
        )
        if self.document.get("schema_version") == 2:
            return
        require(
            "questions" in self.document and "blueprint" in self.document,
            "候选缺题目或蓝图",
        )
        for question in self.document["questions"]:
            require(
                "family" not in question and "parameters" not in question,
                "AI候选不得携带模板题目族",
            )
            require(
                question.get("design", {}).get("structure")
                and question["design"].get("reasoning_path"),
                "缺少自主设计的结构与推理说明",
            )

    def propose(self, context=None, instructions=None):
        return self.document


class OpenAIProvider:
    name = "openai_responses"
    mode = "ai"

    def __init__(
        self,
        model,
        timeout=45,
        max_output_tokens=12000,
        max_calls=2,
        max_input_chars=40000,
        transport=None,
    ):
        require(model and len(model) < 120, "需要显式配置模型名称")
        self.model = model
        self.timeout = min(timeout, 90)
        self.max_output_tokens = min(max_output_tokens, 24000)
        self.max_calls = min(max_calls, 3)
        self.max_input_chars = max_input_chars
        self.transport = transport or urllib.request.urlopen
        self.calls = 0

    def propose(self, context, instructions):
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ProviderError("未配置OpenAI API密钥，可使用宿主AI候选文件")
        prompt = json.dumps(
            {
                "research_context": context,
                "task": instructions,
                "required_protocol": PROTOCOL,
            },
            ensure_ascii=False,
        )
        require(len(prompt) <= self.max_input_chars, "模型输入超过上下文预算")
        body = {
            "model": self.model,
            "store": False,
            "max_output_tokens": self.max_output_tokens,
            "input": [{"role": "user", "content": prompt}],
            "text": {"format": {"type": "json_object"}},
        }
        # Key is only sent in the Authorization header. Never log headers or HTTP exception text.
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + key,
                "Content-Type": "application/json",
            },
        )
        remaining = self.max_calls - self.calls
        if remaining <= 0:
            raise ProviderError("模型调用总预算已用尽")
        for attempt in range(remaining):
            self.calls += 1
            try:
                with self.transport(request, timeout=self.timeout) as response:
                    data = response.read(MAX_BYTES + 1)
                require(len(data) <= MAX_BYTES, "模型响应超过大小限制")
                envelope = json.loads(data)
                if envelope.get("status") != "completed":
                    raise ProviderError("模型输出未完成")
                text = "".join(
                    part.get("text", "")
                    for item in envelope.get("output", [])
                    for part in item.get("content", [])
                    if part.get("type") == "output_text"
                )
                document = json.loads(text)
                validate_document(document)
                for question in document["questions"]:
                    question["generation"] = {
                        "provider": self.name,
                        "model_version": self.model,
                    }
                document["provenance"] = {
                    "mode": "ai",
                    "provider": self.name,
                    "model": self.model,
                    "response_id": envelope.get("id"),
                    "api_calls": self.calls,
                    "template_calls": 0,
                    "usage": envelope.get("usage"),
                    "raw_response_sha256": fingerprint(envelope),
                }
                return document
            except Exception:
                if attempt + 1 == remaining:
                    raise ProviderError(
                        "模型请求失败、超时或响应格式无效。详细请求与密钥未写入日志"
                    ) from None


def select_provider(engine, candidates=None, model=None, allow_template_fallback=False):
    if engine == "template":
        from .providers import FamilyProvider

        return FamilyProvider()
    if candidates:
        return HostAIProvider(candidates)
    if model and os.environ.get("OPENAI_API_KEY"):
        return OpenAIProvider(model)
    if allow_template_fallback:
        from .providers import FamilyProvider

        return FamilyProvider()
    raise ProviderError(
        "AI不可用，需要宿主候选文件或已配置模型，显式允许后才能回退template"
    )
