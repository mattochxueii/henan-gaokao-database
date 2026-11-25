# 中文使用教程

## 安装

先装 Python 3.11 或更新版本。克隆仓库后，在项目根目录运行：

~~~powershell
.\install.ps1
~~~

Windows 默认从清华镜像安装。镜像超时时运行 **.\install.ps1 -OfficialPyPI**。macOS 或 Linux 运行：

~~~bash
python3 -m pip install -r requirements.txt
python3 scripts/install_skill.py
~~~

Codex 在项目目录可读取默认安装的 **.agents/skills/gaokao-platform**。Claude Code 可用 **python scripts/install_skill.py --destination .claude/skills**，Gemini CLI 可指定 **.gemini/skills**。Antigravity 等宿主用 **--destination** 指定它实际扫描的技能目录。若宿主版本无法自动识别，在对话中让助手先读取 **skills/gaokao-platform/SKILL.md**。移动仓库后重新运行安装。

## 一句话出卷

“用 gaokao-platform 给我出一套 2027 河南新高考数学卷，考场版，学生卷与答案分开，按流程做完盲审。”

助手会读取目标年份政策和真题依据，创作、安检、独立求解，再排印和送审。每轮只命制一个学科。日常练习也可以直接用命令：

~~~bash
python scripts/gaokao_platform.py assemble math output/math-2024 --paper-id 2024-cn-math-new-gaokao-1 --limit 100
python scripts/gaokao_platform.py train math output/sequence --topic 数列 --limit 5
python scripts/gaokao_platform.py adapt english candidate.json output/english-adapt
python scripts/math_trends.py
~~~

**assemble** 可按年份、卷 ID、题型或知识点抽题。**train** 选弱项。**adapt** 需要绑定一道原题的原创候选，通常由助手准备。拼卷先生成学生 PDF 和答案数据，经 **workbook-review** 独立核对再生成解析。**math_trends.py** 核验冻结卡的版本，取得考后逐题证据后可传 **--score**。

## 选择排版

- **exam** 为默认考场版，配答题卡。
- **practice** 为自印版。语文和英语的文字长答配书写横线，语文作文配带字数标尺的千格稿纸。数理化的推导、画图和结构式使用纯空白区。题内填空就地作答。

出卷时传 **--layout-mode practice**。版式改变后重新检查实际 PDF。

## 英语听力

英语卷独立输出朗读稿和 **listening-tts.txt**。将纯文本交给配音工具，按 **M:**、**W:** 分配声音，再按朗读稿中的目标年度规则拼接重复和停顿。作答前只发学生卷，朗读稿留给播放端。

## 外部盲审与排雷库

~~~bash
python scripts/gaokao_platform.py export-external-review output/paper output/blind
python scripts/gaokao_platform.py import-external-review output/paper external-findings.json
~~~

把 **output/blind** 给另一模型，让它按模板返回逐题缺陷 JSON。导入后沿用原卷 ID，修订对应题位，再启动 **board-cycle**。同科批处理先用 **batch-plan**，随后由 **batch-run** 逐卷核验。

新问题可在 **data/qa/anti-patterns.json** 的 **entries** 中加一项。写明唯一 **id**、学科 **subject**、严重度 **fatal** 或 **major**、检查要点 **check** 及反例 **counterexample**。规则自动进入创作与盲审上下文。需要机器阻断的规则还需写校验代码和测试。

## 模型选择与 10 秒验货

### 按任务选模型

- 对标联考的原创整卷，选能完整调用工具的强推理编码 Agent，再用 `export-external-review` 交给另一家族的模型盲审，针对具体题位返工。
- 一轮基础过关卷可由常规强模型完成。下表的单模型样卷外审查出了难度偏低，未发现 P0。
- 轻量或免费快速模型建议用于 `research` 查题、`assemble` 拼真题和 `train` 做专项练习。

### 三次数学整卷外审记录

以下是三份实测样卷的异构模型外审记录。六个维度均为 10 分制，P0 指必须修复的缺陷。作答时间为审稿估时。

| 实测模型与版式 | 实际流程 | 均分 | 科学 / 政策 / 评分 / 质感 / 排版 / 难度 | P0、估时与卷子定位 |
| --- | --- | ---: | --- | --- |
| 豆包免费版（3 分 15 秒出卷） | 跳过正式链路，调用旧 `template` | 2.9 / 10 | 4.0 / 3.5 / 3.0 / 2.0 / 3.0 / 2.0 | 6 处 P0。尖子生约 29–37 分钟。有超纲词、符号冲突、压轴偏浅和乱码，不可用于实考。 |
| Qwen4-Max（`exam`） | 完整跑通原创链路 | 7.1 / 10 | 9.0 / 9.0 / 8.5 / 6.0 / 6.0 / 4.0 | 0 P0。尖子生约 42–52 分钟。外审未发现错题，适合一轮基础过关。 |
| Gemini 4 Neon XHigh（`practice`） | 完整跑通原创链路，完成 3 轮隔离盲审 | 7.2 / 10 | 9.0 / 7.5 / 7.5 / 6.5 / 6.5 / 6.0 | 0 P0。尖子生约 74–95 分钟，中等生约 116–133 分钟。作答节奏更接近限时训练，压轴有原创亮点，可再做一轮异构外审，重点复核压轴题位。 |

只说“出一套数学卷子”，助手可能会用 `assemble` 拼历年真题。要新题，明确说“按 Skill 原创模拟整卷”。

### 10 秒验货

1. **看卷头和页脚。** 出现“template模板备用模式”“研究审阅版”或“审阅用”，退回。
2. **看答案卷。** 出现 `programmatically_verified` 之类的工程状态，或解答题缺分步评分细则，退回。
3. **看运行记录。** 确认有 `simulate → exam-qa → board-cycle → publish` 的实际产物。几分钟交卷时先查记录，缺环节或用真题导出代替原创就退回。

> 请严格按 `skills/gaokao-platform/SKILL.md` 命制一套原创模拟卷，依次完成 `authoring-context → simulate → exam-qa → board-cycle → publish` 并交付核验记录。禁止使用 `template`，禁止用 `assemble` 或 `train` 代替原创整卷。

## 常见问题

| 现象 | 处理 |
| --- | --- |
| 找不到 Python 或版本太旧 | 安装 Python 3.11+。Windows 安装时勾选加入 PATH，再重开终端。 |
| 依赖下载超时 | Windows 用 **.\install.ps1 -OfficialPyPI**，其余系统用可访问的 PyPI 源。 |
| 英语正式卷缺 Times New Roman | 将环境变量 **GAOKAO_TIMES_NEW_ROMAN** 设为本机合法字体的实际 **times.ttf** 文件。 |
| 助手没有加载 Skill | 检查安装位置并重开项目，或让助手先读取仓库的 **SKILL.md**。 |
| 安检或盲审未通过 | 看具体题号和规则，修题或改版后另存目录，再走核验。 |
| 卷头写模板备用，或几分钟交卷却没有核验记录 | 退回，要求按 Skill 重跑原创与盲审流程，或换能完整执行流程的强推理模型。 |
| 某套真题导出少题 | 查源记录。缺图、隔离或不完整的题会从练习卷排除。 |
