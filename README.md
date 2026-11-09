# 第五阶段：全国历年高考数学数据库

第六阶段新增逐题来源与答案校准、绑定真题版本的原创设计、考生盲审、专项到整卷的质量门及匿名作答工具。阶段结论与复现入口见 [校准报告](reports/phase6-calibration.md) 和 [命题研究](reports/phase6-research.md)。

已实际扩容21份完整第三方卷面及458条题目实例（449个去重主记录）。保留原有38题，合计23份数学卷、496个实例、487个主记录。2023乙卷理科23条因实质转写错误整卷隔离，默认研究检索排除；剩余473条仍是候选，不是官方认证或全部答案已验证。

新高考Ⅰ卷2020—2026形成连续145题系列，新Ⅱ卷七年145题；河南2020—2023旧文理数学分别登记，2024与新课标Ⅰ卷共享主卷；另有浙江2022特色样本。原数据、独立解答、备份、Skill、模拟卷均保留。每年每卷的真实数量与缺项见 [完整性报告](reports/phase5-completeness.md)，机器统计见同名JSON，原文/公式抽查范围见phase5-visual-review.json。

## 恢复与全文查询

安装requirements.txt；原件渲染需要Poppler与中文字体。完整第三方原文和答案不进入Git明文，恢复两个独立备份需分别持有仓库外的密钥，勿将密钥放入仓库或ZIP。

```powershell
python scripts/private_data.py restore --key <旧库密钥文件>
python scripts/national_cli.py restore --key <全国库密钥文件>
python scripts/national_cli.py validate
python scripts/national_cli.py build-index
python scripts/national_cli.py sqlite-query --year 2020 --series cn-new-gaokao-1 --number 18
python scripts/national_cli.py query --region 河南 --year-from 2020 --year-to 2024 --topic 导数
python scripts/national_cli.py stats
```

源JSONL位于相对目录.private/national-reference，SQLite是可重建索引。同一题可在多份卷出现，保留各自题号、分值、答案与原页码；省份通过关系表使用同一卷。两套备份不互相覆盖。全国库45个加密分片含149文件，旧库63分片继续有效。实际全新目录/独立Python恢复报告见reports/phase5-fresh-restore.json。

## Skill与目标制度

```powershell
python scripts/install_math_skill.py --destination <新的技能安装目录>
python <技能目录>/scripts/run.py research --series cn-new-gaokao-1 --year-from 2020 --year-to 2026 --topic 数列
python scripts/national_cli.py reference-pack --topic 导数 --target-region 河南 --target-year 2027 --output <私有工作目录>/references.json
python scripts/math_skill.py plan --mode full --output <蓝图.json>
```

支持年份范围、省份、学科、系列、知识点、题型、已标注难度、思想方法和能力。未标注不按位置猜测。参考分层为当前适用系列、同系列历史、可比新卷、旧卷/特色；课标待核降权，每卷限额，不能按网站或题数投票。目标年度未登记就停止猜测；2027结构仍是模拟设定，历史选考制和22题结构不能覆盖当前19题150分规则。Skill详见skills/henan-math/references/national.md。

## 新实验与验证边界

任务A数列纵向研究见reports/phase5-task-A.md；任务B跨卷型导数研究见phase5-task-B.md，均绑定实际原题和来源。新增29条内容分析，未知字段保留空值。

本轮宿主AI实际创作了五题样卷C及150分整卷D，无模板族调用；不是旧候选重放。交付位于experiments/phase5/pilotC-v3与fullD-v3，含题目/答案PDF、候选、独立PDF考生审题、数学对照及证书。失败稿与修订保留。作者估时134分钟与独立审题119分钟有分歧，均非实测；不得认定高考等难。已修复并回归阻断公式内中文缺字占位符，答案排版另行实际查看。

```powershell
python scripts/evaluate.py
python scripts/national_duplicates.py
python scripts/package_project.py --phase 5
python scripts/check_phase5_restore.py --archive <项目ZIP> --legacy-key <旧库密钥> --national-key <全国库密钥> --output <新空目录> --report <恢复报告.json>
```

模板练习模式、AI三层写作与严格发布流程仍可用，下面保留第四阶段操作说明。公开CI无需密钥，运行生成、题面和全国数据导入回归；真实全文与备份集成在私有环境运行。测试通过不等于题面或高考质量认证。

## 继续添加历史卷

