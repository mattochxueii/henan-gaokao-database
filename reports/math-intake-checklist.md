# 需要手动补齐的数学资料

优先补两份 6 月正式考试全国一卷数学。可直接上传获准本地保存和结构化处理的文件，或先放在工作目录 `work/math-intake/`。文件名可采用下列名称，正式入库时脚本会按 SHA-256 命名。

1. **`2025-national-1-math-original.pdf`**。完整考场卷面或授权复制件，含卷首、题号 1–19、图表及末页。优先使用教育考试机构或出版机构提供的授权版本。2025 年卷可向语文出版社核实《高考试题分析（2026年版）》数学分册所收录的全国一卷及许可。中国教育在线考后页面供定位题面。锦宏四页文件自称回忆版，不能作为原卷母本。 [语文出版社数学样章](https://www.ywcbs.com/app/gkstfx2026/sx/) · [中国教育在线卷面入口](https://gaokao.eol.cn/shiti/sx/202506/t20250607_2673303.shtml)
2. **`2026-national-1-math-original.pdf`**。同样含卷首、题号 1–19、图表及末页。优先向考试机构或出版机构获取；语文出版社《高考试题分析（2027年版）》发布通知明确该版依据 2026 年全国卷。村学云部落可用作四页扫描的追溯线索，其真伪、页图可用性及许可都需核实。请优先保留第 13、17、18 题所在页的清晰图像。 [语文出版社发布通知](https://www.ywcbs.com/xwdt/zxdt/202607/t20260721_1352.html) · [第三方四页扫描线索](https://1cunzhang.com/index.php?id=5830&p=article)
3. **`2025-national-1-math-marking.pdf`、`2026-national-1-math-marking.pdf`**。如能获得权威正式参考答案、评分说明或分步骤给分细则，请附来源和页码。若只能提供获得授权的出版机构或教师解析，分开提供并明确发布者。锦宏已有第三方答案入口，2025 版共 15 页但文字层几乎为空，2026 版为 13 页可读讲评。两份均未核为命题方评分参考。 [2025 答案候选](https://www.jhgk.cn/upload/file/20250608/1749350495692083975.pdf) · [2026 答案候选](https://www.jhgk.cn/upload/file/20260608/1780886758179094231.pdf)
4. **文件许可凭证和可读图页**。请附权利主体、文件取得方式、是否允许保存、结构化处理及再分发的凭证。2025 年优先保留第 6 题向量图和风速表、第 15 题两张表、第 17 题立体图。2026 年保留第 15 题棱柱图和末页。若图表已清楚包含在授权原卷中，可从该文件登记裁切图。若另附图，注明页码、题号和许可。

## 入库位置

- 原卷 `originals/2025/math/2025-cn-math-national-1/`、`originals/2026/math/2026-cn-math-national-1/`
- 答案及解析 `answers/2025/math/2025-cn-math-national-1/`、`answers/2026/math/2026-cn-math-national-1/`
- 原图或裁切图 `assets/2025/math/2025-cn-math-national-1/`、`assets/2026/math/2026-cn-math-national-1/`
- 每份文件按 [收据字段](../metadata/data-dictionary.md) 登记。运行 `import-file` 后，才有文件 ID、路径和哈希。处理权限允许时运行 `extract-pdf`，再把逐题定位和经核验的文本写入现有 `questions/<year>/math/<paper_id>.jsonl`。

## 本轮为什么没有保存候选文件

两年锦宏卷面和答案可浏览，未见文件级保存和结构化许可。2025 锦宏题面注明回忆版。二一教育可查解析，其网页文字层丢失多处公式。2026 五网原件下载受站点条件限制，扫描页面可定位但无法在本轮读取全部页图。考试卷网自己标残缺。中国教育考试网主频道本轮可达，未找到两年整套原卷和评分参考。语文出版社公开的是样章和发布信息。 [中国教育考试网](https://gaokao.neea.edu.cn/) · [二一教育 2026 解析](https://zy.21cnjy.com/25912080) · [五网下载页](https://www.5ol.com/atta/202606/12/7b1fc8c01de65406485108b12b3e1854.html) · [考试卷网](https://kaosj.com/papers/2026/06/2026-national-volume-1-gaokao-math-paper/)

GitHub 汇编许可只涵盖维护者拥有的整理权益。另一个结构化题面库的底层权限未核实。一个 2026 数据集明示底层许可未知且当前预览仅 18 行，另一个虽列 19 行，但缺许可元数据且答案是模型作答。以上来源用于交叉比对或寻找授权母本。 [数学汇编权利说明](https://github.com/deekur/gaokaomath/blob/main/README.md) · [新高考数学试题知识库](https://github.com/TsubameHata/gaokao_math_corpus) · [GKShuxue 数据集](https://huggingface.co/datasets/zstar1003/gkshuxue-2026-math-eval) · [豆包作答数据集](https://huggingface.co/datasets/zzf-fun/doubao-edu-2026-gaokao-math-national-i)
