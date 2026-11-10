# 命题关联与概率研究数据

## 关系和可用日期

`evidence.jsonl` 保存结构化事实、学科、来源权威级别、原始公开日期、保守可用日、适用年份和使用限制。未知日期保留 null。后来回顾旧试卷的文章，只从该文章公开时可用。课程政策的适用时间与公开时间分别判断。

`targets.json` 固定试卷级事件和评分规则。模块主类采用四大内容主题，三角与数列归入函数，向量、复数、空间和圆锥曲线归入几何与代数，计数归入概率统计。数学建模为跨主题方式。题目主类按原始分值只计一次，次要主题线索可以多选。2020、2025 课标版的表 1、2 都支持这一对照口径。建模实践和机动课时不按题目主模块分配。

`contemporaneous.jsonl` 保存可用时间明确的纸卷结构观察。公开评析只举例的内容可以证明某例出现，无法证明其余题目没有同类方式。现有同期回测只计分“全卷少于 22 题”。

私有版 `research/` 保存活跃版本对应的 294 条题目特征及纸卷观察。题型、分值、主类、次类、条件、跨问提示、数学习惯方法、关键转化线索、情境与建模、运算负担和创新线索分别保存。推理深度和运算量仅为既有编辑分析的投影，未知不赋零。机器采用题面及原归档分析两个视图，33 道题另经独立题面复核。详见两组一致率。未确认主类及隔离缺口合并入 150 分分母的待分配分值，由此产生每个主题的上下界。

SQLite 由来源和标签物化，表为 Evidence、CurriculumTopic、CurriculumWeight、ForecastTarget、ExamFeature、FeatureObservation、Forecast、Backtest，政策、评价要求、官方评析及教学趋势为类型视图。ExamFeature 的 occurrence_id、paper_id 及题目版本对应主真题库。公开证据库没有私有 ExamFeature 行。

## 模型及计分

- `frequency` 按年份块平均，采用 Beta(1,1) 平滑。同一全国卷跨省保留一份。同年Ⅰ、Ⅱ卷同块，Ⅱ卷相对目标Ⅰ卷权重为 0.5。跨年可识别的同源题群合并为一个有效块。
- `recent` 在年度频率上采用 3 年半衰期。
- `curriculum` 将主题课时占比 `s` 转为 `1-(1-s)^6`。6 个有效机会是事先固定的人为参照。课时表本身没有给出这个概率。
- `policy_experiment` 在近期模型上加入定性政策的弱先验。短卷只在同期证据确认 2024 结构变化已公开后，对更早结构权重乘 0.25。先验为透明的敏感性设定，政策事件并不保证题型变化。
- 少于两个有效年份块，或未知卷面超过 20%，历史模型保留弃权。未知卷面在两种极端赋值下给出敏感性范围。零正例的具体结构平滑值单列为先验主导。不同目标可共存，概率无需加总。

回测用上一年 12 月 31 日截止的同期材料。2026 年整理的真题特征不进入 2023–2026 严格回测；只在当前前瞻研究及描述性对照中使用。目标年份结果在事后读取，评分用 Brier、对数损失和分箱观察。分箱观测少且Ⅰ/Ⅱ卷同年相关，不能据此认证校准。2024 结构断点权重是在本项目 2026 年制定的回放规则，存在事后规则选择风险。

## 复现

```powershell
python scripts/forecast_research.py backtest --output work/strict-backtest.json
python scripts/forecast_research.py database --output work/public-research.sqlite
python scripts/forecast_research.py study --audit forecast/research/independent-labels.json --cutoff 2026-11-10 --output work/private-research --snapshot work/henan-2027-math-v3.json
python scripts/forecast_research.py verify-freeze forecast/frozen/henan-2027-math-v3.json
```

私有复现需要已恢复的严格真题目录。使用相同输出文件名可得到相同冻结 run_id 和内容哈希，输出目录必须为空缺。冻结使用排他创建，保存候选、模型文件、目标和数据哈希。该机制提供版本校验和可追溯性。GitHub 私有提交和 CI 是发布证据；本轮没有独立时间戳机构的令牌。结果发生后只创建独立评分记录，原候选保持冻结。日期不明确或适用卷系不符时暂停评分。

模式接口与未来计分字段见 [数学 Skill 协议](../skills/henan-math/references/forecast.md)。
