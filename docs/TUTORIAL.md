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

## 常见问题

| 现象 | 处理 |
| --- | --- |
| 找不到 Python 或版本太旧 | 安装 Python 3.11+。Windows 安装时勾选加入 PATH，再重开终端。 |
| 依赖下载超时 | Windows 用 **.\install.ps1 -OfficialPyPI**，其余系统用可访问的 PyPI 源。 |
| 英语正式卷缺 Times New Roman | 将环境变量 **GAOKAO_TIMES_NEW_ROMAN** 设为本机合法字体的实际 **times.ttf** 文件。 |
| 助手没有加载 Skill | 检查安装位置并重开项目，或让助手先读取仓库的 **SKILL.md**。 |
| 安检或盲审未通过 | 看具体题号和规则，修题或改版后另存目录，再走核验。 |
| 某套真题导出少题 | 查源记录。缺图、隔离或不完整的题会从练习卷排除。 |
