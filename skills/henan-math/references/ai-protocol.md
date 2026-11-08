# 动态AI候选协议 v1（历史数学回放，禁止直接导出学生卷）

当前可发布命题必须使用 [writing-protocol.md](writing-protocol.md) 的v2三层流程、5题样卷检查和PDF-only独立考生审题。下文只保留第三阶段证据与内部计算兼容，不是当前出卷入口。

宿主AI先研究真实候选及其分析，再自行设计蓝图和不同数学结构。JSON是AI创作结果的传输格式；本地程序不以26个题目族填充ai模式。

调用链：research → rules / plan → 宿主创作JSON或OpenAI Responses → 独立规格求解 → 审题 → 修订 → 独立AI复核 → review导出。命题者的答案与design不送入数学求解进程。程序不能证明自然语言与规格语义完全一致，独立AI须逐项比对，正式使用还需教师审阅。

## 文档格式

顶层含schema_version=1、blueprint、provenance、questions。
blueprint含mode(full/mixed/sequence/derivative/acceptance)、profile、slots（按序仅需module）、title。
provenance为mode=ai、provider=host_ai、model_version=not_exposed_by_host（不知道时）、api_calls=0、template_calls=0及实际生成说明。
每题含id（orig:ai:命名空间）、slot、kind、points、module、generation(provider/model_version)、problem、design。
禁止family和parameters字段。不得用现有实验候选替代一次新的创作并声称新生成。

problem含context（语境）、given_text（全部必要背景条件）、tasks（至多5项）、单选options、多选assertions及可选answer_domain。design含structure、reasoning_path、knowledge_combination。所有数学约束同时明确进入任务规格；出现语义与规格冲突就退回修订。
单选options的A-D项各含text（LaTeX）、semantic_value（安全表达式）、error_path。真选项可解释正确路径，假选项须写具体学生误解。多选assertions为A-D真值任务，每项text与数学字段绑定，独立判断真假。

现成的完整、真实协议文件在experiments/phase3/proposals。仅作为格式和本轮运行证据。生成新题应重新推导数学结构。

## 求解规格

表达式仅允许安全四则、幂、初等函数、有限集合比较；符号见ai_spec.py。禁止代码、属性访问、任意函数。新结构可以组合通用任务，不能新写一个答案然后假称程序已验证。

- evaluate(expression)：求值；equation(expression,domain,unique)：全解，unique可要求唯一。
- system(variables,expressions,conditions)：表达式等于0，筛选不等式条件。
- sum/product(expression,index,lower,upper)：有限和积。
- recurrence(relation,initial)：u(n)、u(n+1)表示递推，relation移项等于0；recurrence_sum另给weight及upper。
- derivative(expression,variable,domain,at)：求导/指定点导数，有限差分独立交叉。
- extrema/optimum/monotonicity(expression,variable,domain,open)：完整临界集、端点、连续性。optimum另给ask(max/min)。
- parameter_monotone：参数线性、导数系数符号固定时求单调不减范围；parameter_bound求全域非负参数。超出可判定条件即拒绝。
- nonnegative：完全最值分析与取等；identity/comparison：恒等、符号判定与反例。不是任意证明器。
- probability/count/expectation：有限等可能sample_space与condition/event，可复现穷举。
- coefficient、statistics、vector、geometry、intersection、point_on_curve：具体字段见ai_spec.solve_task与本轮候选。
- assertion真值任务：derivative_claim、probability_claim等。

不支持、超时、定义域不连续、解集不能完整确认：失败并保留记录。禁止AI口头保证替代数学验证。

## 验证与输出

generate保存raw-ai-proposal、events、rejected和run。最多3候选/槽位。宿主模式失败后由宿主读取反馈，重新设计候选，保存原版和修订理由，重新运行到新目录。API模式最多3次总调用（默认2），格式/网络失败与数学反馈共享预算，输入40000字符、输出上限24000token，超限退出。无隐式收费调用。

review报告的questions/re_reviews须含candidate_sha256、status=pass、reviewer、model_version和独立高中解法。版本哈希不匹配拒绝。独立AI审题不是人类审题或形式化证明。

状态分别保留：已完成程序验证、已完成符号与数值交叉验证、已完成独立AI推理审查、尚需人工核验、验证失败禁止发布。修改题面后旧记录失效。正式试卷评级不能从测试通过推导。

当前边界：API仅通过模拟传输测试，未实际联网付费调用；任意自然语言证明不受支持；原题无统一语义AST，跨真题的结构比较依赖版本绑定分析；不能证明全网首次原创。
