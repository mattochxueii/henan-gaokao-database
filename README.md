# 河南新高考真题库与 AI 命题 Skill

这里收录六门学科共 48 卷、1,297 道结构化试题。AI 可以查真题、拼练习、改编题目或命制原创模拟卷。程序检查考制、评分和排版，分别输出学生卷和答案。

## 仓库和 Skill 怎么配合

仓库是真题弹药库、代码安检机和印刷排版器。唯一的 Skill [gaokao-platform](skills/gaokao-platform/SKILL.md) 是 AI 助手的操作手册。装好后，在助手里用中文说你想练什么。

## 真题库

| 学科 | 试卷 | 试题 |
| --- | ---: | ---: |
| 语文 | 8 | 183 |
| 数学 | 23 | 496 |
| 英语 | 8 | 456 |
| 物理 | 3 | 45 |
| 化学 | 3 | 54 |
| 生物学 | 3 | 63 |
| 合计 | **48** | **1,297** |

[data/papers/](data/papers/) 用 JSON 存题，另有 240 个题图。部分试卷含适应性演练，缺图或版本争议会逐题标明。比如把 2024 年新高考Ⅰ卷数学可用题导出为 PDF：

~~~bash
python scripts/gaokao_platform.py assemble math output/math-2024 --paper-id 2024-cn-math-new-gaokao-1 --limit 100
~~~

## 三步上手

1. 运行 **git clone https://github.com/mattochxueii/henan-gaokao-database.git**，再进入 **henan-gaokao-database**。
2. Windows 运行 **.\install.ps1**。macOS / Linux 依次运行 **python3 -m pip install -r requirements.txt** 和 **python3 scripts/install_skill.py**。
3. 在 Codex、Claude Code、Gemini CLI 或 Antigravity 中打开项目，说：“请用 gaokao-platform 为我命制一套 2027 年河南新高考物理模拟卷。”

每轮命制一个学科的一套卷。程序检查卷型、评分模板和学科门禁，独立复核再检查题意和答案。高水平推理模型更擅长原创命题和独立求解。可用 **export-external-review** 将学生卷交给另一模型复核，再导入意见返工。

默认 **exam** 为考场版。选 **practice** 可直接打印刷题，语英文字题有书写横线，语文作文有千格稿纸，数理化演算区留白。详见[中文教程](docs/TUTORIAL.md)。

仅供个人学习与教研参考，不作高考押题承诺。
