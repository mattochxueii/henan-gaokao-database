# 中文题面协议 v2 与不可跳过的发布检查

1. 命题 AI 阅读 research、rules 和 analysis/language-rules.json，设计数学结构。内部规格保存在 math_spec；另存 solution、assessment 与真实 provenance。禁止 family。
2. 运行 writing-request 输出不含命题答案、设计路径、干扰项错因的写作请求。写作 AI 根据条件和任务写自然中文，用 {{formula_key}} 引用 formulae。attach-writing 绑定 math_spec SHA256，拒绝缺条件、公式来源不匹配、未定义符号、内部术语、提示和无依据高分。
3. 每题含 id/order/kind/points/module、math_spec、writing、solution.paragraphs、assessment。完整实物协议见 experiments/phase4/proposals/pilot.json、fullA.json、fullB.json；它们是历史生成证据，不是重新创作。
4. math_spec 包含 symbols、givens、tasks 与可选 options；expr 公式必须引用 givens 的同一表达式，由 notation.py 转成规范数学记号。自由 authored notation 仍需独立语义核对，程序不假装自动证明全部自然语言语义。
5. writing 含 spec_sha256、stem、parts、options、formulae、条件与任务锚点、used_symbols。生成器只向排版器传递 compile_writing 允许的学生可见字段。无法转换就拒绝，禁止原样回退 AST。
6. generate v2 返回 review-only/paper.pdf、student-text.json、数学验证和页面 manifest；尚不是可发布成品。先生成5题 pilot 并通过独立 PDF-only 审题，full 才接受 --pilot-certificate。
7. 考生审题者仅看最终 PDF 及其实际渲染 PNG，不能先读答案、JSON、设计、代码或其他审题报告。必须实际查看全部页面；像素未变的修订页允许复用先前真实图审证据并明确说明。
8. 审题记录 input_scope=pdf_only，reference_answers_read/internal_spec_read/proposer_design_read=false；逐题保存已知条件、设问理解、独立求解、选项答案、可读性/数学/分值通过与阻断项。整卷 overall_pass 也必须为 true。记录 PDF 和每页 PNG 哈希。
9. 命题者或另一审校者将 PDF 独立答案与当前数学检查逐题比对，保存 math-comparison。数列无穷项、轨迹充分性、参数根数及自然语言证明不得用有限枚举或辅助导数替代。partial/complete=false 不能变成程序完全证明。
10. publish 只复制被审过的同一 PDF 字节，检查文本/候选/数学/独立审题哈希、完整页数、逐题及整卷结论。修题必须新目录、重算、重排、重新审题；旧结论失效。
11. 答案 PDF 由自然中文高中解法生成，另做独立校审和实际页面检查。教师审核、考生实测、形式化证明与独立 AI 复核分开陈述。

## 参考运行

```powershell
python scripts/math_skill.py writing-request <候选.json> --output <无答案写作请求.json>
python scripts/math_skill.py attach-writing <候选.json> <写作结果.json> --output <v2候选.json>
python scripts/math_skill.py generate --engine ai --candidates <5题v2候选.json> --output <全新样卷目录>
python scripts/math_skill.py publish <样卷目录> --student-review <PDF盲审.json> --math-comparison <数学对照.json>
python scripts/math_skill.py generate --engine ai --candidates <整卷v2候选.json> --output <全新整卷目录> --pilot-certificate <样卷目录>/publication.json
python scripts/math_skill.py publish <整卷目录> --student-review <PDF盲审.json> --math-comparison <数学对照.json>
python scripts/math_skill.py verify <已发布整卷目录>
```

v1 协议只为历史证据和内部数学回放保留，不再允许直接导出 AI 学生卷。模板备用模式仍显式使用 --engine template。
