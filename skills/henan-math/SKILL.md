---
name: henan-math
description: 检索河南2025—2026数学候选真题、研究知识点和命题特点、生成原创专项或河南高考风格模拟卷，并独立求解、校验和导出PDF。用于数列、导数及高中数学命题请求，需要已恢复的henan-gaokao-database。
---

# 河南数学真题研究与命题

使用本技能时，先告知正在使用 henan-math。默认用中文执行，直接完成可运行的研究、命题、求解和交付流程。

## 数据定位

运行本技能目录中的 scripts/run.py。它依次读取显式 --database、环境变量 HENAN_MATH_DB、安装时的相对配置、当前目录的父目录和技能位置的父目录。定位失败时报告真实路径问题。

数据库必须含 database.json、analysis/rules.json 和已恢复的私有题面。恢复命令见 references/storage.md。遇到私有数据缺失时可继续检查安装与规则，但完整题面研究依赖用户持有的恢复密钥。

## 真题研究

先运行 research。按知识点、年份或题型过滤，读取返回的实际 candidate、curation、analysis 和 original_independent_solution。

```powershell
python <技能目录>/scripts/run.py research --topic 数列
python <技能目录>/scripts/run.py research --year 2026 --kind constructed_response
```

解释时附题目ID、候选版本、页码、分析依据。遇到版本冲突逐版解释，使用 curation.answer_for_current_candidate，原始解答作为历史记录保留。所有候选均未获命题机构逐题确认，AI视觉审阅也须单列。

## 原创专项

支持的知识模块、题目族及验证覆盖见 references/coverage.md。先研究相关候选，再选择不同的条件结构与推理任务。原创性检查覆盖当前38题及同卷题目，外部重复仍需教师审查。

```powershell
python <技能目录>/scripts/run.py generate --topic 数列 --count 2 --kind constructed_response --output <新输出目录>
python <技能目录>/scripts/run.py generate --topic 导数 --count 1 --difficulty 4 --output <新输出目录>
```

当前执行引擎使用运行时参数化的受支持题目族。宿主AI负责研究、设计与推理复核。远程模型调用预算为0，新增自由题面需要先扩展规范、独立求解器和测试。超出覆盖时如实报告，避免将未验证题面放入已通过试卷。

## 完整模拟

遇到“生成一套河南2027年高考风格数学模拟卷”，先运行 rules，检查目标年份和规则类别，再运行 full。若官方结构更新，先更新有证据的规则再出卷。

```powershell
python <技能目录>/scripts/run.py rules
python <技能目录>/scripts/run.py generate --mode full --seed 20261110 --output <新输出目录>
```

150分结构采用历史两套候选的8单选、3多选、3填空和5解答。2027详细结构仍为模拟设定。多选部分得分按卷头约定。知识点分布和难度按本次蓝图设计，两套样本的观察须标样本量。

## 独立验证和修订

生成入口自动调用独立求解模块。求解模块只接收题目族与数学参数，重新求值并记录步骤，接着检查答案、选项个数、可解性、规范题面、重复度、题量和分值。

若门槛失败，自动换新草稿，最多3次。每次均保存新ID、题面校验值和求解记录。修改题面或参数后必须重新验证，旧验证会因校验值不匹配失效。

```powershell
python <技能目录>/scripts/run.py verify <输出目录>/run.json
```

程序验证与文字证明分开报告。逐步检查全域、边界、取等条件、唯一性及量词。含不等式、全域分类、存在性等证明的题目保留 reasoning_review 状态，明确剩余不确定性。教师盲审与实测难度仍是独立环节。

## 输出和交付

默认生成 paper.pdf、solutions.pdf、可编辑Markdown、图像及run.json。答案册包含结果、完整步骤、知识模块、设计难度、程序验证状态与质量边界。PDF输出后须渲染逐页检查公式、图像和分页，再交付。

本环境Word渲染工具未就绪。可编辑源为Markdown和结构化JSON。安装说明包含配置字体的办法。

## 验收流程

当用户说“检索河南2025—2026年高考数学真题，分析数列命题特点，然后生成5道原创数列题，独立验证答案并输出完整解析”，依次执行研究、读取规则、sequence生成、verify和PDF页面检查。总结S4/S8块和、递推-导数综合、局部九项等比存在性的异同，并注明来源版本。

```powershell
python <技能目录>/scripts/run.py research --topic 数列
python <技能目录>/scripts/run.py rules
python <技能目录>/scripts/run.py generate --mode sequence --seed 20261107 --output <新输出目录>
python <技能目录>/scripts/run.py verify <新输出目录>/run.json
```

报告实际题量、状态、文件路径、失败及修复记录。关于许可与备份、机制与覆盖、命令故障分别查阅references中的文件。
