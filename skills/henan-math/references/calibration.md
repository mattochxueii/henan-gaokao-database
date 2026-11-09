# 已校准题面与专项命题

私有档案中运行 `python scripts/national_cli.py research --series cn-new-gaokao-1 --verified-only`。严格模式只选已对照存档原页并完成独立重解的记录，排除隔离卷及题面冲突。第三方整理 PDF 仍是候选来源。题面、答案、深度分析各有版本，修订后以新答案绑定为准。

先读完整题面、来源页和 `deep_analysis`。为每道原创题选择实际可核的参考，写清转移的推理机制以及新题的数学结构差别。多选题检查各选项对应的错误方式，解答题检查首问结论如何支撑后问。公式解析范围不能决定原创题的设计范围。

使用 v2 JSON，顶层 `research_protocol` 为 `calibrated-v1`。每个 question 增加 `research_design`，其中含 `novel_structure`、`reasoning_target` 和 `references`。每条参考给出 `occurrence_id`、`version_sha256`、`transfer`、`structural_difference`。生成器核对当前已校准版本。无可用历史全文时可继续通用原创或模板模式，并说明参考范围。

独立考生审题先只看最终学生 PDF 及页图。独立重解、评题并给出证据。十分维度使用 0 至 2 的编辑评分，字段见 `scripts/mathgen/research_quality.py`。专项每题至少13/20，整卷前四题至少10/20，其余至少13/20。推理、阅读、分值均至少1，并且逐题无阻断。可对少量已校准真题另做匿名同题型配对比较，记录可比性及评审限制。

数列、导数、解析几何各做5题专项，候选中的 `module` 分别用“数列”“导数”“解析几何”。专项均通过后才组 `calibrated-v1` 整卷。对 `generate` 传三次 `--specialty-certificate`，各指向一份 `publication.json`。这一路径按目标地区配置读取题型和分值。旧的通用流程可继续使用五题 pilot 的 `--pilot-certificate`。

复核题只是编辑判断。报告中单列完整程序校验、部分符号支持、独立数学证明、教师审核和学生实测。已发布候选可用 `scripts/student_feedback.py` 汇总匿名作答。详见 [作答反馈指南](student-feedback.md)。
