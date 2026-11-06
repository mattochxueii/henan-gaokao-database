# 登记与题目数据字典 · v1

## 试卷与来源

`sources.jsonl` 每行为一个来源，包含 `id`、`title`、`publisher`、`tier`、`url`、`accessed_on`、`access`、`rights_status` 和 `note`。其中 `evidence_only` 表示该链接只承担归属或说明证据用途，`underlying_permission_unverified` 表示未核实底层权利。`compilation_license_only` 表示声明的许可范围限于来源方拥有的整理权益。

每卷清单包括 `schema_version`、`id`、`year`、`subject`、`scope`、`edition`、`formal_title`、`title_basis`、`regions`、`authoring_body`、`regime`、`exam_kind`、`session`、`attribution_sources`、`identity_status`、`researched_on` 与 `materials`。题数未知用 `null`。文件夹和 ID 使用小写 ASCII 编码。`formal_title` 可为按正式考试制度整理的规范名，逐字核对状态见 `title_basis`。

`materials` 可用角色为 `paper`、`answer`、`explanation`、`image`、`listening_questions`、`listening_transcript`、`listening_audio`。`linked` 表示有候选，`partial` 表示有局部候选或完整性不明，`not_found` 表示本轮未定位适合该角色的候选。`files` 空数组表示尚无本地登记的对应文件。只有实际保存的文件才能生成文件路径和哈希。

## 文件收据

每个收据至少含以下字段。值由维护者根据实际授权填写。

- `role` 与 `source_id` 绑定资料类别和已登记的来源。
- `acquired_on` 使用 ISO 日期。
- `rights` 取 `licensed`、`public_domain` 或 `rightsholder_permission`。核对适用范围后再选。
- `rights_holder`、`evidence` 记录权利主体及许可文号、网址或可追溯的内部凭证。
- `allow_local_storage` 必须为 `true`。分别为 `allow_redistribution`、`allow_derivatives` 填布尔值。
- `variant` 取 `official_original`、`scan`、`retypeset`、`third_party` 或 `supporting_material`。
- 答案与解析需有 `authority`，取 `official` 或 `third_party`。官方身份须能回溯到官方发布。
- `coverage` 可填 `complete`、`partial` 或 `unknown`，省略时视为未知。`note` 可补充页码、附件和缺项。报告区分缺少本地文件和缺少完整版本。

导入后由程序附加 `id`、`paper_id`、`sha256`、`path`、`format`、`bytes`、`original_filename`。

## 试题 JSONL

- `id` 形如 `2025-cn-math-national-1:q006`。`paper_id`、`original_number`、`order` 分别记录归属、原始题号字符串和卷内顺序。大题的子问保留在题干、解析或后续可选的 `subquestions` 数组。
- `kind` 为题型，`stem`、`options`、`formulas` 分别保存题干、有序选项和符号表达。保存公式时建议用 LaTeX，另留原页锚点。图表和装置通过 `asset_refs` 指向同一试卷的已登记图像 ID。
- `points` 保存分值，未知用 `null`。`reference_answer` 和 `explanation` 可为 `null`，非空时需对应可派生的 `answer_file_id` 和 `explanation_file_id`，并将来源列入 `source_ids`。
- `source_ids`、`source_locator` 记录来源和定位。转写必须指向已登记且可派生的 `source_locator.file_id` 和正整数 `source_locator.page`。如跨页可加 `end_page`。审核时可补原图的区域坐标。
- `record_type` 为 `index_only` 或 `transcribed`。题号索引允许记录题型、分值和来源，内容及分析字段留空。后续补全文时复用题号 ID。
- `confidence` 记录置信依据。`review_status` 见 README。人工核验必须填写 `reviewer`、`reviewed_on` 和 `review_note`。
- `content_complete` 在审阅全部题干、选项、公式、子问和所需图表后可置为 `true`。校验程序要求该记录已转写且状态为已人工核验。候选页码记录为 `candidate_page`、`candidate_end_page`，正式原页另由授权文件的页码定位。
- `knowledge_points`、`difficulty` 和 `intent` 为分析预留。第一阶段留空。

## 独立解答

`metadata/independent-solutions.jsonl` 以 `question_id` 关联题号，记录结果、推导、证据定位和适用范围。`independently_derived` 表示已按可比较的数学条件推导，`conditional_on_candidate` 表示题面或选项分歧使结果只能按候选解释。CLI 返回 `independent_solution` 并单独计数。正式答案、题面完整性和人工核验分别登记。