1. 先核实卷名、年度、地区关系、制度和许可。全国同卷只追加paper-regions，独立省卷另建Paper；六学科component约束见national/schema.json。
2. 对具有可处理条件的公开版本，在national/acquisition.json加入固定提交的真实文件及Git blob SHA；登记实际依赖图到asset-manifest.json。保留来源许可通知，不把项目自身整理许可当作所有底层题目授权。
3. collect_national.py下载或校验已有缓存，同时获取图像；import_national.py解析TeX、选项、子问和答案并检查原PDF定位。个别新增卷预检查失败会记录并跳过，不用空索引补数。首次解析后运行render_national_assets.py建立TikZ关联PDF页预览，再重新解析；不执行不受信TeX。
4. 逐页、逐公式对照原文件；错误来源先隔离，修订用curation哈希绑定并保存差异。新格式先加解析器和错误夹具测试，不能靠改预计题数通过。
5. 更新catalog、目标规则及版本绑定分析，运行validate、去重、全部测试与独立审查。源码不改变原件；未验证答案继续标候选。对新数据选一个新的备份版本及仓库外新密钥，执行national_backup.py --version <新版本> --key <新密钥>，保留旧分片，实际恢复后提交。避免只在当前工作目录保留全文查询结果。
6. 不要直接提交research导出的完整第三方原题JSON。完整原文进入受控私有层及新备份，公开元数据只记定位和状态。人工核验与AI/自动校验分开。

---

# 第四阶段：规范中文题面与独立PDF考生审题

当前推荐 `experiments/phase4/final/fullA/` 与 `final/fullB/`：各19题150分、8页题目；A卷答案5页、B卷答案6页。先完成5题样卷，再创建整卷；A初稿被独立审题拒收后，实际替换统计、计数、图像题并重设计数列解答题。旧70题保留作审计证据，不再推荐作合格高考模拟卷。

本轮交付见 `reports/phase4-delivery.md`；旧70题逐题审查见 `phase4-legacy-audit.json`，新38题与真实候选风格比较见 `phase4-new-style-comparison.md`。样本仍是第三方2025/2026候选，2027沿用卷型为模拟设定。

本轮结论为“独立AI可读性、数学与风格审阅通过的模拟研究版”。125项程序测试通过不能替代质量判断。独立考生审题只读PDF及实际页图；答案另行校审。尚未教师审核、考生实测或形式化证明。初次答案校审发现的3处分页问题已由通用分页修复，保留旧报告及最终独立复查。

## 当前v2命题与发布

内部 `math_spec`、AI中文 `writing`、排版 `student-text` 分开；求解器只读数学规格，考生审题者只读PDF。无法转换的AST不得回退为题面。所有公式与条件绑定，先5题样卷，再整卷；最终须逐题数学对照和PDF-only审查，发布复制同一PDF字节。修题必须重新核验。

```powershell
python scripts/math_skill.py research --topic 数列
python scripts/math_skill.py research --topic 导数
python scripts/math_skill.py writing-request <候选.json> --output <无答案写作请求.json>
python scripts/math_skill.py attach-writing <候选.json> <AI写作结果.json> --output <v2候选.json>
python scripts/math_skill.py generate --engine ai --candidates <5题v2候选.json> --output <新样卷目录>
python scripts/math_skill.py publish <新样卷目录> --student-review <PDF考生审题.json> --math-comparison <数学对照.json>
python scripts/math_skill.py generate --engine ai --candidates <整卷v2候选.json> --output <新整卷目录> --pilot-certificate <新样卷目录>/publication.json
python scripts/math_skill.py publish <新整卷目录> --student-review <PDF考生审题.json> --math-comparison <数学对照.json>
python scripts/math_skill.py verify experiments/phase4/final/fullA
python scripts/evaluate.py
python scripts/audit_phase4_delivery.py
python scripts/compare_phase4_style.py
```

generate只产出待审稿，不能自行填写“通过”替代独立实际审阅。协议和真实创作记录见 `skills/henan-math/references/writing-protocol.md` 及 `experiments/phase4/proposals/`；重放不算新创作。v1只供历史数学回放，禁止直接导出AI学生卷。

安装：`python scripts/install_math_skill.py --destination .agents/skills/henan-math-phase4`，之后运行该目录的 `scripts/run.py`。PDF需Poppler（pdftoppm）及中文字体，Python依赖见requirements.txt。宿主AI流程无需新增API额度。模板备用模式仍显式使用 `--engine template`。

新电脑恢复及验证：`python scripts/check_phase4_restore.py --archive <项目ZIP> --key <单独密钥> --output <全新目录> --report <结果.json>`。检查完整题查询、已安装Skill的v2回放及冻结发布证书；新渲染稿不能冒用旧PDF审核。以下历史说明保留，当前出卷以上方v2流程为准。

# 河南新高考真题数据库与数学命题原型

截至2026-11-08，沿用第一阶段的12卷归属登记、71条来源、38条数学索引和独立推导。2025、2026数学各19道完整候选题面现有仓库内私有工作目录及可迁移的加密备份。另有38条版本绑定分析、命题规则及可安装Skill。第三阶段新增70道宿主AI动态设计题、六组真实运行实验及独立审题；26族模板作为备用模式保留。

