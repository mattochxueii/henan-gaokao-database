# 整卷题位与结构复核

以同卷型的活跃真题版本选锚点。记录卷型、年份、题型内顺位、独立解题链与运算负担。目的性样本只提供编辑对照。末题可能采用常规短解，实际门槛针对末段组合和预设功能。

在逐题候选上填写 `placement`：

- `role` 取 `foundation`、`transfer` 或 `challenge`，`purpose` 说明本题承担的能力。
- `moves` 记录可复查的推理步骤，每步有 `kind`、`evidence`、`after`。依赖使用从 1 开始的先前步骤号，平行计算分别登记。常规检查可标 `routine: true`，如直接应用已知角范围检查端点，避免把标准解法标成挑战。
- `minutes` 是编辑估时区间。没有考生数据时不得填写实测时间、分数等值或区分度。
- `structures` 填写 `model`、`goal`、有序 `route` 及实质对象 `objects`。对象类型支持 `equation`、`function`、`recurrence`、`finite_model`。关键条件及参数保留在对象和路径中。不同题用可对照的名词。
- 若确需跨题共享对象，在 `coverage_plan.intentional_links` 登记题号对，独立评审补充 `necessary: true` 与实质证据。能力重叠可以说明取舍，重复给出其他题答案应修订。

先用五题 `position_pilot` 实际验证关键题位。正式整卷提交 `--pilot-certificate`，校准模式还需既有专项证书。生成时写出 `position-plan.json`。考生审题者从最终 PDF 重建 `position_review.questions` 的题号、步骤依赖和估时，报告绑定 PDF 校验值。发布门槛另外核查各题型末段、全卷梯度、17 分题推理、高重复和时长。项目自拟逐步评分另行提交。

保留计划和独立解题差异。编辑判断、程序检查、原题引用、教师审查和实际考生作答分别登记。
