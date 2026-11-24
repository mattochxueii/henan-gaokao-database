# 单卷与批量发布

以下命令接在 `python scripts/gaokao_platform.py` 后。宿主负责原创、局部改写及调度三个相互隔离的审稿上下文。每次使用 `authoring-context` 先读取同位真题与随版本绑定的排雷条目。新增条目写入 `data/qa/anti-patterns.json`，保留唯一编号、适用学科、严重度、检查动作与反例。

## 多卷

1. `authoring-context physics --limit 100 --output context.json`，再运行 `batch-plan physics plan.json --count 2`。六科均可使用；更多方向用 `--pool pool.json`，格式参见 `experiments/phase25/physics-batch/revised-pool.json`。每一受保护题位占用独立的模型、主情境、核心动作和图示表示。
2. 为每卷创作候选，放入 `job/paper-1/round1/candidate.json` 等相应目录，附图路径相对于该候选。各题填 `design.model/scene/action/representation`；指定题位的 `batch_role` 对应蓝图。写完后对照实际学生题面校正指纹。程序比较全体题对，检查重复指纹、数字归一化后的高重合文本和已支持的物理条件结构。读者仍需判断不同措辞是否使用了同一物理路径。
3. 运行 `batch-run plan.json 2027 context.json job`。按返回的状态，宿主填写候选或调度各卷的独立读者，再以同一命令恢复。横向冲突由 `batch-check plan.json A.json B.json --output cross.json` 单独复现。互斥处理在正式送审前执行。
4. 审题回复写入各轮的 `inbox/{solver,pedagogy,visual}/reply.json`。每位读者只收到自己的学生 PDF、规则、任务说明；教研员额外读取去答案的两年同题位参考，英语听力审查另读朗读稿。命题记录、评分参考、其他读者的回复不进入读者输入。印刷审稿实际逐页渲染；一个身份不能提交三份角色意见。外部服务可实现 `BlindProvider.review`，只接收同一份白名单输入。
5. 宿主按 `decision.json` 的 `rewrite` 题号重写，已锁定题号保持原始文本、共享材料、图件和答案。命题与审题记录绑定到实际 PDF；每轮产生不可覆写的 `scorecard-roundN.json`。一票否决计零。主干与器具每项扣 6 分、题位偏浅每题扣 4 分、弱干扰每题扣 3 分、抽象情境每处扣 2 分、图件每处扣 2 至 3 分。文字密度告警由盲审按语境核定。分数达到 85 且无否决、硬安检通过时取得发布资格；第三轮仍失败则停止。
6. 全部卷本取得资格后，把原有学科协议需要的核对、逐题审稿及视觉签字分别放入该轮的 `signoff` 目录，按命令返回的文件清单命名；恢复 `batch-run`，生成独立的学生卷和解析发布记录。评分是项目编辑判断，考生得分和难度另由真实试做检验。

## 单卷

对 `simulate` 生成的送审稿执行 `exam-qa <卷目录>`。对于常量测量题，候选的 `constant_observations` 须登记题号、符号和物理量的 SI 值；光电斜率支持带题面锚点的两组频率、电压及尺度。独立解题者仍须复查未被机器识别的常量和模型假设。自绘图通过 `core.exam_qa.save_figure` 按实际导出分辨率检查文字、图例和柱顶。

运行 `board-cycle <卷目录> <独立邮箱>`，按角色分开投递并恢复同一命令。单独导出使用 `board-packet <卷目录> solver|pedagogy|visual <新目录>`。也可用 `board-score <卷目录> <求解.json> <教研.json> <印刷.json>` 一次登记三个角色的回复。下一轮附 `--previous <上轮卷目录>`。全卷缺项需指出承接修订的题位，用 `--repair-slot <题号>`。放行后照原有学科流程生成解析、核对并发布。

正式样本的完整三轮输入与回复见 `experiments/phase25/physics-batch/{A,B}/published/board`。题面出现问题的原始盲判与最终学生解析分别保留，等价表达由独立重解与编辑裁决对照登记。
