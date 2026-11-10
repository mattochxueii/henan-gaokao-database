# 预测验证与时间证据

第十阶段目标、基线、回测和冻结文件继续由原接口读取。此目录保存独立的第十一阶段验证协议。它固定了目标定义、模型参数、年份、缺失处理、抽样和评分规则。历史结果已经公开，因此这是 2026 年制定规则后的回放。

## 复现

无密钥候选可直接执行第一条命令。后两条使用私有许可档案、盲审记录和裁决。输出路径须为新文件。

```powershell
python scripts/forecast_validation.py --output work/format-replay.json
python scripts/forecast_labels.py --review forecast/validation/research/blind-review.json --decisions forecast/validation/research/adjudications.json --archive work/label-observations.json --audit work/label-audit.json
python scripts/forecast_validation.py --archive work/label-observations.json --output work/validation-run.json
```

`paper-dates.json` 保存同卷资料公开的保守日期及可追溯来源。试卷正文的档案版本和标注生产日单独记录。日期证据只能支持规定范围，当前转写与同期稿件的逐字符一致性仍可能不确定。争议题保留未知。用全年同一套规则标注，不用解答、既有标签或考后政策做历史特征。

评价单位为年份。同年两卷先合并分数，个别年份缺卷时同时披露按卷得分。删除某一评分年份只重算评分汇总，已拟合模型保持原训练窗。回放协议在本轮评分前锁定。结构断点和第十阶段探索结果在制定协议时已知，2027 年没有前瞻评分结果。八个试验标签记录可复核性，当前均不进入正式预测。

## 冻结与独立时间证明

本地冻结保存原文件和 SHA-256。私有 Git 提交增加可审阅的历史记录。独立时间证明需要由可信签名方签发、验签及保存原始回执。

在获授权前可在本地生成 RFC 3161 请求。它只封装文件摘要、摘要算法、随机数和请求参数。在授权范围内选择可信时间戳机构后，才可将请求发送并保存其原始 DER 响应、证书链、信任锚及签名时间。验证时既检查响应与原始请求匹配，也核对被证明文件的字节和当时的证书有效性。记录审查者、时区、凭证版本与政策。公开哈希或登记公开证明均须单独授权。

```sh
openssl ts -query -data forecast/frozen/henan-2027-math-v3.json -sha256 -cert -out v3.tsq
openssl ts -query -in v3.tsq -text
# Signed response and trust files are obtained only after authorisation.
openssl ts -verify -queryfile v3.tsq -in v3.tsr -CAfile tsa-root.pem -untrusted tsa-chain.pem
openssl ts -verify -data forecast/frozen/henan-2027-math-v3.json -in v3.tsr -CAfile tsa-root.pem -untrusted tsa-chain.pem
```

目前状态为本地冻结和私有 Git 记录，独立签名时间证明待取得。RFC 3161 约定及证书标识更新见 [时间戳协议](https://www.rfc-editor.org/info/rfc3161/) 与 [RFC 5816](https://www.rfc-editor.org/info/rfc5816/)。
