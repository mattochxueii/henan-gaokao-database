---
name: henan-math
description: 检索河南数学候选真题并研究命题特点，通过宿主AI或已配置API动态设计原创数列、导数、专项及高考风格模拟卷，独立求解、审题并输出PDF；保留明确标记的template备用模式。
---

# 河南数学研究与动态AI命题

使用时告知正在应用henan-math。先实际研究题库，再动态创作、独立求解、审题与交付。不得把运行模板或重放旧JSON说成一次新的AI创作。

## 定位与恢复

运行技能scripts/run.py。支持--database <仓库>、HENAN_MATH_DB及安装相对配置。私有原文需单独密钥恢复，见references/storage.md。未恢复时可以读取分析与规则、验证新原创题，不能声称已阅读完整原题。候选尚未获命题机构逐题确认。

## 研究与规划

先执行research --topic 数列及research --topic 导数，并读取rules。必要时按年份和题型检索。分析须关联原题ID、版本哈希、页码与证据。命题规则区分官方要求、候选事实、有限样本观察和模拟设定。2027详细结构未确认。

执行plan --mode full --profile balanced --output <蓝图.json>，根据研究证据与覆盖目标制定槽位。AI可以改变知识搭配、条件与解法，不得复制固定族布局。150分历史结构为8单选、3多选、3填空、5解答；2027沿用只是模拟假设。

## 动态命题（原创请求必须显式ai）

当前宿主AI阅读研究结果，依据蓝图自主设计不同数学结构，输出references/ai-protocol.md协议JSON。保留原始候选、模型标识（未知则not_exposed_by_host）、设计路径、干扰项误解路径。不能只替换原题数字。

python <技能目录>/scripts/run.py generate --engine ai --candidates <宿主新候选.json> --output <新目录> --no-export

可选API：用户已有环境密钥时，--engine ai --model <显式模型>启用Responses。无需为默认宿主流程购买API。请求、失败修订共享有界调用预算，密钥仅环境读取。无AI时明确报告；仅允许显式--allow-template-fallback回退。

## 独立验证与修订

求解进程只读取problem.tasks，绝不以命题者标准答案、设计解法或选项解释为求解依据。检查定义域、边界、根集、参数、唯一性、选项范围与题意。失败保留rejected/events；宿主根据反馈修订，记录旧哈希及理由，换新目录重新运行。API按剩余预算自动修订。

验证失败或未知不得进入通过卷。状态区分程序、符号数值交叉、独立AI推理、人工待审与失败。全部验证均不等于任意自然语言的形式化证明。

python <技能目录>/scripts/run.py verify <目录>/run.json

## 独立审题与导出

另起不读标准答案的独立推理流程审查原始题意、课程范围、条件、解法和干扰项。复杂风险任务由独立审题者复核。可用新上下文独立AI，但不得称为人类盲审。保存candidate_sha256及高中解法。修改题目后重新求解、审题，不能复用旧哈希。

python <技能目录>/scripts/run.py review <目录>/run.json --report <独立审题.json>

review仅对匹配版本且程序通过的题导出研究审阅版paper.pdf、solutions.pdf及可编辑Markdown。未审题的generate默认只保存候选草稿，交付前必须review。PDF逐页渲染检查公式、图、页边界、答题空间。高质量评级还需教师审核和作答实测。

## 模板备用模式

python <技能目录>/scripts/run.py generate --engine template --mode full --output <新目录>

26族参数化模式只称template备用练习。它的可靠性不能作为AI自由命题已验证的证据。覆盖详见references/coverage.md。

## 验收与边界

用户要求研究数列与导数、生成5道不同结构时：研究二者→读取规则→动态规划5槽→宿主逐题创作新JSON→generate ai→独立AI推理与程序比对→review→verify→逐页检查PDF。保存原始候选和修改；报告真实失败及不确定性。本轮可重放的验收证据位于experiments/phase3/release/acceptance5，但重放不算新的生成。

使用原创性报告比较条件结构、数学模型、解法、知识组合与情境。允许经典方法，不声称全网首次。任意证明、课程标准语义、实测难度均有未解决边界。若数学质量不足，即使测试通过，也只能交付带限制的研究版。
