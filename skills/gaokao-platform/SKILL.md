---
name: gaokao-platform
description: 六科真题检索与拼卷、同构改编、目标卷系整卷模拟与专项训练。命题读取版本绑定的真题和画像，学生卷与答案独立核对。
---

# 全国高考真题研究与出题

统一入口为项目根目录的 `python scripts/gaokao_platform.py`。安装后的入口为同目录结构下的 `scripts/run.py --database <项目目录>`。以下命令都接在统一入口后。

## 真题检索与拼卷

- `research physics --region 河南 --year 2026 --topic 电场` 读取题面、原题位置和参考答案。主三科与物理、化学、生物学使用相同接口。演练卷加 `--adaptation`，要查缺图、缺答或隔离状态再加 `--include-incomplete`。隔离题不参与默认选题。
- `assemble chinese <新目录> --year 2024 --topic 信息类阅读 --limit 5` 生成独立学生卷 PDF 和 Markdown。可用多个 `--question-id` 固定题单，或用 `--kind` 筛题型。完形、七选五和听力按完整题组展开。
- 独立从学生 PDF 作答，检查图件与材料，再用 `workbook-review <目录> <逐题核对.json>` 对照档案答案并生成分离的答案 PDF。听力文字通过单独的朗读稿提供。保持原题年份、题号和版本可追溯。
- `import-electronic <试卷.json> --images <题图目录> --track` 从透明的来源材料追加私有明文档案。理科题图必要却缺失时保留题面和单题缺图标注。运行 `python scripts/audit_core_papers.py --write-profiles` 更新画像。

## 真题同构改编

1. `authoring-context english --source-id 2025-cn-english-national-1:q021 --output <对照.json>` 获取题面和版本绑定的命题依据。
2. 新题复用原题的核心推理，不复用原句或仅换数字。说明保留的考查动作、条件或情境的实质变化，以及难度依据。候选格式见 [改编与核对](references/practice.md)。
3. `adapt english <改编候选.json> <新目录>` 生成改编学生卷。另行求解，运行 `workbook-review`。
4. 理科改编候选应按理科的结构提供 `topic` 和 `verification_mode`。可计算题提交 `problem.op`，其余提供逐问独立核对要点。生成学生版后使用 `review` 与 `publish`。

## AI 高仿真完整模拟

1. 先运行 `authoring-context math --output <真题上下文.json>`，读取其中三个年份的真实题面和 `data/dna/math.json` 的题位、条件及推理层次。其他学科更换学科名。
2. 数学候选遵循 `scripts/math_skill.py` 的内部规格与写作分层，答案子问与分步评分分别保留。适合用图呈现条件的立体几何、解析几何和函数题优先配清晰示意图。语文和英语用 `plan <学科> <年份> --mode standard` 获取结构与蓝图哈希。不要将最近某年考点位置当成下一年的必然规律。
3. 宿主 AI 生成候选后，运行 `simulate <学科> <年份> <候选.json> <新目录> --context <真题上下文.json>`。主三科使用 2024–2026 年Ⅰ卷。理科使用 2025、2026 年河南正式选择性考试的正文与画像，沿用 `plan <学科> <年份> --mode standard` 的 100 分蓝图和两种核对通道。2027 年模拟的卷型依据在蓝图中列明。
4. 理科命题读上下文的 `paper_layout`。物理至少 6 道配图选择题，建议 6–8 道，第 11–12 题嵌入填空、第 13–15 题保留演算。化学至少 7 道配图选择题，建议 8–10 道，第 15–18 题嵌入填空。生物学至少 4 道配图选择题，第 17–21 题嵌入填空，因果解释和实验设计预留较长答位。题干须指向参与求解的图，组别和计分说明由栏目统一印出。用至少三个连续下划线写空位，可按题内顺序显式加 ①、②，排版会自动补全圈号。
5. 数学用 `math publish <目录> --student-review <核对.json> --math-comparison <数学核对.json>`。语英与理科用 `review <目录> <核对.json>`，逐页验收后用 `publish <目录> <视觉核对.json>`。理科标准卷的重解记录应绑定学生 PDF 的校验值，包括配图选择题的 `figure_reading` 和所有空位的 `blank_answers`，按题内圈号排列。交付前核查题图标签、每根横线与后接单位、公式后标点及分页。

## 专项训练

`train english <新目录> --year 2025 --topic 阅读理解 --limit 3` 为指定弱项抽真实题。需要新题时，从同一考点的对照材料选取参考，走改编流程；数学也可用 `math generate --engine ai --mode sequence|derivative --candidates <候选.json> --output <新目录>` 完成原创专项并沿用数学独立核对。

原有理科、数学预测和试做工具仍由同一入口转发。版式可编辑稿保留为 Markdown，语文、英语文本可用 `docx <Markdown> <Word>` 转换。
