# 2027 河南新高考六科候选示范卷

## 主三科

三科各 150 分。学生卷采用 practice 排版，答案和评分参考单独成册。可编辑版的分页按 Word 实际渲染核对。
- **语文**（22 题，150 分钟）。[学生 PDF](chinese/paper.pdf) · [解析 PDF](chinese/solutions.pdf) · [学生 Word](chinese/paper.docx) · [解析 Word](chinese/solutions.docx) · [Markdown](chinese/paper.md) · [外审包](chinese/external-review/)
- **数学**（19 题，120 分钟）。[学生 PDF](math/paper.pdf) · [解析 PDF](math/solutions.pdf) · [学生 Markdown](math/paper.md) · [解析 Markdown](math/solutions.md) · [外审包](math/external-review/)
- **英语**（67 题，120 分钟）。[学生 PDF](english/paper.pdf) · [解析 PDF](english/solutions.pdf) · [听力朗读稿 PDF](english/listening-script.pdf) · [学生 Word](english/paper.docx) · [解析 Word](english/solutions.docx) · [朗读稿 Word](english/listening-script.docx) · [外审包](english/external-review/)

## 核验记录

三卷均绑定同科真题、命题画像和 2027 政策。语文与英语各用三份分块候选稿合卷，原始结构化题面、采分说明及选材依据随卷保存。英语采用听力 30 分、笔试 120 分原始分计入总分的口径，两节均播两遍。[英语政策核对表](english/external-review/policy-check.json)

- **语文**。信息、文学与文言正文分别为 1,640、1,779、632 汉字。机检计入出处和注释后的口径也随卷保留。第 9 题补写新增作答区，第 17 题延长空位并纳入有出处的开放答案，第 18 题检查两种明确的语病，第 21 题改为跨段比证。古诗栏目与材料同页。[三轮记录](chinese/board/) · [量化核验](chinese/validation.json)
- **数学**。覆盖十个主干模块。第 7、11 题分别改为有耦合约束的空间最值与两圆外条件下的切线推理。第 10 题由盲解发现符号求解漏根，修复后恢复三零点对应的正确选项。第 7、16、18 题配图的标注经二次调整。14 题完成全部程序规格核对，另外 5 题保留相应的独立论证。[三轮记录](math/board/) · [量化核验](math/validation.json)
- **英语**。阅读 A–D 合计 1,485 词，C、D 平均句长分别为 26.47 和 20.75 词。语法十空覆盖八类各有证据的考点。第 31、34 题改为根据阅读材料在新情境中辨认证据。第 57 空改为 way 后的不定式。阅读、完形及写作标题随文，题号方括号与空线连续。第 63 空所用文化材料以非遗数字博物馆的公开资料核证。[三轮记录](english/board/) · [量化核验](english/validation.json)

历年题号变化时，语文与英语按题组内的位置和功能做真题对照。个别数学同号真题仍只有有限版本证据，逐题质量记录已标明。历史原创题面的数值归一化比对覆盖 104 个归档文件和 650 条题面签名，本批完整题面未出现匹配。[原创性比对](originality.json)

三卷均经历三轮本地隔离审稿，最终状态为 LOCAL_QA_PASSED，Fatal 为零。教师审阅及学生实测均为零。外审包保存本地待审内容及反馈模板。[统一验收](validation.json)

## 物理、化学、生物学

每科 100 分、75 分钟。三科按已入库的 2026 年河南选择性考试卷面组卷，对照 2025、2026 年正式卷同题位与 DNA 画像。2027 年报名问答确认继续实行物理首选、化学和生物学再选的制度，试题结构沿用 2026 年题卷作为模拟依据。[河南省教育厅 2027 年高招报名问答](https://yk.eeahn.cn/portal/article/index.html?cid=23&id=7330)

- **物理**（15 题）。单选 7 道、多选 3 道、实验 2 道、计算 3 道。力学和天体 37 分，电磁 49 分，光热波和近代 14 分。选择题配图 7 道、非选择题配图 5 道。实验使用 10 个题内填空，三道计算题分别预留 7、7、10.4 厘米书写区。[学生 PDF](physics/paper.pdf) · [解析 PDF](physics/solutions.pdf) · [学生 Word](physics/paper.docx) · [解析 Word](physics/solutions.docx) · [外审包](physics/external-review/) · [审稿记录](physics/board/)
- **化学**（18 题）。14 道单选 42 分，工艺、实验、反应原理、有机合成分别为 14、14、15、15 分。选择题配图 10 道、非选择题配图 4 道，非选择嵌入式填空分布为 7、8、10、7。[学生 PDF](chemistry/paper.pdf) · [解析 PDF](chemistry/solutions.pdf) · [学生 Word](chemistry/paper.docx) · [解析 Word](chemistry/solutions.docx) · [外审包](chemistry/external-review/) · [审稿记录](chemistry/board/)
- **生物学**（21 题）。16 道单选 48 分，5 道非选择合计 52 分。选择题配图 6 道、非选择题配图 5 道，非选择嵌入式填空分布为 9、7、6、7、7。[学生 PDF](biology/paper.pdf) · [解析 PDF](biology/solutions.pdf) · [学生 Word](biology/paper.docx) · [解析 Word](biology/solutions.docx) · [外审包](biology/external-review/) · [审稿记录](biology/board/)

三卷 54 题全部完成学生卷隔离重解。图件逐一运行中文标签和碰撞检查，学生与解析 PDF 均逐页复核。物理、化学、生物学分别经过 3、3、2 轮计分审查，终版均为 LOCAL_QA_PASSED。外审包供用户送审，教师审核与学生实测目前各为 0。Word 的题文与选项可编辑，公式和题图以内嵌图件保留印刷质量。[小三科验收](science-validation.json) · [原创性与结构重写记录](originality-science.json)
