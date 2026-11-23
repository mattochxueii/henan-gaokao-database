---
name: gaokao-platform
description: 检索语数英明文真题、分析新高考命题特征并生成、独立核阅与排版原创试卷；转发现有理科、数学与预测入口。
---

# 全国高考真题研究与原创命题

在项目根目录运行 `python scripts/gaokao_platform.py`。已安装入口可用本目录 `scripts/run.py`，跨目录时使用 `--database`。

1. 用 `exam <subject> <year>` 核对适用身份。适应性演练用 `research --adaptation` 单独查询。资料完整度、来源定位、答案和冲突按题检查。
2. 主三科先运行 `dna <subject>`，再运行 `research <subject> --region 河南 --year <year>`，读取目标题位的真实材料和逐题证据。画出题位与文本、设问和能力的对应。没有题面样本时只能使用来源可追溯的结构与评析，候选需标为 `structure_only`；独立答案和评分记录与预测无关。
3. `plan chinese|english <year> --mode standard` 获取逐题分值与特征。语文保留指定年份的题号、连续的阅读材料与评分颗粒。英语听力信息单独存储；先核对听力播放次数、题组，完整卷 150，河南笔试分另由 `english-score` 换算。材料均须原创或获得明确使用许可，勿只换同义词。
4. 由宿主 AI 完成有版本的原创候选。语文/英语候选键参考 `experiments/phase17/<subject>/candidate.json`。先核对选项与文本证据，避免范围扩大、时序错误等被误当正确；语文古诗文核字、英文逐空作答；主观题分解给分且写作附合格范文。
5. `generate <subject> <year> --mode standard <candidate.json> <new-folder>` 生成学生卷。独立复核只从学生题面和必要的英语听力文本作答。用 `review <folder> <review.json>` 校验版本、答案和评分，再逐页渲染检查，使用 `publish <folder> <visual.json>` 绑定最终 PDF。学生版、听力稿、解析各自发放。
6. 数学用 `math` 转发现有数学规划、原创、独立求解、正式发布和预测程序。检索优先读取明文数学快照，原题 ID 与旧复核证据继续有效。
7. 物化生沿用原有 `plan/generate/review/publish`，`program` 或 `independent_review` 两条通道。研究预测可用 `forecast`，四年以内仅输出小样本历史趋势。
