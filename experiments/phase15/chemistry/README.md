# HN15-C40-v1 化学专题试做

建议 35 分钟，满分 40 分。作答前只发放学生卷 `paper.pdf` 及匿名记录表 `feedback-blank.csv`。交卷后给出 `solutions.pdf`，按项目分步评分参考自评。评分应接受科学上等价的解法。本卷使用课内理论和纸面模拟数据。

匿名代码使用 4 至 32 位字母、数字、下划线或短横线。不要收集姓名和学校等资料。保留 CSV 的题号、题目 ID 与哈希。记录每题用时秒数、得分、阅读困难 0 至 3、作答状态与错误类型。整行反馈为空视为该题未录入。状态可填 `correct`、`partial`、`incorrect`、`unfinished`。错误可填 `concept`、`model`、`calculation`、`logic`、`reading`、`time`、`other`，用竖线连接。

```sh
python scripts/student_feedback.py experiments/phase15/chemistry prepare .feedback/trial.csv .feedback/trial.json
python scripts/student_feedback.py experiments/phase15/chemistry diagnose .feedback/trial.json YOUR_CODE
```

个人诊断可定位用时和理解困难。教师审阅和真实试做分别登记，当前处于待实测状态。
