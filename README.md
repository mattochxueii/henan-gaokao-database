# 河南新高考真题数据库与数学命题原型

截至2026-11-08，沿用第一阶段的12卷归属登记、71条来源、38条数学索引和独立推导。2025、2026数学各19道完整候选题面现有仓库内私有工作目录及可迁移的加密备份。另有38条版本绑定分析、命题规则、可安装Skill、四组真实运行实验。

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
python scripts/install_math_skill.py
```

默认安装到本项目的.agents/skills/henan-math，配置为指向仓库的相对链接。打开项目后由支持SKILL.md的宿主加载。独立安装包可以解压后使用--database指定仓库根目录，或设置HENAN_MATH_DB。仓库与项目内安装一起移动仍可定位。外部安装后单独移动仓库需要重新安装相对配置。

```powershell
python .agents/skills/henan-math/scripts/run.py research --topic 数列
python .agents/skills/henan-math/scripts/run.py generate --mode sequence --seed 20261107 --output <新的输出目录>
python .agents/skills/henan-math/scripts/run.py verify <输出目录>/run.json
python scripts/math_skill.py generate --topic 等比数列 --count 1 --kind constructed_response --difficulty 4 --output <新的输出目录>
python scripts/math_skill.py generate --mode derivative --output <新的输出目录>
python scripts/math_skill.py generate --mode mixed --output <新的输出目录>
python scripts/math_skill.py generate --mode full --output <新的输出目录>
```

支持知识模块、题型、题量和设计难度筛选。26个受支持题目族在执行时按种子采样，题目结构由本轮AI研究设计。宿主AI使用Skill编排研究、设计和推理复核，本地求解器重新计算数学结果。本轮未调用外部模型API，远程调用与费用预算均为0。自由自然语言题面的任意语义验证尚未实现，增加题目族需要同步扩展独立求解器与测试。

每题最多3次重试，每次重做验证并保存attempts.json。新输出目录保护历史记录。题面校验值变化会使旧验证失效。数值替换形式的同卷重复会被相似度门槛拦截。文本检测范围为当前38候选及同卷生成题，全球原创性与真实难度仍需要外部评审。

150分模拟采用历史候选的19题结构。2027的细节仍属模拟设定，正式考试通知优先。多选题部分得分在模拟卷头明确约定。

## 已运行成果

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

新题目族须增加规范题面、独立求解、选项判定、相似度与失败测试。新增命题规则须给证据和分类。样本量为两套，观察频率不能直接升级为固定命题比例。

## 报告

详细验收见reports/phase2-delivery.md。逐题记录见reports/question-audit.json和analysis/curation.jsonl，异文见reports/phase2-conflicts.md，命题规律见reports/paper-patterns.md，程序与恢复结果见reports/test-results.json及reports/fresh-environment.json，PDF逐页结果见reports/pdf-qa.json。第一阶段报告作为历史记录保留。
