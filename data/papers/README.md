# 明文试卷

每卷一份 UTF-8 JSON，放在 `data/papers/<subject>/<paper-id>.json`。只有本地使用依据的资料放在 `.local-data/papers/`。两处使用同一个读取器。资料仅用于个人学习与教研参考。

顶层包含 `id`、`subject`、`year`、`title`、`series_id`、`regions`、`exam_kind`、`question_count`、`points`、`source`、`questions`。题面引用的完整阅读材料放在 `passages`。英语附 `listening_transcript`，单独笔试资料标 `written_only`。每题包含原题号 `number`、`kind`、`points`、`stem`、`answer`、`position` 或 `page`，可追加 `options`、`parts`、`explanation`、`topic`、`features`、`rubric`、`passage` 与 `images`。影响判题的分歧标 `conflict_severity: material`。

运行 `import-electronic <json> [--markdown <md>] [--images <dir>]`。Markdown 逐题用 `## 题号` 与 `### 答案`。图件使用轻量 PNG/JPEG。可公开分发的资料可加 `--track`，并提供 `source.license_url` 和 `source.public_reuse`，逐项说明题目、阅读材料、答案及图件的依据。
