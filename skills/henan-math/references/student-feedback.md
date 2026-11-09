# 匿名作答反馈

反馈写入个人受控的 `.feedback/`，以同一份已审试卷的 PDF 哈希绑定。记录前由组织者分配随机代码。参与者代码之外，姓名、联系方式、学校等身份信息均省略。自由文本只写解题过程要点。

输入为 UTF-8 JSONL，每行一人一题。字段为 `participant_code`、`paper_sha256`、`question_id`、`seconds`、`score`、`status`、`error_types`、`reading_difficulty`、`method_note`。题目 ID 和满分可从试卷的 `student-text.json` 读取，PDF 哈希见 `publication.json`。

作答状态用 `correct`、`partial`、`incorrect` 或 `unfinished`，错误标签可选 `concept`、`model`、`calculation`、`logic`、`reading`、`time`、`other`。题意困难用 0 至 3 表示从无困难到严重。未完成可以给已做部分的分值，时间为已观察的作答秒数。

```sh
python scripts/student_feedback.py <试卷目录> prepare <原始记录.jsonl> .feedback/round1.json
python scripts/student_feedback.py <试卷目录> summary .feedback/round1.json --min-sample 10
```

汇总给出满分人数、得分率、未完成人数、时间中位数、错误次数和题意困难中位数。至少10人时才提示是否复查难度。样本来源、参与者覆盖与实际条件需要记录。复查提示供人工决定是否调整难度，不会覆写编辑分值。空记录返回0条，不生成实测难度。
