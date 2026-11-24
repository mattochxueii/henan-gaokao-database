# 河南新高考六科真题与 AI 命题平台

从真实试卷检索题目、研究命题方式，生成可打印的练习与模拟卷。统一入口支持六科拼卷、改编、专项与模拟；标准卷经过独立求解、同题位对照和逐页印刷审查。批量出卷另查实验题材、数学或物理模型及压轴设问的重复。数学趋势研究有单独的封存记录。

## 真题库与成品

题数按明文库实际保存的题目实例统计，包含适应性演练及部分材料缺失的题目。逐题来源、完整性与可用状态随题保存。打印时只向学生发放学生卷。

| 学科 | 收录卷数 | 题目实例 | 最新学生卷 | 答案与解析 |
|---|---:|---:|---|---|
| [语文](data/papers/chinese/) | 8 | 183 | [语文 150 分](experiments/phase26/chinese/final/paper.pdf) | [语文解析](experiments/phase26/chinese/final/solutions.pdf) |
| [数学](data/papers/math/) | 23 | 496 | [数学 150 分](experiments/phase23/math-standard/paper.pdf) | [数学解析](experiments/phase23/math-standard/solutions.pdf) |
| [英语](data/papers/english/) | 8 | 456 | [英语 150 分](experiments/phase26/english/final/paper.pdf) · [监考朗读稿](experiments/phase26/english/final/listening-script.pdf) | [英语解析](experiments/phase26/english/final/solutions.pdf) |
| [物理](data/papers/physics/) | 3 | 45 | [A 卷](experiments/phase25/physics-batch/phase26/A/final/paper.pdf) · [B 卷](experiments/phase25/physics-batch/phase26/B/final/paper.pdf) | [A 卷解析](experiments/phase25/physics-batch/phase26/A/final/solutions.pdf) · [B 卷解析](experiments/phase25/physics-batch/phase26/B/final/solutions.pdf) |
| [化学](data/papers/chemistry/) | 3 | 54 | [化学 100 分](experiments/phase22/chemistry/paper.pdf) | [化学解析](experiments/phase22/chemistry/solutions.pdf) |
| [生物学](data/papers/biology/) | 3 | 63 | [生物学 100 分](experiments/phase24/biology/paper.pdf) | [生物学解析](experiments/phase24/biology/solutions.pdf) |
| **合计** | **48** | **1,297** | | |

## 快速开始

使用 Python 3.11 或更高版本，在仓库根目录安装依赖。第一组命令可直接从已入库真题生成学生练习。输出目录使用新路径。

```sh
python -m pip install -r requirements.txt
python scripts/install_skill.py
python scripts/gaokao_platform.py assemble chinese work/reading --year 2024 --topic 信息类阅读 --limit 5
python scripts/gaokao_platform.py train english work/english-reading --year 2025 --topic 阅读理解 --limit 3
python scripts/math_trends.py
```

原创与改编需先由命题宿主按上下文撰写候选 JSON；求解、教研、印刷三个角色分别返回审稿文件。以下各行的输入文件名与对应输出目录可替换。

```sh
python scripts/gaokao_platform.py authoring-context physics --limit 100 --output context.json
python scripts/gaokao_platform.py exam-policy english 2027
python scripts/gaokao_platform.py simulate physics 2027 candidate.json work/simulation --context context.json --layout-mode practice
python scripts/gaokao_platform.py board-cycle work/simulation work/simulation-inbox
python scripts/gaokao_platform.py batch-plan physics plan.json --count 2
python scripts/gaokao_platform.py batch-run plan.json 2027 context.json work/batch
python scripts/gaokao_platform.py authoring-context english --source-id 2025-cn-english-national-1:q021 --output adaptation-context.json
python scripts/gaokao_platform.py adapt english adaptation.json work/adapted
```

标准模拟默认 `exam`，供另配答题卡。`--layout-mode practice` 在长答题后印书写横线，实验填空使用题内答位。单次任务限制一个学科的一套卷，批量仅限同一科。可向[排雷库](data/qa/anti-patterns.json)追加唯一编号、学科、严重度、检测要点与反例。详细操作见[统一命题入口](skills/gaokao-platform/SKILL.md)、[标准卷发布与红队验收](docs/STANDARD-RELEASE.md)和[完整开发历史](docs/DEVELOPMENT-HISTORY.md)。

语英分三段创作后用 `merge-sections` 合卷。按 `export-external-review` 生成可交给独立模型的学生材料，用 `import-external-review` 把缺陷绑定到原 PDF 和返工题号。[标准卷与分块格式](skills/gaokao-platform/references/standard.md)

本项目归档用于个人学习与教研。题目版本、来源及可用范围以各卷记录为准。模拟卷编辑评分与考生实测成绩分别记录。
