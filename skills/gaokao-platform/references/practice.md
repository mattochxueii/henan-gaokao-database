# 真题改编与核对

`authoring-context` 输出 `dna_sha256` 与来源题的 `version_sha256`。

改编 JSON 的顶层字段为 `source_id`、`source_version_sha256`、`dna_sha256`、`title`、`minutes`、`comparison`、`questions`，另可提供 `passages` 字符串字典。对比说明写明 `preserved_thinking`、`changed_condition_or_context`、`difficulty_basis`。每题写 `stem`、`kind`、`points`、`answer`、`explanation`，有选项则写 `options`，引用共享材料则写 `passage`。题面不能复用原句。数学子问放在 `parts`，公式用 `\\(...\\)`。

核对 JSON 的 `paper_sha256` 取自出卷目录的 `manifest.json`，`input_scope` 为 `student_pdf`。按卷面连续题号提供 `items`，每项包含 `number`、`answer`、`reasoning` 和核对结论 `consistent`。主观题可提供 `rubric`，每步写 `points` 与 `step`，合计为原题分。需要时加上可独立采纳的另解或例文。学生卷仅发 `paper.pdf`，听力稿与 `solutions.pdf` 单独发放。

完整模拟的上下文包含近期真实题面。候选 JSON 的 `provenance` 必须保存上下文给出的 `dna_sha256`，以及上下文文件本身的 `context_sha256`。用 `Get-FileHash` 或 `sha256sum` 获取后一项；候选应使用当前画像与实际读过的对照卷。
