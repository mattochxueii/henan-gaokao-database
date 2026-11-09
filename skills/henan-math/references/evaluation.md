# 参考与留出对照

已核验题面和独立重解进入可分组范围。试卷、共享主记录、已知等价和改编候选建立连通分组。指定留出卷后，组内其他卷一同留出。分割固定到题目 ID、题面版本和分组哈希。

```sh
python scripts/math_skill.py study-split --holdout-paper <卷ID> --output <分组.json>
python scripts/math_skill.py study-packet --evaluation-split <分组.json> --topic 数列 --topic 导数 --output <命题参考.json>
python scripts/math_skill.py generate --engine ai --evaluation-split <分组.json> --candidates <候选.json> --output <新目录>
```

创作前只读命题参考包与参考分区合法题面。将分组哈希写到候选根字段 `evaluation_split_sha256`。逐题引用参考分区的版本。参考包省略留出正文、解析与逐题分析。分组过期和留出题引用均会阻断生成。含外部服务的模式继续禁止把本地历史题面发给外部模型。

先冻结候选及其参考包哈希，再读留出题。给独立对照者随机左右顺序的纯考生材料，另存来源映射。记录考查能力、条件结构、关键推理、读题负担、分值、正确性和相似程度。已知同源排除只是运行时防泄漏，预训练或宿主既往接触无法判定。主观评审与真实作答统计分开。

启用留出协议的发布记录对未完整程序覆盖的题，逐题保留 `argument_audit` 中的 `scope`、`necessity`、`sufficiency`、`boundaries`、`equality`、`school_solution`。不适用项记录具体理由。
