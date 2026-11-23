# 第十六阶段 · 理科整卷与电子版入库

## 验收结果

- `plan <subject> 2027 --mode standard` 实际返回 2026 年同省、同卷系结构。物理为 7 单选（28 分）、3 多选（18 分）、5 非选择（54 分）。化学为 14 单选（42 分）、4 非选择（58 分）。生物学为 16 单选（48 分）、5 非选择（52 分）。三科均 100 分、75 分钟。2027 年实际卷面待确认。
- 原程序题继续使用 `program` 和 `problem.op`。复杂题可选 `independent_review`，提供 `proposed_answer` 以及 `independent_check.checks` 和 `independent_check.parts`。检查键允许 `conservation`、`dimensions`、`reaction_conditions`、`experimental_controls`、`derivation`、`assumptions`，并逐问提供非空依据。审阅者重新求解，提交同一题面版本、另行推导、独立作答和相应检查。整卷非选择题另须提交合计等于题目分值的自拟评分。未知题仍须解决数学或科学分歧后才能发布。
- 实际化学卷位于 `experiments/phase16/henan-chem-100/`，4 道非选择题为双平衡反应、含铜焙砂流程、供氧与固体作用的对照实验、有机物逆向推断。卷内实验数据为原创模拟数据。18 题全部从学生版重解，部分数值另用精确分数、对数和电子当量复算。18 题均为独立推理通道，专用程序算子全验 0 题。没有教师审阅或学生实做数据。
- 学生卷 8 页，参考答案与项目分步评分 5 页。逐页检查 122 dpi 渲染。原草稿曾出现分页产生的空页和实验表格偏小，修订后重新渲染、核对并绑定文件哈希。
- 用既有第九阶段原创候选实际运行数学 `generate --engine ai --mode full --skip-pilot`，在新输出路径生成 19 题、150 分学生审阅 PDF 和 `pilot-waiver.json`。跳过前置小样卷；整卷题位检查、数学核对及最终发布审阅继续执行。
- 化学以 2026-11-23 为截止日实际输出 2025、2026 两年卷面观察。两项目标均观察到 2/2，状态 `small_sample_trend`，预测概率空，未进入历史概率计分。没有明确可用时间的观察继续排除。
- 实际运行 `test_multisubject.py`、`test_physics_quality.py`、`test_chemistry_quality.py`、`test_science_intake.py`、`test_paper_quality.py`、`test_phase4.py`、`test_forecast_validation.py`，共 87 项通过。数学 v3 冻结预测 SHA-256 仍为 `33c20281a81ddc747189bc251564b90fc725ad86f540ad068c767ea0ee185931`。

## 理科电子版快导

整理后的 JSON 可直接导入。用 Markdown 时，JSON 保留卷、题号、题型、分值、选项和图片等字段，Markdown 每题写 `## 题号`（例如 `## 3`），正文下写 `### 答案`。两个文件的题号须一一对应。图片文件须为真正的 PNG/JPEG，文件路径相对 `--images` 目录。仅供软件验收的合成样本在 `tests/test_science_intake.py`。

```text
python scripts/gaokao_platform.py import-electronic paper.json --images ./images
python scripts/gaokao_platform.py import-electronic paper.json --markdown text.md --images ./images
python scripts/gaokao_platform.py research chemistry --year 2026 --region 河南 --verified-only
python scripts/gaokao_platform.py research chemistry --year 2026 --region 河南 --official-only
```

顶层填写 `dataset_id`、`subject`、`year`、`title`、`source`、`questions`。地区默认河南。`source` 包括 `title`、`rights_basis`，按资料附 `url`；原页来自官方时另填 `authority: official` 并在题目中登记 `page`、`official_page`。每题含 `number`、`kind`、`points`、`stem`、`answer`，选择题附 `options` 字典（A–D），有图附 `images` 文件名数组，有子问可附 `parts`（各含 `label`、`text`）。`conflict_note` 保留差异。使用 `conflict_severity: material` 隔离影响解答的冲突。选择性考试卷型由已有历史映射校验。

导入仅写 `.local-data/subject-imports/`，并记录当前文本与答案版本、图片哈希及定位。检索记录中 `local_bundle_path` 与 `asset_refs[].path` 组合为图文件路径。完整可靠电子版标记 `usable_for_practice`，保留轻微差异；带官方来源、原页、页码及对应图片哈希的完整版本可检索为 `strict_official_verified`。该分级依据录入的资料出处与本地文件绑定。导入验证不会主动访问外部网站鉴定图像真伪。现有隔离记录保留，带必要图表的更完整版本可单独判断。

## 尚缺原始输入

统一检索当前在河南 2025/2026 返回的全文各科均为 0；物理摘要 4/3 条、化学 5/3 条、生物学 2/2 条，语文及英语各 0/0 条。软件快导用合成数据验收，没有以合成数据增加真题数。首要缺项是能合法本地使用的原始电子试卷，带同版答案、原页页码与独立清晰图件。物理尤其需要刻度、单位和完整实验图；化学需要可辨结构式、箭头与条件；生物学需要清晰图例、对照表和实验附件；语文需要完整阅读材料与原版页码；英语需要与笔试同卷匹配的听力音频、听力文本和答案（如有）。
