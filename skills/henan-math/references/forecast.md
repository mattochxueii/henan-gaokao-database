# 预测研究与命题模式

`generate --study-mode standard` 使用既有高考蓝图和整卷门槛。专项训练用 `--study-mode targeted` 与专题参数。两种模式都不接收冻结预测或预测标签。

研究模式先执行 `forecast-context <冻结文件>`。`target_evidence_tiers` 区分探索性估计和弃权，`prospective_calibration` 单独记录前瞻校准状态，目前为未具备。现有 v3 的历史估计都属探索性，弃权目标不参与命题绑定。按可用方向研究题目机制，题型与分值仍由蓝图决定。制作宿主 AI v2 候选时，顶层添加 `forecast_snapshot_sha256`，每题填写 `forecast_targets`，元素有目标 `id` 及关联依据 `why`。程序核对有估计的目标、显式证明或跨问提示、主模块及冻结哈希，并在标题添加“概率预测研究实验”。随后照常独立求解、PDF 盲审并验证质量。

```powershell
python scripts/math_skill.py forecast-context forecast/frozen/henan-2027-math-v3.json
python scripts/math_skill.py generate --engine ai --study-mode forecast-research --forecast-snapshot <冻结文件> --candidates <AI候选.json> --output <新目录>
```

正式整卷仍需样卷证书，校准整卷也需专项证书。研究模式拒绝模板回退。公开候选自带同期来源回测，私有预测快照和逐题标签从许可档案本地取得。

```powershell
python scripts/forecast_research.py backtest --output work/as-of-backtest.json
python scripts/forecast_research.py database --output work/research.sqlite
python scripts/forecast_research.py verify-freeze <冻结文件>
python scripts/forecast_validation.py --output work/baseline-comparison.json
```

只有确认河南的实际卷型、真题公开时间和独立结果标签后，才用 `forecast_research.py score <冻结文件> <结果.json>` 评分。结果需有 `exam_date`、`published_on`、`target_year`、`subject`、`region`、`series`、`series_confirmed`、`official_identity_url`、`independent_review`、`paper_version_sha256`、`target_spec_sha256` 与 `events`，可加 `shares`。同版目标用 Brier 和对数损失，未知不计分。原创题仍由数学解答和独立质量审查验收。低概率与研究弃权不改变正常复习范围。
