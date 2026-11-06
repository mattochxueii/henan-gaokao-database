# 河南新高考真题数据库 · 第一阶段

本地仓库，调查截至 2026-11-06。目录覆盖 2025、2026 年河南普通高考六科的 12 份正式主考卷。数学两卷各登记 19 个题号、题型、分值和候选页码，另有逐题独立推导。文件级保存许可尚未核实，完整数学卷面、正式参考答案和题图尚无本地登记。

## 快速开始

在仓库根目录运行。检索、登记和检查只需 Python 3.10 或以上版本。

```powershell
python scripts/cli.py query --year 2025 --subject 数学 --region cn-ha
python scripts/cli.py query --year 2026 --subject math --region cn-ha --number 17
python scripts/cli.py query --subject math --kind fill_in
python scripts/cli.py query --subject math --kind fill_in --complete-only
python scripts/cli.py report --region cn-ha --output reports/completeness.json
python scripts/cli.py validate
python -m unittest discover -s tests -v
```

第二条命令返回第 17 题的索引、候选页码和独立解答。索引的 `stem` 为 `null`。`--kind` 查询该题型的已登记条目，`--complete-only` 仅查询对照原卷人工核验并明确标为完整的题面。可用中文科目名或英文代码，题号查询使用原始题号字符串。

## 文件位置

- `metadata/sources.jsonl` 保存发布者、访问日期、网址、证据用途与权利状态。
- `metadata/papers/` 每卷一份 JSON，保存正式考试名称、卷型、命题主体、已核适用地区、候选来源、听力政策和版本差异。
- `metadata/files/` 每个实际导入的文件版本一份登记。原始路径、采集日期、文件格式、SHA-256、大小、许可和发布者身份保存在此。
- `originals/`、`answers/`、`assets/` 分别存放获准保存的试卷、答案解析、图像和听力资料。首次入库按年份、学科和试卷 ID 分类。
- `parsed/` 保存获准处理的 PDF 逐页原生文本。`questions/<year>/<subject>/<paper_id>.jsonl` 保存题号索引或经许可转写后的记录。
- `reports/` 保存逐卷完整性、候选排除、命令输出和后续技术建议。`tests/` 使用临时合成样本验证脚本。

JSON 与 JSONL 使用 UTF-8，是当前数据主档。首批体量很小，查询直接读主档，便于审阅和版本控制。后续可按需从主档重建 SQLite 索引。全国卷 ID 的地域段用 `cn`，河南省卷用 `cn-ha`。同一全国卷确认在另一省使用后，给现有记录追加已核地区和证据，避免重复创建试卷。河南记录的 `regions` 仅列本次核实的省份。

## 新增或补齐试卷

1. 核对年份、考试性质、命题主体、卷型和实际用卷地区。加入至少两个归属证据，其中至少一个为官方来源。把模拟卷、适应性考试、回忆版和其他省独立命题试卷放在候选或排除记录中。
2. 在 `metadata/sources.jsonl` 添加来源。参照现有试卷 JSON 填写新的清单，按 `<year>-<scope>-<subject>-<edition>` 命名。运行 `python scripts/cli.py register <清单.json>`。更新同一卷时，审阅并编辑现有清单，随后运行校验。
3. 核验文件对应的权利人、版本和使用范围。针对原卷、答案、解析、图片、音频分别保存权利依据。保存、派生处理和再分发分别记录，按授权条件执行。内容来源、站方下载条件和底层权利分开核实。
4. 将已经合规取得的本地文件登记。示例命令中的路径由维护者替换为真实文件和收据。系统按 SHA-256 去重，逐份保留独立授权记录。排版、扫描或答案版本不同且字节不同会独立留存。

```powershell
python scripts/cli.py import-file 2025-cn-math-national-1 <已获许可的卷面.pdf> --receipt <收据.json>
python scripts/cli.py extract-pdf <导入输出中的文件ID>
```

收据为 JSON，字段见 [登记与题目数据字典](metadata/data-dictionary.md)。导入会记录首次保存的路径。相同字节被其他试卷或资料角色合法引用时共用一个文件。导入中断后用同一输入重试，程序可复用已写好的文件。如果异常退出留下 `metadata/.intake.lock` 空目录，确认当前没有登记进程后清理空目录再重试。

PDF 提取命令使用可选的 Poppler `pdftotext`。结果按页保存并标记待校对。空白文本页交给获准的 OCR 流程，复杂公式和图像安排人工比对。当前环境未安装该工具，测试以模拟输出验证了逐页提取逻辑。

## 内容核验

- **已发现来源**：可以回溯到候选链接。已有题号索引也使用此状态。
- **已获取原始资料**：已登记一个具有本地保存许可的卷面版本。文件登记区分官方原卷、扫描、重排及第三方。
- **已解析**：已产出可定位原卷的结构化题干，公式与图表仍需核对。
- **已自动校验**：题号、顺序、字段、哈希、图片引用和已知分值通过检查。校验命令只报告结果，审核员可据记录更新条目状态。
- **已人工核验**：审核人对照合法原卷逐题检查并记录姓名或内部 ID、日期、说明。
- **存在问题**：归属之外的版本缺页、题干、答案、公式等差异应登记来源和处理意见。涉及本轮数学第 13、17、18 题的差异见报告。

原生提取先核对页码和顺序，再核对题号、分值、选项、子问、公式、图像和答题指示。原卷层保留原始符号，结构化层可另记 LaTeX 及原页位置。数学检查根号范围、上下标和不等式。物理检查单位、箭头、图示标号和实验装置连线。化学检查元素上下标、电荷、反应条件和方程式。生物学检查基因符号、实验对照、图例与比例尺。独立记录答案版本、解析版本与勘误。

## 资料报告与后续工作

- [逐卷完整性与核验报告](reports/completeness.md)
- [机器可读完整性报告](reports/completeness.json)
- [数学逐题核验报告](reports/math-completeness.md)
- [数学版本冲突报告](reports/math-version-conflicts.md)
- [数学资料补充清单](reports/math-intake-checklist.md)
- [数学实际查询输出](reports/math-retrieval.json)
- [登记与题目数据字典](metadata/data-dictionary.md)
- [下一阶段接入建议](reports/next-stage.md)

本地 Git 已初始化。版权敏感文件、登记收据和后续题干转写默认被忽略。新增纯题号索引时可逐个审阅并加入版本控制。正式备份应覆盖获准保存的本地文件与登记，并按权限区分访问。
