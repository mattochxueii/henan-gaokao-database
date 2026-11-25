# HN14-P40-v1 学生试做

作答前发放 `paper.pdf` 和 `feedback-blank.csv`。建议限时 32 分钟，满分 40 分。自行计时或按题记录，交卷后再提供 `solutions.pdf` 与项目分步评分。等效、物理上成立的解法按相应步骤得分。试做处于待实测状态。

CSV 每题一行。保留预填题号、题目 ID 与试卷哈希。参与者使用自选的 4 至 32 位字母、数字、下划线或中划线代码，不填姓名、学校等信息。完全空白的作答行表示未录入。开始记录某题后，填写用时秒数、得分、状态与阅读困难程度 0 至 3。状态可填 `correct`、`partial`、`incorrect`、`unfinished`。错误类型可用竖线连接 `concept`、`model`、`calculation`、`logic`、`reading`、`time`、`other`，也可留空。方法和困难填在 `method_note`。扩展列按需要填写，歧义与评分问题用 0 或 1。

```sh
python scripts/student_feedback.py experiments/phase14/physics prepare .feedback/session.csv .feedback/session.json
python scripts/student_feedback.py experiments/phase14/physics diagnose .feedback/session.json YOUR_CODE
```

代码按试卷 PDF 校验值验证记录。个人诊断按题展示得分、用时、与编辑估时的差值和错误类型。小样本不能据此推断群体难度。匿名记录存于本地 Git 忽略目录。
