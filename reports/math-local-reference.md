# 两套数学卷本地参考采集

## 实际取得的资料

2025 年下载了锦宏四页 PDF，首页自标回忆版，带站方标识。2026 年下载了锦宏四页 PDF，并从村学云部落正常公开页面取得四张页图。逐页渲染和目视核对后，2025 年用锦宏回忆版，2026 年用第三方扫描候选作为本地查询版。后一来源对原卷身份的声明尚未获考试机构核实。 [2025 锦宏发布页](https://jhcee.cn/pc/gk_information/consultation_detail-d6278da9-0614-42f2-b955-956d684bd64c.html) · [2026 锦宏发布页](https://www.jhgk.cn/mobile/trendDetails.htm?id=d7c00c3c-6b56-4ea5-86f6-1b627dfa708b) · [2026 扫描候选](https://1cunzhang.com/index.php?id=5830&p=article)

破冰 PDF 本轮浏览器直开超时，沿用已核预览做比较。五网页面能查看部分文字，原文下载受站点条件限制。 [破冰候选](https://www.hnpobing.com/uploads/allimg/20250615/1-250615091625101.pdf) · [五网候选](https://www.5ol.com/atta/202606/12/7b1fc8c01de65406485108b12b3e1854.html)

## 卷面与查询

两年各 19 条本地候选题面，覆盖 1–19 题，各 150 分。每条按原有题目 ID 关联独立解答。题面是依据页图整理的中文与 LaTeX 表述，保留数学条件、选项顺序、子问、图表所在页和位置框。2025 年第 6、15、17 题及 2026 年第 15 题共核对了 5 处图表框。源文件及页图分开留存，文件 SHA-256 在本地清单里。完整性计数区分本地可答的候选题面和经原卷审核的正式题面，后者仍为 0。

从仓库根目录运行以下命令。两条指定题号查询已经实际执行，输出同时含题面、版本、页码及独立解答。

```powershell
python scripts/cli.py --reference-dir ../../work/math-reference-local validate
python scripts/cli.py --reference-dir ../../work/math-reference-local query --year 2025 --subject math --number 1
python scripts/cli.py --reference-dir ../../work/math-reference-local query --year 2026 --subject math --number 17
python scripts/cli.py --reference-dir ../../work/math-reference-local report --subject math
```

GitHub 同步范围为程序、来源登记与核验报告。参考 PDF、页图和整卷题面数据存放于工作区的 `work/math-reference-local/`，在仓库目录及发布 ZIP 之外。现有 `--complete-only` 仍以正式原卷的人工完整性核验为标准。

## 逐页确认的差异

- **2025 第 6 题**。实际箭头从 `(3,3)` 指向 `(0,2)`，对应当前版 A。先前破冰的图形文字描述方向相反。第 4 题的正确数值在锦宏页图为 C，第 9 题为 BC，第 11 题为 ABC，其他候选出现选项位置差异。第 15 题附表中首列将 0.005 与 3.841 配对，按图保留并标疑；题设使用 0.001 列，页图显示 10.828。 [2025 锦宏 PDF](https://www.jhgk.cn/upload/file/20250610/1749549496776033663.pdf) · [二一教育候选](https://zy.21cnjy.com/24899530)
- **2026 第 9、12 题**。锦宏实际印出第 9 题 D 项分母为 `z−1`、第 12 题首项系数为 3。扫描候选分别为 `z−i`、5。这些是实物版本差异。 [2026 锦宏 PDF](https://www.jhgk.cn/upload/file/20260608/1780886746084032608.pdf) · [扫描候选第 2 页](https://1cunzhang.com/assets/gaokao_pages/gk2026_8095de_p2.jpg) · [扫描候选第 3 页](https://1cunzhang.com/assets/gaokao_pages/gk2026_8095de_p3.jpg)
- **2026 第 13、17、18 题**。两套本地页图均显示第 13 题第一空为相位、第 17 题为 15 分。第 18 题扫描候选写 Q 在第三象限，锦宏实际印 P，均用 PFO 作面积参照。按各自页图保留差异。 [2026 锦宏 PDF](https://www.jhgk.cn/upload/file/20260608/1780886746084032608.pdf) · [扫描候选第 3 页](https://1cunzhang.com/assets/gaokao_pages/gk2026_8095de_p3.jpg) · [扫描候选第 4 页](https://1cunzhang.com/assets/gaokao_pages/gk2026_8095de_p4.jpg)

2025 年仍需要经认证的考场页图来裁决选择题字母及附表。2026 年仍需要命题方原页或能追溯至命题方的出版版本来确认扫描身份。两年还缺正式评分参考。当前返回的是既有独立推导及适用版本说明。
