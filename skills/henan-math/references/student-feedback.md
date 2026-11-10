# 匿名试做与作答反馈

试做材料分为考前学生包和作答后评分包。先独立作答并记录各题用时、未完成项、题意困难或歧义，保存答案后再看解析并自评。按同一卷号、版本、题号和 PDF 校验值汇总。需要可靠的历史题特征时，参见 [独立盲标基准](../../../forecast/benchmark/README.md)。研究标注与作答反馈分开保存。

```sh
python scripts/trial_kit.py <已审核150分试卷目录> work/试做包
python scripts/student_feedback.py <试卷目录> blank-csv .feedback/空表.csv --extended
python scripts/student_feedback.py <试卷目录> prepare .feedback/已填表.csv .feedback/round1.json
python scripts/student_feedback.py <试卷目录> summary .feedback/round1.json --min-sample 10
```

- 保存空表副本，保留前四个绑定列。每位参与者自用一个随机代码。未记录的题保持反馈列空白，做了但未完成的题填写 `unfinished` 和观察到的秒数，可填已获部分分。
- `status` 用 `correct`、`partial`、`incorrect` 或 `unfinished`。错误类型以 `|` 分隔，可选 `concept`、`model`、`calculation`、`logic`、`reading`、`time`、`other`。自由文本只写解题思路。
- `reading_difficulty` 为0到3，从无困难到严重。可填 `ambiguity_reported` 的0或1。看过解析后，`explanation_clarity` 可填0到3，从看不懂到能独立复述。姓名、学校和联系方式均省略。
- 扩展表可填评分疑点 `scoring_issue` 的0或1，以及推理负担 `reasoning_load`、计算负担 `calculation_load` 的0到3。输入兼容旧 CSV 和 UTF-8 JSONL。填过的记录只保存在私有 `.feedback/`。

汇总给出满分人数、得分比例、未完成人数、时间中位数、错误类型、题意困难、歧义与解析理解。至少10位有效作答者时才提示复查难度，低于10位只作个人或小样本记录。提示根据实际提交计算，不会覆写编辑分值，也不代表正式难度标定。

## 个人试做

按解析册中的项目自拟评分细则逐题记分。空行表示尚未录入；已看题但未做完时填 `unfinished` 并登记已用时间与实际得分。

```powershell
python scripts/student_feedback.py <试卷目录> diagnose <已导入记录.json> <匿名代码>
```

个人诊断显示各题的得分、用时、与编辑估时的差值、错误分类、题意反馈和解析理解，并按模块汇总观察值。未录题单独统计，个人结果用于学习复盘。群体汇总同时标记样本量和小样本状态。
