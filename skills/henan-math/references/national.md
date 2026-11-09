# 全国历史资料检索与参考选择

使用完整题面需分别恢复旧库与全国扩容库；只有catalog不等于已读题。source-conflict隔离题默认不得用于研究或命题。需要调查冲突时用national_cli.py query --include-quarantined，必须保留警示，不能借此绕开质量门。

## 检索

在数据库根目录执行（安装技能scripts/run.py转发research的相同选项）：

```powershell
python scripts/math_skill.py research --series cn-new-gaokao-1 --year-from 2020 --year-to 2026 --topic 数列
python scripts/math_skill.py research --region 河南 --year-from 2020 --year-to 2024 --topic 导数
python scripts/math_skill.py research --series cn-new-gaokao-2 --kind constructed_response
python scripts/national_cli.py reference-pack --topic 数列 --target-region 河南 --target-year 2027 --output <私有工作目录>/references.json
```

还支持--subject、--difficulty、--method、--capability。难度、思想方法、能力只匹配已绑定的逐题分析，不按题号或位置自动填充；未标注的题可能检索不到。topic同时匹配完整中文题面、字面标志和已标注知识点，不能保证穷尽召回。全文输出文件不应提交Git。

返回题目主ID、所属试卷实例ID、原题号、完整题面/选项/子问/题图引用、答案及版本、原文件SHA和PDF页/TeX行。一个主记录可有多份卷中的实例，不能把跨卷复用计为更多独立研究证据。SQLite可重建，非原始权威层。

## 目标规则与分层

先读取national/targets中的目标省份、年份、学科；未登记目标不能自动拿其他年份替代。河南2027沿用2025/2026实际卷型作为模拟设定，尚非2027详细公告。

参考层级：当前使用系列100、同系列历史80、可比新高考55、旧卷/特色25；再考虑年份、课标与题型。不同课标或课标待核降权。每卷最多2题进入一个参考包，数量不是权重。旧文理卷提供方法，不能覆盖现代19题150分结构；旧卷选考题保留原分值，不改造成必答题。

阅读完整参考及analysis/rules、national/research的证据后才设计蓝图。记录实际读过的题目ID、版本和定位，明确官方要求/内容事实/样本观察/模拟设定。历年试题出现频率不是下一年必考概率。来自两个网站的同题不是两个独立样本。

研究范围可跨省；同卷跨省只追加用卷关系，不能复制题目。旧全国Ⅰ卷与新高考Ⅰ卷有不同series_id；2024河南虽仍3+x，数学与新课标Ⅰ卷共享主卷。其他科目按schema区分英语听说、理综子卷及省级选择性考试，不能只按3+1+2合并。
