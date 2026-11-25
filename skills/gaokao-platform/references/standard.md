# 标准卷约束与分块格式

先读取同版本的真题上下文和 `exam-policy <学科> <年份>`。年份以生成命令为准。全国卷 2026 年起听力两节都播放两遍，河南外语 2027 年起按听力与笔试合计。数学与物理多选给分分别取政策表。由版式程序统一印说明，听力材料只写第几段对应哪些题。项目根目录的 `data/exam-policy.json` 记录来源和生效范围。

## 数理化生

- 数学须覆盖指对数超越函数、导数工具、立几选填及均值外的统计量。补集用 `\complement_U A`，对立事件用 `\overline{Y}`。立体几何大题用三维示意图。图文中同时标明关键点、量值、方程或必要部件。
- 物理题的 `physics_module` 只能取一个主考模块。力学组为 `mechanics`、`astronomy`，电磁组为 `electrostatics_circuits`、`magnetic_force`、`induction_ac`，其余为 `thermodynamics`、`optics_waves`、`atomic`。每题分值只计一次。三组分别须为 35–46、38–50、12–20 分，热学最多 12 分。第 13–15 题内有一题电磁计算、有一题含连续推理的力学综合。八类主干及典型器具上限仍需复核。
- 涉及 π 的数值空，如指定精度，提供 `"pi_checks":[{"blank":"①","expression":"4*pi**2/4.00"}]`。使用实际题面量，表达式支持数字、pi、四则、整数幂、平方根。程序用 3.14 与 3.1416 分别计算并检查进位和候选答案。已给出拟合斜率的单摆求重力题可由程序提取斜率。物理 11–12 题嵌入填空、13–15 题保留演算，11–15 题均配有实质信息的图。
- 化学 15–18 题须配图，每题设 4–12 个嵌入填空。前五题覆盖 STSE 和基础实验操作。选必2至少两题，至少一题涉及晶胞之外的原子或成键。离子反应兼顾目标 pH、竞争反应、先后次序和物料收支。
- 生物 17–21 题保留题内答位，至少三题有可核图件。实验对照与结论分别说明，长句答案分步骤给分。
- 用连续三个或更多的下划线表示答位。题图有实验读数、过程或空间关系才用于检验。自绘图用 `save_figure(fig,path,subject=...)` 查标签重叠与中文标注。保留规范物理量和计量单位。长答留白服从实际书写需要，学科程序覆盖和独立求解分别登记。

## 三段候选格式

每个片段为一个 JSON 对象，包含 `protocol: "gaokao-language-part-v1"`、`part: "part1"|"part2"|"part3"`、`subject`、`paper_id`、`reference_notes`、`questions` 和 `materials`。只有 part1 填公共 `title`。按蓝图填写 `number`、`section`、`points`、`kind`、`stem`、`answer`、适用的 `options` 和片段内 `material`。题目 ID 形如 `orig:english:<paper_id>:q21`。每段的材料 ID 全卷唯一，各题引用自己的材料。英语 part1 填 `listening` 字典，以十组材料 ID 为键，值为单遍原稿。合卷按题序整理播放顺序并保存各片段的哈希。

### 语文

part1 为 `information/literary`，part2 为 `classical/poetry/recitation`，part3 为 `language/essay`。按独立材料正文的汉字数计量，信息类 1600–2100，文学类 1600–2300，文言 520–750。第 12、15 题问“不正确的一项”。文言选陌生材料，保留来源与必要注释。正文与选项一级引用用中文双引号。第 17 题按三条小题顺序填写 `recitation_sources`，每条有 `author`、`title`，作者及篇目不得重复。

### 英语

part1 为 `listening`，part2 为 `reading/gap_match`，part3 为 `cloze/grammar/application/continuation`。A–D 四篇正文共 1380–1650 词，C、D 各自平均句长至少 17 词。保持自然论证和不同体裁。钟点用 10:45 一类写法。一级引用用双引号，普通缩写与所有格保留撇号。优先使用全国卷常见美式拼写。

语填材料用 `[56] ____ (carry)` 一类唯一编号的实际空位。第 56–65 题逐空填 `grammar_tag`，如 `{"category":"nonfinite","form":"ing"}`。至少五个类别，含 `finite`、`nonfinite`、`conversion` 和 `clause`。非谓语至少两种形态，每个细类最多两空。谓语可标 `tense/passive/agreement/modal`，非谓语用 `infinitive/ing/past_participle`，词性转换用 `noun/adjective/adverb/verb`，从句用 `relative/nominal/adverbial`。其余标签见项目中的 `scripts/core/language_corridor.py`。独立审题另核语法功能、语境与答案唯一性。

合卷检查范围为题号分值、材料引用、语篇体量、语法与课标格式。课程难度、文章质量、可替代答案和图文信息由独立审稿和最终 PDF 核验。
