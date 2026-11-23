# 全国多学科平台

数学沿用既有数据库、版本、学科 Skill、独立验证和冻结预测。物理、化学、生物学通过统一入口连接各自的验证器。语文和英语登记在学科目录，英语预留笔试、听力和听说部分。

## 安装与操作

在仓库根目录运行。公开候选版可先运行 `python scripts/local_data.py init`，随包数学原创样题可以立即查询。三门理科项目原创示例位于 `experiments/phase13/`。

```sh
python scripts/install_math_skill.py --skill gaokao-platform
python .agents/skills/gaokao-platform/scripts/run.py subjects
python scripts/gaokao_platform.py exam physics 2026 --region 河南
python scripts/gaokao_platform.py research chemistry --year 2025 --region 河南 --verified-only
python scripts/gaokao_platform.py index .local-data/multisubject.sqlite
python scripts/gaokao_platform.py plan biology 2026 --mode standard
python scripts/gaokao_platform.py generate physics 2026 experiments/phase13/physics/candidates.json .local-data/physics-draft
python scripts/gaokao_platform.py review .local-data/physics-draft experiments/phase13/physics/review.json
python scripts/gaokao_platform.py forecast physics 2027 --cutoff 2026-11-10
```

演示目录的评审适用于同版本示例题。重新渲染的 PDF 需要逐页复核后，用 `publish <输出目录> <视觉记录>` 写新回执。PDF 只含学生可读题面或独立解析；结构化规格与程序解释留在验证记录。

## 数据边界与导入

- `catalog.json` 是公开资料登记。省级卷需要当年当地证据。河南旧理综的三科关系指向同一综合卷。2027 河南的详细选择性试卷结构待核。
- 私有研究样本 `research-samples.json` 是真题的自写语义摘要及独立解答。保留原题号、来源版本与图像情况，`content_complete` 为 false。公开候选只附来源目录及项目原创题。
- 合法全文使用六张既有 JSONL 表加 `manifest.json` 的规范化数据包。输入目录的 `distribution` 须为 `local-only`，`version_scheme` 为 `normalized-question`。为原文来源填写 `rights=local_copy_authorized` 与具体 `rights_basis`，在 `paper-regions` 登记当年当地用卷证据。为 `questions` 提供完整题干、选项、公式、子问、附件引用和 `content_complete=true`；学科表格、反应条件、物理量等可按需放在 `subject_data`。附件列清单和 SHA-256，答案绑定题面版本。用 `python scripts/gaokao_platform.py import <资料包目录>` 写入 Git 忽略的 `.local-data/subject-imports/`。不同省、不同卷系或证据不足的新卷先核实目录。自带副本的题保留为待复核，已隔离题从默认研究检索排除。
- 统一 SQLite 是派生索引。学科、用卷关系、题目及版本化答案用独立表，试卷、来源、知识点、分析、验证、原创和预测等类型用带类型的实体表。数学题目保留原实例 ID 和版本哈希，旧数据库和备份可照原路径使用。未恢复数学全文时，仍可构建目录和理科索引。索引输出用 `math_archive_available=false` 显式记录覆盖缺口。
- 理科预测输入分学科、地区、卷系。证据文件包含 `targets` 与逐年 `observations`，观察值允许未知，须标注公开时间、来源、版本哈希和独立核查。使用至少五个具有二值变化的可比较年份才给出探索性频率。概率快照由 `--freeze <新文件>` 创建，`score` 按同一学科、地区、卷系和年度评分。真题摘要只供研究，不会自动成为历史预测标签。

## 河南物理题证与试做

用 `python scripts/gaokao_platform.py physics-index 2026 --number 12` 查询卷面页码、图表状态与隔离原因。正文资料可合法本地导入；隔离版本不会进入默认命题参考。试做入口与说明见 [HN14-P40-v1](../../experiments/phase14/physics/README.md)。

## 河南化学题证与试做

运行 `python scripts/gaokao_platform.py chemistry-index 2026 --number 17` 查看候选版本和隔离原因。可运行 `research chemistry --year 2026 --strict` 查询经版本双复核的本地研究摘要。安装化学入口用 `python scripts/install_math_skill.py --skill chemistry-gaokao`。试做见 [HN15-C40-v1](../../experiments/phase15/chemistry/README.md)。

理科电子版快导、独立复核出卷和 2027 模拟蓝图的用法见[第十六阶段验收](../../reports/phase16.md)。
