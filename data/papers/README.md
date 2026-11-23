# 明文试卷

每卷一份 UTF-8 JSON，放在 `data/papers/<subject>/<paper-id>.json`。当前私有研发分支直接读取 Git 中的试卷，不需要恢复密钥。可选的本地使用目录 `.local-data/papers/` 仍接受同一格式。资料仅用于个人学习与教研归档。

顶层包含 `id`、`subject`、`year`、`title`、`series_id`、`regions`、`exam_kind`、`question_count`、`points`、`source`、`questions`。题面引用的完整阅读材料放在 `passages`。英语附 `listening_transcript`，单独笔试资料标 `written_only`。每题包含原题号 `number`、`kind`、`points`、`stem`、`answer`、`position` 或 `page`，可追加 `options`、`parts`、`explanation`、`topic`、`features`、`rubric`、`passage` 与 `images`。影响判题的分歧标 `conflict_severity: material`。

运行 `import-electronic <json> [--markdown <md>] [--images <dir>]`。Markdown 逐题用 `## 题号` 与 `### 答案`。图件使用轻量 PNG/JPEG。添加 `--track` 录入当前私有研发分支，提供 `source.title` 和 `source.url`，导入器会记录归档用途。带 `written_only: true` 的英语卷按笔试范围验收。练习级可用与原页严格复核分别记录。


命题画像位于 `data/dna/`。运行 `python scripts/gaokao_platform.py dna <subject>` 按现有语料重算。演练卷使用 `research --adaptation` 独立检索。
