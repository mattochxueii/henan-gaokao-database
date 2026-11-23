---
name: chemistry-gaokao
description: 使用河南选择性考试资料研究高中化学命题，按知识与能力规划训练或历史卷型模拟，并做化学独立复算、实验推理审查和概率研究。
---

# 河南高考化学研究与命题

在项目根目录使用 `python scripts/gaokao_platform.py`。通过 `chemistry-index <年份> [--number <题号>]` 读取卷面证据、版本及隔离原因。用 `research chemistry --year <年份> --region 河南` 读取完整可靠的本地电子版及摘要。`--strict` 限于历史候选严核摘要；`--official-only` 限于绑定官方原页的本地版本。审查记录需要题号、卷系、来源版本和真实推理动作。题位与选题依据优先使用跨来源内容一致且已重解的记录。

- **标准模拟**。用 `plan chemistry <年份> --mode standard` 获取蓝图和结构依据年份。2027 备考沿用 2026 年的 14 单选、4 必答非选择题和 100 分结构，标注 2027 实际卷型待核。
- **专项训练**。用 `plan chemistry <年份> --mode targeted` 确定考查能力。选择题的错误选项要分别对应真实误解。解答题用逐问推进的反应约束或实验数据形成推理。避免仅更换物质和数字。
- **预测研究**。用 `forecast chemistry <年份> --cutoff YYYY-MM-DD --evidence national/multisubject/chemistry-observations.json`。同省同卷系的后验观察只能提供研究样本。年份不足时保留弃权。

知识体系和标签在 `national/multisubject/chemistry-taxonomy.json`。优先使用守恒、条件、结构与证据四层审查。介质、相态、温度、限制试剂和近似均应写清。可配平的反应仍须独立确认在给定条件下合理。实验题给出变量、对照、可读数据及结论限度。有限模型的程序证据不能替代实验可行性或开放题审查。使用纸面实验或模拟数据并清楚标明。

程序题参照 `experiments/phase15/chemistry/candidates.json`。超出算子的整卷题参照 `experiments/phase16/henan-chem-100/source/candidates.json`，使用结构化独立复核通道。用 `generate chemistry <年份> --mode standard <候选> <目录>` 导出待审试卷。将学生 PDF 与必要图表给独立解题者，保存答案、证据边界和等效可得分步骤。用 `review <目录> <审查文件>` 校验答案，逐页检查电荷、下标、反应箭头、结构式及数据表，随后用 `publish <目录> <视觉回执>` 固定版本。匿名反馈沿用 `student_feedback.py`。