当前可检索题面来自2025锦宏回忆重排版与2026第三方扫描候选。命题机构确认的完整原卷仍为0，人工逐题审核仍为0。候选原文保存在受控解密目录。

## 新环境恢复

需要Python 3.10以上及单独保存的恢复密钥。在仓库根目录执行。

```powershell
python -m pip install --target .deps -r requirements.txt
python scripts/private_data.py restore --key <另外保存的恢复密钥>
python scripts/cli.py validate
python scripts/cli.py query --year 2025 --subject math --number 1
python scripts/cli.py query --year 2026 --subject math --number 17
python scripts/math_skill.py research --topic 数列
```

database.json 的 reference_dir 指向 .private/math-reference，backup_parts_manifest 指向private-data/backup-parts.json，均使用相对路径。版本管理保存63个加密分片。恢复时按清单重组到.private/cipher-cache，校验整份密文，再解密。覆盖全部23个原有资料文件的inventory记录文件大小和SHA-256。恢复会检查认证加密、重复或越界路径、大小限制、文件清单和哈希，拒绝覆盖已有目录。读取时也会核对题面和页图哈希。全新目录、独立解释器的恢复和Skill测试见 reports/fresh-environment.json。

密钥不在仓库或ZIP中。请分别备份交付的恢复密钥和项目ZIP，丢失密钥无法解密。此仓库保持私有。加密备份用于现有私有项目连续访问，解密后原文的再分发仍受各来源权利条件约束。

## 查询和状态

```powershell
python scripts/cli.py query --subject math --kind fill_in
python scripts/cli.py query --subject math --kind fill_in --complete-only
python scripts/math_skill.py research --year 2026 --kind constructed_response
python scripts/math_skill.py research --topic 等比数列
python scripts/math_skill.py rules
```

普通题号查询返回完整候选题面、公式、选项、子问、图表定位、来源页码及答案。current_solution 和 answer_for_current_candidate 对应当前候选版本，independent_solution 保留历史推导。图表的image路径相对于database.json指定的reference_dir。asset_refs保留原页坐标框。

完整候选、候选页图视觉核对、版本冲突、条件解答、程序复算、独立推理审核分别记录。content_complete和--complete-only仍要求正式原卷及人工核验，所以当前结果为0。分析文件的模型标识为not_exposed_by_host，环境未提供可核实的精确宿主模型版本。

## 安装和使用Skill

```powershell
python scripts/install_math_skill.py --destination .agents/skills/henan-math-phase3
python .agents/skills/henan-math-phase3/scripts/run.py research --topic 数列
python scripts/math_skill.py research --topic 导数
python scripts/math_skill.py rules
python scripts/math_skill.py plan --mode full --profile geometry --output <蓝图.json>
```

支持--database、HENAN_MATH_DB及安装相对链接，详见skills/henan-math/SKILL.md。已有旧安装不覆盖，请选择新目录。

原创请求必须显式使用ai。宿主AI实际阅读研究结果后，自主设计蓝图和新数学结构，按references/ai-protocol.md写出结构化候选；本地程序独立求解并审题。读取已有实验JSON只是重放，不是再次创作。

```powershell
python scripts/math_skill.py generate --engine ai --candidates <宿主新候选.json> --output <新目录> --no-export
python scripts/math_skill.py verify <新目录>/run.json
python scripts/math_skill.py review <新目录>/run.json --report <独立审题.json> --no-export
```

上述v1命令仅供历史数学回放；review不再允许导出AI学生PDF。当前发布使用上方v2三层流程。程序、符号数值交叉、独立AI审题和教师待审分开保存，不代表形式化证明或高质量评级。

默认不需要API。用户已自行配置OPENAI_API_KEY时可使用--engine ai --model <显式模型>，提供者采用OpenAI Responses，格式失败、超时与数学反馈共用调用总预算（默认2、最高3），限制输入与输出长度，不记录密钥。本轮API仅做模拟传输测试，实际动态创作使用宿主AI，精确模型版本未暴露。

AI不可用时明确失败；只有显式--allow-template-fallback才回退。稳定备用命令：

```powershell
python scripts/math_skill.py generate --engine template --mode full --output <新目录>
```

26族模式沿用数学结构并调整参数，不代表AI自主原创。固定布局仅保留在template中；ai蓝图依据分析、覆盖和宿主设计组合模块。本轮两套150分卷采用历史候选19题结构，2027仍为模拟设定。任意自然语言证明、实测难度和高考风格尚不能自动认证。

## 第三阶段交付

