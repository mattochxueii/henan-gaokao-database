# 数据、来源与授权

初始随包数据库含 1 份项目原创样卷、5 道题及解释。历史来源目录按年份、学科、系列与地区登记候选卷。历史目录行的 `availability` 为 `source_only`，随包历史完整题目数为 0。

第三方历史来源包括教育考试机构公告、学校整理版，以及 deekur/gaokaomath 和 DxAThing 的 LaTeX 汇编。汇编授权的适用范围以各自声明和底层内容权利为准。可下载、已在项目私有环境核验或来自官方机构，均不自动产生全文转载权。历史目录使用公开 URL 和书目字段。链接可能失效，使用者应遵守访问条件、用途限制和适用法律。

- [deekur/gaokaomath](https://github.com/deekur/gaokaomath)
- [DxAThing/Gaokao-Math-Problems-Compilation](https://github.com/DxAThing/Gaokao-Math-Problems-Compilation)

## 关系与版本

每个目录包以 `manifest.json` 记录用途、数据版本和文件 SHA-256。JSONL 表分别存放 `papers`、`paper-regions`、`sources`、`questions`、`occurrences` 和 `answers`。一卷可有多个地区关系。同一题面由多个实例引用，同卷题号唯一。原卷纸面位置和来源由实例关联。答案必须绑定实例和题面版本。合并时拒绝 ID 对应不同内容的冲突。判断同题和改编题仍需编辑复核。

普通导入按规范化题面生成版本 SHA。维护者迁移的历史包沿用已有题目 ID 和来源版本哈希，并保留原文件校验。自行修改任何数据都应通过重新制包产生新版本，更新答案与来源。索引使用数据包清单重建。审计可核对附件。校验通过表示数据一致性，题面及答案的学术核验状态单独记录。

`national/catalog/` 保存系列、地区、考试制度与课程标准分类。数学用 `track` 区分 `unified`、`liberal`、`science`。英语用 `component` 区分 `written`、`listening`、`speaking_listening`。物理、化学、生物的 `composite_section` 关联 `parent_paper_id`。独立 `selective_provincial` 记录 `region_id` 和 `authoring_body`。语文使用实际试卷系列、地区与来源。原始分值和选考关系保留在纸卷或实例元数据里。

## 导入合法资料

1. 用 `python scripts/local_data.py sources --year 2024` 查卷名、系列、地区和来源。自行取得授权允许处理的文件。
2. 写入 UTF-8 JSON 输入。顶层键为 `dataset_id`、`papers`、`sources`、`paper_regions`、`records`。每卷需要 `id`、`year`、`subject`、`series_id`、`reported_name`、`question_count` 及学科分类字段。每题需要 `id`、`paper_id`、`number`、`kind`、`points`、`stem`、`source_locator`（含登记过的 `source_id` 与页码或其他定位）。可提供 `options`、`formulas`、`parts`、`asset_refs`、`answer` 及分析字段。保持题目 ID、题号、来源和答案同版。字段实例见 [原创数据](../sample-data)。
3. 需要附件时，把路径登记为 `files/<相对文件名>` 并提供 SHA-256。运行 `python scripts/local_data.py prepare input.json /path/to/new-bundle --assets /path/to/attachments`。纯文本可省略 `--assets`。
4. 运行 `python scripts/local_data.py import /path/to/new-bundle`，再运行 `python scripts/local_data.py audit`。资料只写入忽略目录。导入后 SQLite 会按清单更新。保留输入、源资料与完整数据包作离线备份。
5. 改动资料时先备份当前包。原 ID 需保留时，请在独立工作副本或停用旧数据包后导入新版。资料目录名须与数据包版本管理协调。以 `audit` 验证完整性和跨包关系。

## 可选个人备份

复制经过审计的包目录即可进行明文备份和恢复。若需要加密，额外安装 `python -m pip install -r requirements-backup.txt`。通过 `local_data.py backup <数据包> <归档> --key <独立密钥位置>` 加密，以 `local_data.py restore <归档> <新数据包目录> --key <独立密钥位置>` 恢复。密钥和归档分别保管，随后用 `import` 登记。旧项目的分片归档由持有原密钥的维护者用私有仓库脚本恢复及转换。
