# 整卷命题质量审稿

适用于 `simulate` 的六科标准原创卷。先运行 `authoring-context <学科> --limit 100 --output <上下文.json>`，在命题端读取 `references` 中的可用正文和 `quality_benchmarks.slots` 中逐题的版本、来源和覆盖。以 `analysis_db.fingerprint` 计算 `quality_benchmarks` 的指纹，写入候选的 `provenance.quality_reference_sha256`。

提交审稿单所需字段

- 根对象包含 `protocol`（`gaokao-editorial-audit-v1`）、`reviewer`、`paper_version`、`paper_pdf_sha256`、`reference_sha256` 和按题号排序的 `items`。从生成结果和版本文件读取值。数学使用 `review-manifest.json` 的 `writing_sha256` 与 `pdf_sha256`。
- 每题包含 `number`、`benchmarks` 和 `depth`。`benchmarks` 以年份为键，各项有真题的 `version_sha256` 和具体的 `comparison`。`depth` 分别列出 `reasoning_steps` 与 `linked_concepts`。把推理动作写成可以由题面和答案复核的步骤。
- 每题 `findings` 含 `distractors`、`depth`、`figure` 和 `language`。每条含 `verdict` 和 `evidence`。`pass` 表示审查有证据，`return` 应写明问题，非选题的干扰项及无图项可填 `not_applicable`。
- 选择题的 `distractors` 以实际未选中的选项为键。每个选项记录 `misconception`、能推到该具体结果的 `mechanism` 和布尔值 `plausible`。初稿尚未重解时，可用 `answer_key` 提交退稿。
- 配图题的 `required_figure_information` 写明移去图后缺失的关键读数、连接、方位或结构关系。
- 重写版的 `revisions` 以题号和退回规则为键，各值写清改动。再次送审时提供 `--previous-rejection` 绑定原退稿。程序会检查原退稿题是否真的换版。

运行 `quality-audit <目录> <审稿单.json>`。退稿时命令非零退出，仍写入审稿单与退回记录。审核通过需要最终学生卷的重解。数学以 `--blind-review` 指定已有盲核文件，其余科目先执行 `review`。发布时重新计算审稿结论并核对档案。样例见第22阶段两份标杆卷的 `quality-audit.json`。

审稿判断对应上述真题样本和项目的编辑标准。真实选项区分度及考生用时需由试做记录估计。