- experiments/phase3/deliveries/sequence10：10道数列，100分。
- experiments/phase3/deliveries/derivative10：10道导数，100分。
- experiments/phase3/deliveries/mixed50：7题50分。
- experiments/phase3/deliveries/fullA、fullB：不同蓝图的两套19题150分卷。
- experiments/phase3/deliveries/acceptance5：3数列、2导数，5种结构的50分验收卷。
- 每组含原始候选、独立求解、独立审题、质量报告、paper/solutions.pdf及Markdown。
- proposals-initial、proposals、revisions、attempt1/attempt2保留失败与修订。过程快照保存在本地工作区，交付以deliveries为准。
- reports/phase3-ai-vs-template.md解释两种模式；reports/phase3-delivery.md记录验收与真实限制。
- GitHub Actions仅运行不解密的公开合成/原创回归测试；完整私有题库与加密恢复测试在本地安全环境运行。

两套150分卷目前偏基础至中档，压轴强度与分值需要教师审核，未评定为高质量高考模拟卷。创新度限于当前样本与结构比较，不能证明全网首次。

## 保留并修复的模板实验

- experiments/sequence 含5道递进数列题，共50分。
- experiments/derivative 含5道导数综合题，共50分。
- experiments/mixed 含7道跨模块题，共50分。
- experiments/full 含19道模拟题，共150分。结构为8单选、3多选、3填空、5解答。
- 每组提供paper.pdf、solutions.pdf、可编辑Markdown、图像、run.json与attempts.json。
- 答案册含结果、完整推导、知识模块、设计难度、独立计算结果及质量边界。
- 本环境未找到LibreOffice，Word无法完成要求的渲染核验。本次可编辑源为Markdown和JSON。

PDF使用中文字体和渲染后的LaTeX。可通过HENAN_MATH_FONT指定字体文件。未找到可嵌入字体时使用STSong-Light，换环境应重新渲染检查。原型图像以坐标构型为准，示意图标明特定参数。

## 数据文件

- metadata保留原有来源、用卷归属、独立推导与冲突记录。
- questions保留原有索引，原始数据未修改。
- .private/math-reference含完整候选题面、PDF及页图，默认忽略Git。
- private-data含认证加密备份和逐文件校验清单，密钥独立保存。
- analysis/questions.jsonl含38条逐题知识、能力、方法、条件设计、计算、推理、难度、创新及跨题比较。
- analysis/curation.jsonl含当前版本答案、修订推导、视觉复核与争议。
- analysis/rules.json区分官方要求、候选事实、有限样本观察、假设和模拟设定。
- analysis/paper-patterns.json给出按AI标签统计的覆盖、核心素养及难度分布。
- scripts/mathgen将题目提案、求解、质量门槛、蓝图和输出分为独立模块。

## 检查和重现

```powershell
python scripts/build_analysis.py
python scripts/audit_math.py
python scripts/evaluate.py
python scripts/qa_outputs.py
python scripts/math_skill.py verify experiments/sequence/run.json
python scripts/math_skill.py verify experiments/derivative/run.json
python scripts/math_skill.py verify experiments/mixed/run.json
python scripts/math_skill.py verify experiments/full/run.json
```

evaluate运行全部测试并保存结果。专项复算覆盖10道重点题，38题另有字段、题号、分值、源文件哈希、图表定位、题面分析绑定和AI页图检查。数学证明的AI复核与程序可复算部分分别说明，教师人工核验仍待补充。

## 继续维护

第一阶段的register、import-file、extract-pdf和report命令继续可用。新增试卷先核验地区、年份、命题主体与许可，再登记来源、导入允许保存的原件。授权PDF使用可选pdftotext提取，公式和图表另行审阅。数据字典见metadata/data-dictionary.md。

候选的新版本另存私有目录及清单，保留既有版本，生成新的分析校验值。先恢复旧密文到新空目录，再导入新版本。为新一代备份配置新的encrypted_backup、backup_parts_manifest和backup_inventory相对路径，再选新密钥备份。当前backup拒绝覆盖已有密文、密钥、分片或库存。

新AI数学操作须增加独立求解、语义排版、反例及超时测试；模板新增题目族同样须补齐规范与验证。新增命题规则须给证据和分类。样本量为两套，观察频率不能直接升级为固定命题比例。

## 报告

详细验收见reports/phase2-delivery.md。逐题记录见reports/question-audit.json和analysis/curation.jsonl，异文见reports/phase2-conflicts.md，命题规律见reports/paper-patterns.md，程序与恢复结果见reports/test-results.json及reports/fresh-environment.json，PDF逐页结果见reports/pdf-qa.json。第一阶段报告作为历史记录保留。
## 公开候选版

当前仓库仍是私有存档。运行 `python scripts/build_public_release.py --output ../gaokao-public --zip ../gaokao-public.zip`，可从明确审查的文件清单生成无私有 Git 历史的独立候选版。公开候选可直接初始化并查询原创样题，无需历史恢复密钥。历史原卷、全量题面、受限附件、加密分片和密钥保留在私有范围内。详见 [候选版说明](public-release/README.md)、[资料边界](public-release/DATA.md) 和 [验收记录](reports/opensource-readiness.md)。
