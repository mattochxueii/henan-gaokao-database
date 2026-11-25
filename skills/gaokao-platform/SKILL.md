---
name: gaokao-platform
description: 本仓库唯一官方六科命题入口。使用高考真题研究、拼卷、改编或专项训练，按目标年份模拟整卷，分块创作语英，批量避免模型重复，组织本地和外部盲审。
---

# 高考真题研究与模拟命题

直接说你想练什么，例如“用 gaokao-platform 抽五道数列真题”或“出一套 2027 河南新高考物理卷，自印版，学生卷和答案分开”。先确定学科、年份和用途，再按下方流程执行。

单次会话或单轮任务只命制一个学科的一套试卷。返工保持同一个卷 ID。批量任务只能指定一个学科，每套独立安检、盲审和发布。

在仓库根目录使用 `python scripts/gaokao_platform.py`。用 `python scripts/install_skill.py` 安装到项目的 `.agents/skills/gaokao-platform`，或用 `--destination <宿主技能目录>` 指定其他宿主。安装后用 `scripts/run.py` 转发同一套命令，也可用 `--database <项目根目录>` 定位真题库。

## 单卷

1. 用 `authoring-context <学科> --limit 100 --output context.json` 读取真实题面、命题画像及两年同题位依据。用 `exam-policy <学科> <年份>` 取卷头、计分与听力规则，语英、理科用 `plan <学科> <年份> --mode standard` 取标准蓝图。
2. 创作独立于参考原题的新推理任务，写明同题位深度、错项误区和图件提供的条件。数学分离内部规格与中文题面，理科使用 `program` 或 `independent_review` 通道。物理逐题声明主考模块，语文默写逐小题登记作者和作品，英语语填逐空标考点。阅读 [标准卷约束与分块格式](references/standard.md)。
3. 运行 `simulate <学科> <年份> <候选.json> <新目录> --context context.json`。默认 `exam` 按紧凑考场版排印。用 `--layout-mode practice` 给语英文字长答印书写横线，给语文作文印千格稿纸，数学、物理演算及化学结构式或路线使用纯空白。化学需要附加演算区时在该非选择题登记 `response_area: calculation`。命题会话沿用同一任务凭据，普通终端可用 `--session <凭据.json>` 显式绑定。政策说明由程序排印。纯嵌入式填空使用题内横线。
4. 用 `exam-qa <卷目录>` 查硬门禁，再执行 `board-cycle <卷目录> <分离审稿邮箱>`。三角色各自只看白名单材料并提交八维回执。教研角色另提交中等生和尖子生分块分钟数及把关题证据。语数英尖子生估时最低95分钟，理化生最低55分钟。估时属于编辑判断。普通对外状态为 `LOCAL_QA_PASSED`，逐笔扣分保留在本地评分卡。题位失败则锁定其余题目，另存新目录修订。
5. 用最终学生 PDF 做独立重解，完成 [逐题质量审稿](references/quality-audit.md) 和视觉签核。语英、理科使用 `review <卷目录> <核对.json>` 和 `publish <卷目录> <逐页复核.json>`。数学用 `math publish <卷目录> --student-review <核对.json> --math-comparison <数学核对.json>`。学生卷、答案、英语朗读稿分开；`docx <Markdown> <Word>` 导出文字版。

评分模板由程序生成。语文第9、10、17、22题、英语第66、67题的审查回执保留解析与范文。数学逐题填 `math_technique`，物理实验逐题填 `experiment_archetype`。中文题面用 `<dot>`、`<wave>` 标记文言文字。科学数据表用 `table: {headers, rows, caption}`。化学注明 `relative_atomic_masses`。在 `ledger_topics` 中登记主题、实验、压轴、诗文篇目或英语材料词。发布更新 `data/ledger/`，新卷上下文读取台账。语文默写核对 `data/corpus/chinese/` 中的整理本。英语输出 `listening-tts.txt`。新版英语 PDF 需要本机 Times New Roman，可用 `GAOKAO_TIMES_NEW_ROMAN` 配置字体。

## 语文、英语分块

三个独立创作任务共用同一目标年份、卷 ID 和真题上下文。语文分现代文双阅读、文言古诗默写、语用作文。英语分十段听力、阅读与七选五、完形语填写作。用 `merge-sections <chinese|english> <年份> <候选.json> <part1.json> <part2.json> <part3.json> --context context.json` 校验合并，再进入单卷流程。材料与答案按题号在片段内配对。

## 批量

用 `batch-plan <学科> plan.json --count N` 预留互斥的实验、情境和压轴模型。物理各卷独立达到三大板块分值范围，再在同板块换模型。用 `batch-check` 比较实际候选，可用 `batch-run plan.json <年份> context.json <工作目录>` 恢复批量生产。各轮仍执行单卷安检与独立审阅。文件布局及修订约定见 [批量与盲审](references/batch.md)。

## 外部盲审

用 `export-external-review <卷目录> <新目录>` 生成学生 PDF、Markdown、政策表、两年题位摘要、提示词和回执模板。英语另有只供播放的朗读文本。外部模型使用导出目录材料独立挑错。收到 JSON 后运行 `import-external-review <卷目录> <回执.json>`，查看承接题号并从新的试卷目录用 `board-cycle <修订卷目录> <新邮箱> --previous <原卷目录>` 复核。模型身份、PDF、缺陷证据与修订均需绑定版本。

## 真题与专项

- `research <学科> --region 河南 --year <年份> [--topic <主题>]` 查题面、版本与来源。演练卷加 `--adaptation`，排查缺图或隔离加 `--include-incomplete`。
- `assemble <学科> <新目录> [--year <年份>]` 拼卷，`train <学科> <新目录> --topic <弱项>` 抽题训练。带材料题按组输出，完成独立核对后用 `workbook-review` 生成分离答案。
- 用 `authoring-context <学科> --source-id <原题ID> --output <对照.json>` 研究同构改编，再运行 `adapt <学科> <改编候选.json> <新目录>`。保留核心推理，实质改变条件、情境或设问。[改编与核对](references/practice.md)
- 数学趋势专题只在明确需要时使用 `trend-pack`，逐题绑定冻结证据与题位。正式标准卷按目标蓝图、真题和 DNA 创作。趋势卡在项目根目录的 `forecast/preregistered/2027-math-trends.md`。

真题导入用 `import-electronic <试卷.json> --images <题图目录> --track`。理科必要图缺失时保留文字并登记单题缺图。导入后用 `python scripts/audit_core_papers.py --write-profiles` 更新画像。
