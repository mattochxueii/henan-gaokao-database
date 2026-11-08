"""Reproduce the Phase4 editorial audit, using explicit per-item AI judgments.

No original source text is copied into the public audit. Dimensions and time bands
are design judgments, not measured student difficulty or an automatic score rule.
"""

import bootstrap
from collections import Counter
import json
import re
import statistics

from analysis_db import fingerprint, research
from gaokao import ROOT, digest, read_json, require
from storage import atomic_json


# dimensions: knowledge, condition comprehension, modeling, logical reasoning,
# calculation, integration. Each is ordinal 1..5, judged from this item's content.
# level is an independent overall judgment, not an average of those dimensions.
# time = estimated student minutes; points = rough workload band for an isolated
# practice item, NOT a replacement for the established 150-point paper blueprint.
JUDGMENTS = {
    "sequence10": [
        (
            "211221",
            2,
            "3-5",
            "4-6",
            "rewrite",
            "分式数列求和",
            "间隔两项的裂项与四个边界项是核心，题前已告知残项机制；只求一个和，10分偏重。",
            True,
        ),
        (
            "211232",
            3,
            "5-7",
            "6-10",
            "rewrite",
            "等差权重与等比项求和",
            "需组织错位相减或等价递推，工作量高于普通等比和，10分上沿可讨论；导语只是在重复数学对象，不宜误判为已泄露具体方法。",
            False,
        ),
        (
            "222332",
            3,
            "6-8",
            "8-10",
            "rewrite",
            "变系数一阶递推",
            "须识别适当归一化并控制初值，具有实际转化门槛；可保留数学结构，但不能打印移项为0的程序关系。",
            False,
        ),
        (
            "222322",
            3,
            "4-6",
            "6-8",
            "rewrite",
            "交错增量递推",
            "奇偶模式或归纳可得到通项，初值与符号是推理重点；单一通项任务不足以稳定支持10分。",
            False,
        ),
        (
            "211221",
            2,
            "3-4",
            "4-6",
            "rewrite",
            "分式有限积",
            "分成两组相邻比后直接约消，题前已经说明首尾保留；10分明显偏重。",
            True,
        ),
        (
            "211211",
            2,
            "2-4",
            "3-5",
            "rewrite",
            "根式数列求和",
            "有理化后逐项抵消，突破口单一且计算很短；10分与实际工作量不匹配。",
            False,
        ),
        (
            "211221",
            2,
            "3-4",
            "4-6",
            "reclassify_and_rewrite",
            "二项式系数",
            "实际任务只是乘积多项式的一项系数，没有数列的结构研究；专题主标签应归排列组合，不能计作数列核心覆盖。",
            False,
        ),
        (
            "112211",
            1,
            "2-3",
            "3-5",
            "rewrite",
            "等差中项与平方和",
            "条件已直接给出两个低次方程，中心项先确定后只剩正根筛选；10分过重，原始方程组重复自然条件。",
            False,
        ),
        (
            "222222",
            2,
            "4-6",
            "5-8",
            "rewrite",
            "组合计数与有限和",
            "可用组合恒等式或多项式求和，但新旧编号叙述费解；应明确第k项对象、范围及空和边界。",
            False,
        ),
        (
            "222232",
            3,
            "5-8",
            "7-10",
            "rewrite",
            "奇数平方和及比较",
            "第二问直接展示第一问的闭式答案，使求和突破口失去考查意义；应改为以S_n表述比较，而不是写出结果。",
            False,
        ),
    ],
    "derivative10": [
        (
            "212322",
            2,
            "4-6",
            "5-8",
            "rewrite",
            "区间单调与参数",
            "参数界来自导数在整段的符号；第二问仅代入边界参数，几乎没有新推理。题前已提示约束机制。",
            True,
        ),
        (
            "212322",
            2,
            "4-6",
            "5-8",
            "rewrite",
            "对数基本不等式与参数界",
            "两问实质上是同一个全域下界的两种表述，不能因有两个任务就增加难度；需重排为真正递进的设问。",
            False,
        ),
        (
            "212322",
            3,
            "5-7",
            "7-10",
            "rewrite",
            "端点与驻点比较",
            "导数分段、端点比较和取值位置形成完整链条，适合作为中档练习；导语直接指出端点竞争，应删除。",
            True,
        ),
        (
            "212222",
            2,
            "4-6",
            "5-8",
            "redesign",
            "对数切线界",
            "第一问直接给导数方程，第二问又给差函数，学生无需建立切线与不等式的联系；应从同一原函数发问。",
            True,
        ),
        (
            "222332",
            3,
            "6-9",
            "8-11",
            "rewrite",
            "切线条件逆求参数与最值",
            "第二问显式写出恢复后的系数，泄露第一问答案。应沿用f(x)而非把数值系数代入题面。",
            False,
        ),
        (
            "212222",
            2,
            "3-5",
            "4-7",
            "redesign",
            "导数零点与极值辨析",
            "题前已经告诉考生驻点不保证极值；第二问只是把1代入导数，且“指定值1”未说明是自变量。",
            True,
        ),
        (
            "222322",
            3,
            "5-7",
            "6-9",
            "rewrite",
            "无穷区间单调参数",
            "必要性涉及无穷区间而非只查有限端点，有合理推理价值；导语明说极限决定参数界，削弱关键识别。",
            True,
        ),
        (
            "212322",
            2,
            "4-6",
            "5-8",
            "rewrite",
            "指数基本不等式",
            "一次导数符号分析可完成；曲线与切线的结论可作为合法证明目标，不应把目标本身误判为方法泄露。应明确实数量词，10分仍需依据。",
            False,
        ),
        (
            "222333",
            3,
            "7-10",
            "8-11",
            "rewrite",
            "多项式零点与单调区间",
            "因式分解与导数分区有真实工作量，但两问更应研究零点分布和函数变化的联系，不能只并排列计算任务。",
            False,
        ),
        (
            "212222",
            2,
            "3-5",
            "4-7",
            "redesign",
            "正比例与反比例的最优界",
            "两问重复最小值结论；开无穷区间没有最大值，“求最大值及位置”应改为存在性判断，不能暗示一定取得。",
            False,
        ),
    ],
    "fullA": [
        (
            "111111",
            1,
            "1-2",
            "5-5",
            "rewrite",
            "复数模",
            "一次模的运算即可，作为前部5分基础题可接受；不能在题前提醒分子分母的模。",
            True,
        ),
        (
            "122221",
            2,
            "2-3",
            "5-5",
            "rewrite",
            "无放回组合计数",
            "自然叙述为无序选取，内部用x<y代表组合可等价，但打印“有序结果数”会使对象混乱；必须统一抽取方式。",
            False,
        ),
        (
            "212222",
            2,
            "2-3",
            "5-5",
            "rewrite",
            "向量夹角余弦平方",
            "内积、模与平方的区分有基本考查价值；“近乎垂直”和注意平方是多余提示。",
            True,
        ),
        (
            "122222",
            2,
            "2-4",
            "5-5",
            "rewrite",
            "条件概率",
            "条件样本空间缩小与目标事件计数有明确含义，5分合理；只需保留掷骰情境，删除变量取值清单与逻辑操作符。",
            False,
        ),
        (
            "212222",
            2,
            "2-4",
            "5-5",
            "rewrite",
            "三角函数区间最值",
            "角区间限制与峰值位置形成中低档单选，5分可接受；不应直接提示使用区间位置限制范围。",
            True,
        ),
        (
            "222232",
            2,
            "3-5",
            "5-5",
            "rewrite",
            "圆的弦长",
            "直线、圆和弦的数量关系需要转化，5分合理；应直接给两曲线方程及交点名，避免“指定交点量”。",
            False,
        ),
        (
            "211211",
            1,
            "1-2",
            "5-5",
            "rewrite",
            "复合函数求导",
            "作为基础5分可接受；“指定值1”在考生题面上不能唯一表达求f'(1)，导语又透露链式求导。",
            True,
        ),
        (
            "222232",
            2,
            "3-5",
            "5-5",
            "rewrite",
            "多项式展开系数",
            "需区分形成三次项的不同组合，有一定计数转化；题前列贡献路径会削弱考查。",
            True,
        ),
        (
            "111211",
            1,
            "2-3",
            "6-6",
            "redesign",
            "数列性质多选",
            "同一数列可做基础多选，但当前主要是直接恒等式和显然错误等式；整卷多选梯度不足，需加入有约束的求和或存在性性质。",
            False,
        ),
        (
            "211211",
            1,
            "2-3",
            "6-6",
            "redesign",
            "同一函数的多性质",
            "同一函数对象是可取的，但四项只轮流求导和点值；可保留一题基础多选定位，不能整组都停留于此。",
            False,
        ),
        (
            "211211",
            1,
            "2-3",
            "6-6",
            "redesign",
            "空间向量关系",
            "四项仅换向量做零内积/平行判断，没有统一空间构型，6分多选的综合价值偏低。",
            False,
        ),
        (
            "111111",
            1,
            "1-2",
            "5-5",
            "rewrite",
            "样本方差",
            "基础填空5分可接受，但样本列表不应采用Python方括号，均值成对和分母提示均应移入解析。",
            True,
        ),
        (
            "212222",
            2,
            "2-4",
            "5-5",
            "rewrite",
            "通项化简与等比求和",
            "需要先化简通项再求和，5分合适；附加“n为正整数”与固定上限五项无关，应删除无用变量。",
            True,
        ),
        (
            "111111",
            1,
            "1-2",
            "5-5",
            "rewrite",
            "点到直线距离",
            "前部基础填空可接受，导语只是重复目标量而非新增条件；用点名和直线名直接设问即可。",
            False,
        ),
        (
            "122222",
            2,
            "5-8",
            "6-9",
            "replace_for_slot",
            "有限条件概率与期望",
            "16个基本结果上的三次计数/平均，期望又可由对称性直接得到。13分槽位应重设计分布或情境建模，不只是增加小问。",
            False,
        ),
        (
            "222232",
            2,
            "6-9",
            "7-10",
            "replace_for_slot",
            "空间向量与距离、角",
            "坐标直接给齐，两问共享法向量但都为例行公式，15分与构型推理不足。应补实质几何条件、证明和后续关联。",
            True,
        ),
        (
            "222333",
            3,
            "8-12",
            "9-13",
            "redesign_for_slot",
            "非齐次递推及加权和",
            "通项与加权和有实际联系，但题前已明示消去非齐次项；若保留15分还需增加有意义的界或条件研究。",
            True,
        ),
        (
            "211222",
            2,
            "4-7",
            "5-8",
            "replace_for_slot",
            "椭圆点距最值",
            "已给完整椭圆又问半轴，题中直接给参数表示、代换和距离化简。17分压轴定位失真，需要重构条件与关联设问。",
            True,
        ),
        (
            "222332",
            3,
            "7-10",
            "8-12",
            "replace_for_slot",
            "导数参数与多项式不等式",
            "三问都是同一简单三次函数的导数或因式分解，参数难点已由导语点出，17分压轴缺少充分依据。",
            True,
        ),
    ],
    "fullB": [
        (
            "111211",
            1,
            "1-2",
            "5-5",
            "rewrite",
            "二次方程与区间筛选",
            "作为5分基础单选合理，但集合情境没有真正参与推理；可直接自然表达求区间内的根。",
            False,
        ),
        (
            "111211",
            1,
            "1-2",
            "5-5",
            "rewrite",
            "复数实数条件",
            "一次展开后取虚部为0，5分基础题合理；不应把Im函数调用直接写给考生替代中文条件。",
            False,
        ),
        (
            "111111",
            1,
            "1-2",
            "5-5",
            "rewrite",
            "样本中位数",
            "5分基础单选可以保留；提示中间两数会泄方法，数据应自然列示而非程序列表。",
            True,
        ),
        (
            "211211",
            1,
            "1-2",
            "5-5",
            "rewrite",
            "特殊角与二倍角",
            "5分基础题可接受，但二倍角正是关键转化，题前不能直接说明。",
            True,
        ),
        (
            "111211",
            1,
            "1-2",
            "5-5",
            "rewrite",
            "椭圆顶点与交点",
            "水平切线经过顶点，交点个数可直接识别，适合作为基础题；“指定交点量”应删除。",
            False,
        ),
        (
            "122222",
            2,
            "2-4",
            "5-5",
            "rewrite",
            "条件概率的并事件",
            "条件事件涉及至少一次并需避免重复计数，5分合理；自然掷骰叙述已足够，不能追加模运算和逻辑连接符。",
            False,
        ),
        (
            "111211",
            1,
            "1-2",
            "5-5",
            "rewrite",
            "有限积约消",
            "固定四项的计算短，5分可作基础；导语泄露末端保留规律，且无用n条件应去掉。",
            True,
        ),
        (
            "211211",
            1,
            "1-2",
            "5-5",
            "rewrite",
            "商函数导数值",
            "5分基础题可保留，必须把“指定值0”改成求f'(0)，不要提前提示商法则。",
            True,
        ),
        (
            "111211",
            1,
            "2-3",
            "6-6",
            "redesign",
            "实数恒等式多选",
            "所谓正交单位基并未增加数学约束，四项仍是基础恒等式，缺少高考数学多性质问题的层次。",
            False,
        ),
        (
            "111111",
            1,
            "1-2",
            "6-6",
            "redesign",
            "椭圆点的检验",
            "同一曲线是共同对象，但四次代入同一方程的考查几乎完全重复，整卷6分多选不宜如此配置。",
            False,
        ),
        (
            "122221",
            2,
            "2-4",
            "6-6",
            "redesign",
            "伯努利事件与条件概率",
            "同一两次0-1试验可作为基础多选，但样本空间极小，四项未构成递进，宜加入真实事件关系或保留为唯一基础多选。",
            False,
        ),
        (
            "111111",
            1,
            "1-2",
            "5-5",
            "rewrite",
            "简单二项计数",
            "三个位置恰有两个1可直接组合计数，5分基础填空合理；须说明0-1序列对象，不输出“有序结果数”。",
            False,
        ),
        (
            "211211",
            1,
            "1-3",
            "5-5",
            "rewrite",
            "乘积与对数求导",
            "基本求导5分可接受；指定值1不够明确且导语提醒两因子贡献。",
            True,
        ),
        (
            "212222",
            2,
            "2-4",
            "5-5",
            "rewrite",
            "向量与三角形面积",
            "可用内积与面积公式联系，5分合适；只给向量应明确所张三角形，不先提醒面积比例。",
            True,
        ),
        (
            "211221",
            2,
            "3-5",
            "4-7",
            "replace_for_slot",
            "三角恒等式与区间最值",
            "第一问只是基本平方和恒等式，第二问一次和差化积即可。13分应增加有实质条件的三角形或参数问题。",
            True,
        ),
        (
            "122232",
            2,
            "5-8",
            "7-10",
            "replace_for_slot",
            "组合选择、条件概率与期望",
            "只需列出10种组合即可完成三问，15分偏重；应加入分布建模或参数与决策层次，而非重印样本空间。",
            False,
        ),
        (
            "222333",
            3,
            "8-12",
            "10-14",
            "redesign_for_slot",
            "交错递推与分组求和",
            "通项识别和偶数项前缀和有关联，具中档价值，但导语已点出奇偶抵消，15分仍需校准或增加实质推理。",
            True,
        ),
        (
            "212232",
            2,
            "4-7",
            "5-9",
            "replace_for_slot",
            "空间距离与动点最值",
            "题面直接给距离平方化简式，第3问只是第2问零距离情形；17分应由学生建立关系并增加几何综合。",
            True,
        ),
        (
            "222332",
            3,
            "6-9",
            "7-11",
            "replace_for_slot",
            "对数参数与基本不等式",
            "区间导数参数和全域对数界是两道常规练习，关联没有深入到参数分类或根的相互制约，17分缺依据。",
            True,
        ),
    ],
    "mixed50": [
        (
            "111211",
            1,
            "1-2",
            "5-5",
            "rewrite",
            "复数幂",
            "5分基础单选合理；周期与系数提示不应放在考生题面。",
            True,
        ),
        (
            "122211",
            1,
            "1-2",
            "5-5",
            "rewrite",
            "条件概率基础",
            "自然条件和问题本已清楚，内部变量、或运算和目标事件重复叙述会降低可读性。",
            False,
        ),
        (
            "111111",
            1,
            "1-2",
            "5-5",
            "rewrite",
            "特殊角函数值",
            "5分基础单选合理；无需预先提醒互余关系。",
            True,
        ),
        (
            "111211",
            1,
            "1-2",
            "5-5",
            "rewrite",
            "相邻幂的有限和",
            "固定六项可直接约消，5分作为基础题可接受，但导语已指明机制，无用n条件也须删除。",
            True,
        ),
        (
            "212222",
            2,
            "4-6",
            "5-8",
            "redesign",
            "两类函数的导数性质",
            "有理函数最值与另一二次函数参数范围互不依赖，是两个练习的拼接；10分并非仅因有两问就成立。",
            True,
        ),
        (
            "222232",
            3,
            "5-8",
            "7-10",
            "rewrite",
            "空间向量面积与线面角",
            "共享两向量与平面，可组织成相互关联的小题；10分可讨论，但应自然定义构型而非输出操作标签。",
            False,
        ),
        (
            "212222",
            2,
            "3-5",
            "5-8",
            "redesign",
            "椭圆中心弦",
            "第1问数交点几乎无门槛，第2问是一次联立后的弦长，10分偏重；不应提示弦经过中心作为解题路线。",
            True,
        ),
    ],
    "acceptance5": [
        (
            "222322",
            3,
            "5-8",
            "6-9",
            "rewrite",
            "阶乘权重递推",
            "归一化有合理转化门槛，但题前已告诉阶乘权重；10分需重新校准，数列必须用下标。",
            True,
        ),
        (
            "222222",
            2,
            "4-6",
            "5-8",
            "rewrite",
            "等比关系与方程筛选",
            "列式和正根筛选本应由考生完成，内部方程组直接暴露等比模型；单一求值的10分偏重。",
            False,
        ),
        (
            "212322",
            2,
            "4-6",
            "5-8",
            "rewrite",
            "四次式非负与取等",
            "可通过因式分解或导数证明，10分需依据；量词与变量范围应明确，题前唯一取等提示应删除。",
            True,
        ),
        (
            "212322",
            2,
            "4-6",
            "5-8",
            "rewrite",
            "有界区间参数单调性",
            "导数符号与端点必要性有逻辑要求，但10分略重；不应在题前提示参数系数变化。",
            True,
        ),
        (
            "121211",
            1,
            "2-3",
            "3-5",
            "redesign",
            "不相邻位置计数",
            "只求长度4的合法串，可直接穷举或分类，10分明显失衡；一般n记号未发挥作用，“目标事件为1=1”属发布阻断。",
            False,
        ),
    ],
}

CONCEPTS = {
    "sequence10": [
        ["分式分解", "有限和边界"],
        ["等比数列", "加权求和"],
        ["初值约束", "变系数递推", "归一化差分"],
        ["奇偶讨论", "交错递推"],
        ["有限积", "相邻因子约消"],
        ["根式有理化", "有限和"],
        ["二项式系数", "多项式乘积"],
        ["等差中项", "平方和关系", "正数筛选"],
        ["组合数", "有限和恒等式"],
        ["平方和", "多项式比较", "取等条件"],
    ],
    "derivative10": [
        ["导数符号", "有界区间参数"],
        ["对数最值", "恒成立参数"],
        ["乘积求导", "极值与端点"],
        ["切线斜率", "对数不等式"],
        ["切线条件", "待定系数", "闭区间最值"],
        ["单调性", "驻点与极值"],
        ["无穷区间符号", "参数必要性"],
        ["指数导数", "恒非负取等"],
        ["多项式零点", "导数分区"],
        ["最优下界", "极值存在性"],
    ],
    "fullA": [
        ["复数模"],
        ["无序选择", "限制计数"],
        ["向量内积", "向量模", "夹角"],
        ["条件样本空间", "条件概率"],
        ["三角变换", "受限区间最值"],
        ["直线与圆", "弦长"],
        ["复合函数求导", "导数值"],
        ["多项式系数", "分类计数"],
        ["数列通项代入", "恒等式"],
        ["多项式求导", "函数点值"],
        ["向量内积", "向量平行"],
        ["均值", "方差"],
        ["通项化简", "等比求和"],
        ["点到直线距离"],
        ["有限样本空间", "条件概率", "期望"],
        ["平面法向量", "点面距离", "线面角"],
        ["非齐次递推", "通项", "加权有限和"],
        ["椭圆方程", "点距表达", "二次函数最值"],
        ["参数导数", "单调性", "多项式非负"],
    ],
    "fullB": [
        ["二次方程", "区间筛根"],
        ["复数乘法", "实数条件"],
        ["中位数"],
        ["特殊角", "二倍角"],
        ["椭圆顶点", "交点个数"],
        ["并事件", "条件概率"],
        ["有限积约消"],
        ["商函数求导", "导数值"],
        ["实数恒等式", "平方非负"],
        ["点与椭圆"],
        ["独立事件", "条件概率"],
        ["组合计数"],
        ["乘积求导", "对数函数"],
        ["向量模与内积", "三角形面积"],
        ["三角恒等式", "区间最值"],
        ["组合选择", "条件概率", "期望"],
        ["交错递推", "通项", "分组求和"],
        ["平面方程", "点面距离", "多项式最值"],
        ["对数导数", "区间参数", "全域不等式"],
    ],
    "mixed50": [
        ["复数幂"],
        ["条件概率"],
        ["特殊角函数值"],
        ["有限和约消"],
        ["有理函数最值", "二次函数参数"],
        ["向量面积", "平面法向量", "线面角"],
        ["直线与椭圆", "中心弦长"],
    ],
    "acceptance5": [
        ["阶乘", "非齐次递推", "归一化"],
        ["等比关系", "低次方程", "正根筛选"],
        ["多项式非负", "取等条件"],
        ["对数导数", "有界区间参数"],
        ["不相邻位置限制", "分类计数"],
    ],
}

DISTRACTOR_NOTES = {
    ("fullA", 1): (
        "plausible_paths",
        "模之差、只算分子模平方、漏去分子模平方均能得到相应值；认知归因仍只是设计假设。",
    ),
    ("fullA", 2): (
        "plausible_paths",
        "忽略限制得15，只数两数均大于2得6，重复计顺序得18，与各选项值相符。",
    ),
    ("fullA", 3): (
        "needs_precision",
        "1/10和1/5可分别来自遗漏一个模平方，但原“模平方混用”“模长因子”措辞不够具体，应写出错误分母。",
    ),
    ("fullA", 4): (
        "needs_precision",
        "2/5与有序分子、无序分母混用相符，1/6来自不条件化；1/3的“漏数部分条件结果”未给实际漏数集合。",
    ),
    ("fullA", 5): (
        "needs_precision",
        "端点值是可信干扰；sqrt(3)应解释为分别取两项在区间内的最大值但不能同取，而非泛称叠加振幅；1的错误过程未明确。",
    ),
    ("fullA", 6): (
        "needs_precision",
        "9可来自只留一个坐标差平方，3sqrt(2)是距离；6应解释为两坐标差绝对值相加，简单说“未平方”并不充分。",
    ),
    ("fullA", 7): (
        "plausible_paths",
        "漏乘内层导数得1/2，漏除分母得2，误把偶函数任意点导数视为0也有明确误区。",
    ),
    ("fullA", 8): (
        "needs_precision",
        "12与4分别漏计一种形成路径；24还需明确只计三次一次项且重复顺序，否则若再计2+1会得到36。",
    ),
    ("fullB", 1): (
        "metadata_inconsistent",
        "两根平均为-1，不能由“误用根的平均”得到选项1/2；另外两个错误路径过于笼统。",
    ),
    ("fullB", 2): (
        "needs_precision",
        "负号与系数倒置可产生-2和1/2；选项1若来自把2i写为i应明说，“漏掉一个虚部贡献”按字面会得到0或不成方程。",
    ),
    ("fullB", 3): (
        "metadata_inconsistent",
        "左右中项8和5是合理干扰；极差12-2=10，不是选项9，原归因无法产生所列选项。",
    ),
    ("fullB", 4): (
        "metadata_inconsistent",
        "1/2与sqrt(3)/4可由明确二倍角错误产生；(sqrt(3)-1)/4既非sin15°也非cos15°，不能称只取一个特殊角因子。",
    ),
    ("fullB", 5): (
        "needs_precision",
        "把二重根误作两点的选项2有明确路径；选项4的“重复对称点”尚未说明哪些点满足水平直线，解释较弱。",
    ),
    ("fullB", 6): (
        "plausible_paths",
        "6/11重复计入(6,6)，1/4忽略条件，3/11只保留指定一次为6的有利结果，均能产生对应错误值。",
    ),
    ("fullB", 7): (
        "plausible_paths",
        "只乘前两项、漏最后一项、只留首项分别得到1/5、1/7、1/3，路径可以逐项复现。",
    ),
    ("fullB", 8): (
        "needs_precision",
        "商法则次序颠倒可得-1，只看分母导数可得0；选项2的“乘积法则并重复分子”缺少可复现的具体式子。",
    ),
    ("mixed50", 1): (
        "needs_precision",
        "4漏掉i²负号、-2未平方系数2均可复现；正2仅写“漏乘系数”不足以确定计算路径。",
    ),
    ("mixed50", 2): (
        "plausible_paths",
        "不条件化、条件分母少一、只留一个有利值分别可得1/3、2/3、1/4。",
    ),
    ("mixed50", 3): (
        "needs_precision",
        "漏加一项得1/2，把两项都误作sin60°得sqrt(3)；sqrt(3)/2的“混淆正余弦”还缺一步具体错误。",
    ),
    ("mixed50", 4): (
        "plausible_paths",
        "仅取末差、漏减首端、上限少一分别产生32、64、31，可逐式核查。",
    ),
}


def ability_basis(key, level, focus, concepts, hint):
    descriptions = {
        "knowledge": {
            1: "调用基本定义或直接公式，知识门槛低",
            2: "涉及高中常见性质及标准转化，未见超纲知识要求",
            3: "需熟练联系同模块多个性质，知识熟练度要求较高",
        },
        "condition_comprehension": {
            1: "对象和数值直接给定，无需从情境提取隐含关系",
            2: "需辨明范围、初值、抽样限制或量词，程序式重复另增无关阅读负担",
            3: "需要同时处理多层条件，不能把字面冗长当作数学理解难度",
        },
        "modeling": {
            1: "已直接给数学对象或计算式，没有独立建立情境模型的要求",
            2: "有少量事件/几何/代数关系建构；纯符号转化不额外冒称现实情境建模",
            3: "需从情境构建并验证模型，而不是只代入已给公式",
        },
        "logical_reasoning": {
            1: "主要是直接识别或一次回代，没有实质分类论证",
            2: "需一次转化、分类或边界核对，推理链较短",
            3: "需要组织参数必要性、通项关系或多个区间的完整论证",
        },
        "calculation": {
            1: "少量心算或一次代入即可完成",
            2: "少量展开、求导、有限枚举或短式化简，计算量中低",
            3: "需要若干有结构的求和、消元或区间计算，但没有靠繁算人为增难",
        },
        "integration": {
            1: "单一核心知识即可完成，重复代入不算知识综合",
            2: "存在相关概念联系，但多属同一模块，不能仅按标签数量夸大综合度",
            3: "前后关系可被后续任务使用，有一定联系深度；仍须区别实际关联和并排计算",
        },
    }
    basis = descriptions[key].get(level, "有较复杂的关联要求，具体以本题逐题说明核查")
    if key == "knowledge":
        return focus + "：" + basis + "。实际概念为" + "、".join(concepts) + "。"
    if key == "integration":
        return focus + "：" + basis + "。概念计数不是难度计分公式。"
    if key == "logical_reasoning" and hint:
        basis += "；当前导语暴露识别方向，实际考查会低于去掉提示后的设计意图"
    return focus + "：" + basis + "。"


def text_fields(candidate):
    result = [candidate.get("stem", "")]
    result.extend(r.get("text", "") for r in candidate.get("subquestions", []))
    for value in (candidate.get("options") or {}).values():
        result.append(value.get("text", "") if isinstance(value, dict) else value)
    return "\n".join(result)


def metrics(text):
    without_math = re.sub(r"\\\(.*?\\\)", "□", text, flags=re.S)
    return {
        "raw_characters_including_latex": len(text),
        "chinese_characters": len(re.findall(r"[\u4e00-\u9fff]", without_math)),
        "formula_delimiters": text.count(r"\("),
        "left_parenthesis_commands": text.count(r"\left("),
        "machine_terms": [
            term
            for term in (
                "目标事件",
                "指定值",
                "有序结果数",
                "求几何量",
                "未知量",
                "附加限制",
                "指定交点量",
            )
            if term in text
        ],
    }


def band(value):
    return [int(v) for v in value.split("-")]


def source_record(row):
    c = row["candidate"]
    original_module = row["analysis"]["knowledge"]["module"]
    audited_module = (
        "概率统计"
        if row["id"] == "2025-cn-math-national-1:q015"
        and "独立性检验" in row["analysis"]["knowledge"]["primary"]
        else original_module
    )
    numbers = [r["number"] for r in c.get("subquestions", [])]
    top_level = {re.match(r"\d+", n).group() for n in numbers if re.match(r"\d+", n)}
    leaf_numbers = [
        n for n in numbers if not any(other.startswith(n + "(") for other in numbers)
    ]
    return {
        "question_id": row["id"],
        "year": row["year"],
        "kind": row["kind"],
        "points": row["points"],
        "module": original_module,
        "audited_module": audited_module,
        "module_review_note": "原主模块误标；仅本次复核映射，原分析不改动"
        if audited_module != original_module
        else "本次未发现主模块冲突",
        "candidate_version": c["version"],
        "candidate_sha256": fingerprint(c),
        "source_id": c["source_id"],
        "source_url": c["source_url"],
        "pages": list(range(c["page"], c.get("end_page", c["page"]) + 1)),
        "source_files": c["source_files"],
        "subquestion_count": len(leaf_numbers),
        "top_level_subquestion_count": len(top_level),
        "subquestion_record_count": len(numbers),
        "subquestion_count_basis": "仅统计叶子设问；有子问的条件容器不重复计问",
        "metrics": metrics(text_fields(c)),
        "official_body_confirmed": False,
        "analysis_key_idea": row["analysis"]["key_idea"],
        "candidate_limit": "第三方转写候选，非官方考场卷逐字认证；图表内容不计入文本统计",
    }


def main():
    source_rows = research(ROOT)
    sources = [source_record(row) for row in source_rows]
    require(len(sources) == 38, "需要实际读取38题版本绑定候选")
    dimensions = (
        "knowledge",
        "condition_comprehension",
        "modeling",
        "logical_reasoning",
        "calculation",
        "integration",
    )
    audits = []
    for experiment, judgments in JUDGMENTS.items():
        path = ROOT / "experiments/phase3/deliveries" / experiment / "run.json"
        run = read_json(path)
        require(len(judgments) == len(run["questions"]), "逐题判断缺失")
        for q, supplied in zip(run["questions"], judgments):
            dims, level, time, points, action, focus, note, hint = supplied
            concepts = CONCEPTS[experiment][q["order"] - 1]
            require(
                len(dims) == 6 and all(1 <= int(v) <= 5 for v in dims), "能力维度错误"
            )
            measured = metrics(text_fields(q))
            issues = []
            if measured["left_parenthesis_commands"] >= 4:
                issues.append(
                    {
                        "code": "AST_parentheses",
                        "severity": "major",
                        "evidence": "显式嵌套括号命令数="
                        + str(measured["left_parenthesis_commands"]),
                        "basis": "应由题面写作层选取规范数学记号，非把AST节点逐层包裹",
                    }
                )
            if measured["machine_terms"]:
                issues.append(
                    {
                        "code": "internal_instruction",
                        "severity": "major",
                        "evidence": measured["machine_terms"],
                        "basis": "内部求解任务标签不能直接作为考生设问",
                    }
                )
            if hint:
                issues.append(
                    {
                        "code": "solution_route_disclosed",
                        "severity": "major",
                        "evidence": q["problem"].get("context", "")[:120],
                        "basis": "导语提前提供方法或关键识别；具体判断以逐题说明为准",
                    }
                )
            if q["kind"] in ("single_choice", "fill_in") and "（1）" in q["stem"]:
                issues.append(
                    {
                        "code": "unnecessary_subquestion_marker",
                        "severity": "minor",
                        "evidence": "唯一设问仍冠以（1）",
                        "basis": "不必要的任务包装，改为普通完整设问",
                    }
                )
            if q["kind"] == "multiple_choice":
                issues.append(
                    {
                        "code": "mechanical_claims",
                        "severity": "major",
                        "evidence": "四项被包装成重复的判断/计算指令",
                        "basis": "多选本质仍判断真值，问题在于当前对象、条件与推理层次不足，不是禁止基础多选",
                    }
                )
            if "1= 1" in q["stem"] or "1=1" in q["stem"]:
                issues.append(
                    {
                        "code": "tautological_target",
                        "severity": "blocker",
                        "evidence": "目标事件为1=1",
                        "basis": "程序占位事件没有考生意义，禁止发布",
                    }
                )
            if (experiment, q["order"]) in (("sequence10", 10), ("derivative10", 5)):
                issues.append(
                    {
                        "code": "later_part_reveals_earlier_answer",
                        "severity": "blocker",
                        "evidence": note,
                        "basis": "后问明列前问待求结果，破坏实质考查",
                    }
                )
            if (experiment, q["order"]) == ("derivative10", 10):
                issues.append(
                    {
                        "code": "extremum_existence_ambiguous",
                        "severity": "major",
                        "evidence": "开无穷区间实际没有最大值，却要求最大值及取到位置",
                        "basis": "需明确存在性，不得暗示一定取得",
                    }
                )
            point_band = band(points)
            aligned = point_band[0] <= q["points"] <= point_band[1]
            option_review = None
            if q["kind"] == "single_choice":
                status, detail = DISTRACTOR_NOTES[(experiment, q["order"])]
                option_review = {
                    "status": status,
                    "basis": detail,
                    "student_error_empirically_validated": False,
                    "design_hypothesis_only": True,
                    "published_option_paths": {
                        label: {
                            "semantic_value": value["semantic_value"],
                            "error_path": value["error_path"],
                        }
                        for label, value in q["options"].items()
                    },
                }
                if status == "metadata_inconsistent":
                    issues.append(
                        {
                            "code": "distractor_error_path_inconsistent",
                            "severity": "major",
                            "evidence": detail,
                            "basis": "错因必须能实际产生该选项值，不能只非空或满足取值范围",
                        }
                    )
            if not aligned:
                issues.append(
                    {
                        "code": "score_depth_mismatch",
                        "severity": "major",
                        "evidence": {
                            "original_points": q["points"],
                            "isolated_practice_workload_band": point_band,
                        },
                        "basis": note,
                    }
                )
            audited_module = (
                "排列组合"
                if (experiment, q["order"]) == ("sequence10", 7)
                else q["module"]
            )
            comparable = [
                r
                for r in sources
                if r["audited_module"] == audited_module and r["kind"] == q["kind"]
            ]
            if not comparable:
                comparable = [
                    r for r in sources if r["audited_module"] == audited_module
                ]
            comparable = comparable[:4]
            audits.append(
                {
                    "question_id": q["id"],
                    "experiment": experiment,
                    "order": q["order"],
                    "original_kind": q["kind"],
                    "original_points": q["points"],
                    "original_design_difficulty": q["difficulty"],
                    "candidate_sha256": q["generation"]["raw_candidate_sha256"],
                    "rendered_question_sha256": fingerprint(q),
                    "source_run": path.relative_to(ROOT).as_posix(),
                    "source_run_sha256": digest(path),
                    "focus": focus,
                    "module": q["module"],
                    "metrics": measured,
                    "issues": issues,
                    "distractor_review": option_review,
                    "abilities": {
                        key: {
                            "ordinal_1_to_5": int(value),
                            "basis": ability_basis(
                                key, int(value), focus, concepts, hint
                            ),
                        }
                        for key, value in zip(dimensions, dims)
                    },
                    "knowledge_integration": {
                        "audited_concepts": concepts,
                        "concept_count": len(concepts),
                        "audited_modules": ["排列组合"]
                        if (experiment, q["order"]) == ("sequence10", 7)
                        else (
                            [q["module"], "函数与导数"]
                            if (experiment, q["order"])
                            in (("fullA", 18), ("fullB", 18))
                            else [q["module"]]
                        ),
                        "basis": note,
                        "count_is_not_difficulty": True,
                    },
                    "breakthrough_visibility": {"route_disclosed": hint, "basis": note},
                    "overall_difficulty": {
                        "ordinal_1_to_5": level,
                        "basis": note,
                        "method": "逐题阅读实际条件、设问及数学结构后独立AI判断，不由题号或任务数推断",
                        "empirical": False,
                    },
                    "estimated_minutes": band(time),
                    "time_basis": "掌握目标知识的高中生无方法提示时的AI估计，未做考生作答实测",
                    "score_review": {
                        "supported_by_current_task": aligned,
                        "isolated_practice_workload_band": point_band,
                        "basis": note,
                        "not_a_new_exam_scoring_rule": True,
                        "full_paper_action": "保留标准槽位分值时应重设计任务，不得仅降低分值后仍声称满足150分卷型"
                        if experiment in ("fullA", "fullB") and not aligned
                        else "需结合整卷位置、预估时间与考查层次审核",
                    },
                    "recommendation": action,
                    "review_note": note,
                    "comparison_sources": [
                        {
                            "question_id": r["question_id"],
                            "candidate_sha256": r["candidate_sha256"],
                            "source_id": r["source_id"],
                            "kind": r["kind"],
                            "points": r["points"],
                            "subquestion_count": r["subquestion_count"],
                            "metrics": r["metrics"],
                        }
                        for r in comparable
                    ],
                    "direct_module_reference_available": bool(comparable),
                    "reference_gap": "38题样本无排列组合主模块直接对应；不得伪造同知识点对照，需要课程依据或独立辅助样本"
                    if not comparable
                    else None,
                    "source_style_comparison": {
                        "language": "对照候选的对象—条件—设问组织方式；本题具体多余包装见issues，空列表不代表已通过只看PDF的独立审查",
                        "depth": "仅共享模块不代表难度相同；本题的逻辑与分值以逐题review_note为依据",
                        "selection_basis": "优先同模块同题型，缺少时仅同模块；不是声称每个对照都同一知识点或相同数学结构",
                        "sample_limit": "仅两套第三方版本候选；多选含基础题，不强制所有多选均综合高难",
                    },
                    "reviewer": "independent_host_AI_editorial_audit",
                    "model_version": "not_exposed_by_host",
                    "human_reviewed": False,
                    "official_exam_style_certified": False,
                }
            )
    require(
        len(audits) == 70 and len({r["question_id"] for r in audits}) == 70,
        "70题不唯一或未覆盖",
    )
    source_statistics = {}
    for kind in ("single_choice", "multiple_choice", "fill_in", "constructed_response"):
        rows = [r for r in sources if r["kind"] == kind]
        source_statistics[kind] = {
            "count": len(rows),
            "raw_length_median": statistics.median(
                r["metrics"]["raw_characters_including_latex"] for r in rows
            ),
            "chinese_length_median": statistics.median(
                r["metrics"]["chinese_characters"] for r in rows
            ),
            "subquestion_counts": dict(Counter(r["subquestion_count"] for r in rows)),
            "top_level_subquestion_counts": dict(
                Counter(r["top_level_subquestion_count"] for r in rows)
            ),
            "points": dict(Counter(r["points"] for r in rows)),
            "machine_term_count": sum(
                bool(r["metrics"]["machine_terms"]) for r in rows
            ),
        }
    summary = {
        "reviewed": len(audits),
        "source_candidates_read": len(sources),
        "score_depth_mismatch": sum(
            not r["score_review"]["supported_by_current_task"] for r in audits
        ),
        "route_disclosure": sum(
            r["breakthrough_visibility"]["route_disclosed"] for r in audits
        ),
        "original_difficulty_distribution": dict(
            Counter(r["original_design_difficulty"] for r in audits)
        ),
        "reviewed_difficulty_distribution": dict(
            Counter(r["overall_difficulty"]["ordinal_1_to_5"] for r in audits)
        ),
        "recommendations": dict(Counter(r["recommendation"] for r in audits)),
        "issue_counts": dict(
            Counter(issue["code"] for r in audits for issue in r["issues"])
        ),
        "full_paper_constructed_response_recommendations": [
            {
                "id": r["question_id"],
                "points": r["original_points"],
                "action": r["recommendation"],
                "note": r["review_note"],
            }
            for r in audits
            if r["experiment"] in ("fullA", "fullB")
            and r["original_kind"] == "constructed_response"
        ],
        "quality_gate": "旧70题均不可沿用第三阶段的程序通过标签视作已完成本轮考生可读性验收；历史原件不修改",
    }
    generated_statistics = {}
    for label, pool in (
        ("all_70", audits),
        (
            "two_full_papers_38",
            [r for r in audits if r["experiment"] in ("fullA", "fullB")],
        ),
    ):
        generated_statistics[label] = {}
        for kind in (
            "single_choice",
            "multiple_choice",
            "fill_in",
            "constructed_response",
        ):
            rows = [r for r in pool if r["original_kind"] == kind]
            if not rows:
                continue
            generated_statistics[label][kind] = {
                "count": len(rows),
                "raw_length_median": statistics.median(
                    r["metrics"]["raw_characters_including_latex"] for r in rows
                ),
                "chinese_length_median": statistics.median(
                    r["metrics"]["chinese_characters"] for r in rows
                ),
                "left_parenthesis_commands_median": statistics.median(
                    r["metrics"]["left_parenthesis_commands"] for r in rows
                ),
                "machine_term_count": sum(
                    bool(r["metrics"]["machine_terms"]) for r in rows
                ),
            }
    atomic_json(
        ROOT / "reports/phase4-legacy-audit.json",
        {
            "schema_version": 1,
            "review_date": "2026-11-08",
            "scope": "第三阶段实际交付的70道AI题逐题编辑/能力审查",
            "summary": summary,
            "source_statistics": source_statistics,
            "generated_statistics": generated_statistics,
            "sources": sources,
            "questions": audits,
            "limits": [
                "本报告读了内部规格和解答记录，不是只看PDF的考生盲审；本轮新样卷另需独立盲审",
                "未进行考生实测或教师审定，难度与时间是有据的AI设计判断",
                "正式卷原文尚无命题机构确认，源文本有归一化转写痕迹",
                "未改动原始真题、旧70题及其历史记录",
            ],
        },
    )
    make_rules(sources, source_statistics)
    make_overrides(source_rows)
    make_markdown(summary, source_statistics, generated_statistics)
    print(json.dumps(summary, ensure_ascii=False))


def make_rules(sources, statistics_by_kind):
    byid = {r["question_id"]: r for r in sources}

    def evidence(*numbers):
        return [
            {
                k: byid[n][k]
                for k in (
                    "question_id",
                    "candidate_version",
                    "candidate_sha256",
                    "source_id",
                    "source_url",
                    "pages",
                )
            }
            for n in numbers
        ]

    rules = [
        {
            "id": "L01",
            "category": "engineering_requirement",
            "rule": "数学规格、AI中文题面、排版三层分离。考生题面不得由任务标签或AST字符串直接拼接。",
            "basis": "第四阶段用户要求与旧70题实际失败",
            "blocking": True,
        },
        {
            "id": "L02",
            "category": "editorial_requirement",
            "rule": "先定义数学对象和全部必要条件，再写明确设问；已给条件不在每个小问重新打印。",
            "evidence": evidence(
                "2025-cn-math-national-1:q016", "2026-cn-math-national-1:q017"
            ),
            "blocking": True,
        },
        {
            "id": "L03",
            "category": "editorial_requirement",
            "rule": "数列用下标；代数式用高中常见形式，去掉仅服务AST的括号和逐次乘法。不得通过化简把待求问题变成答案。",
            "evidence": evidence(
                "2025-cn-math-national-1:q016", "2026-cn-math-national-1:q007"
            ),
            "blocking": True,
        },
        {
            "id": "L04",
            "category": "editorial_requirement",
            "rule": "抽样、概率与计数必须交代对象、等可能性、是否放回、是否计顺序和事件；用题意对应的中文叙述，不打印目标事件占位真值。",
            "evidence": evidence(
                "2026-cn-math-national-1:q017", "2025-cn-math-national-1:q015"
            ),
            "blocking": True,
        },
        {
            "id": "L05",
            "category": "editorial_requirement",
            "rule": "导语不得告诉考生裂项、错位相减、恰当代换或关键推理结论；数学定义和必要情境不算提示。",
            "evidence": evidence(
                "2025-cn-math-national-1:q018", "2026-cn-math-national-1:q018"
            ),
            "blocking": True,
        },
        {
            "id": "L06",
            "category": "candidate_observation",
            "rule": "多选可考同一对象的多种性质，允许基础题；整组应有层次，不能四项反复做同一种代入。",
            "evidence": evidence(
                "2026-cn-math-national-1:q009",
                "2025-cn-math-national-1:q010",
                "2026-cn-math-national-1:q010",
            ),
            "not_universal_law": True,
            "blocking": False,
        },
        {
            "id": "L07",
            "category": "editorial_requirement",
            "rule": "解答题的小问围绕共同对象实质关联，可从求值/证明基础关系进入参数、存在性、范围或综合论证；后问不得明列前问待求答案。",
            "evidence": evidence(
                "2025-cn-math-national-1:q016",
                "2025-cn-math-national-1:q018",
                "2026-cn-math-national-1:q017",
            ),
            "blocking": True,
        },
        {
            "id": "L08",
            "category": "editorial_requirement",
            "rule": "变量范围、量词、端点和极值存在性须完整；f'(1)不能写成“指定值1”，新符号必须先定义。",
            "evidence": evidence(
                "2025-cn-math-national-1:q019", "2026-cn-math-national-1:q019"
            ),
            "blocking": True,
        },
        {
            "id": "L09",
            "category": "editorial_requirement",
            "rule": "13/15/17分解答槽位须由条件理解、建模、逻辑、运算、综合度、突破口与预计用时共同支持；题号和小问数量不能作依据。",
            "evidence": evidence(
                "2025-cn-math-national-1:q015",
                "2025-cn-math-national-1:q018",
                "2026-cn-math-national-1:q017",
            ),
            "blocking": True,
            "empirical_score_difficulty_relation": False,
        },
        {
            "id": "L10",
            "category": "engineering_requirement",
            "rule": "AI写作稿必须绑定数学规格哈希，并审查语义、完整性和题型；再对实际PDF/页面哈希做只看考生材料的独立审查，文本或排版变化作废旧审查。",
            "basis": "本阶段用户验收要求；不是由两套真题统计推导",
            "blocking": True,
        },
        {
            "id": "L11",
            "category": "editorial_requirement",
            "rule": "复杂逻辑条件可保留规范数学含义，但面向考生优先写成“至少一次”“恰有”“且/或”“对任意”等明确中文，不为去符号而改变事件。",
            "evidence": evidence(
                "2026-cn-math-national-1:q010",
                "2026-cn-math-national-1:q017",
                "2026-cn-math-national-1:q019",
            ),
            "blocking": True,
        },
        {
            "id": "L12",
            "category": "hypothesis_requiring_more_samples",
            "rule": "题面长度与结构只作同模块同题型对照，不设由两套候选导出的硬性字数、知识点比例或压轴套路。",
            "evidence": evidence(
                "2025-cn-math-national-1:q019", "2026-cn-math-national-1:q019"
            ),
            "blocking": False,
        },
        {
            "id": "L13",
            "category": "editorial_requirement",
            "rule": "每个干扰项的错误路径应能实际计算出该选项；不能只检查error_path非空，也不能把有理范围内任意值冒称典型错误。无考生错误样本实证时，认知归因仅为设计假设。",
            "basis": "本次旧选项审查发现fullB第3题所谓极差实际为10而非选项9等真实错配",
            "blocking": True,
            "student_error_empirically_validated": False,
        },
    ]
    atomic_json(
        ROOT / "analysis/language-rules.json",
        {
            "schema_version": 1,
            "version": "phase4-language-v1",
            "created_at": "2026-11-08",
            "author": "independent_host_AI_editorial_audit",
            "model_version": "not_exposed_by_host",
            "source_scope": {
                "papers": 2,
                "questions": 38,
                "official_body_confirmed_questions": 0,
                "originals_not_reproduced": True,
                "metric_scope": "仅统计版本绑定候选文本，不把归一化转写当作官方逐字卷面",
            },
            "official_language_requirements": [],
            "official_language_requirements_note": "未检索并核实官方题面写作规范文件；本规则不冒称官方语言标准。官方考试结构另见analysis/rules.json。",
            "rules": rules,
            "observed_statistics": statistics_by_kind,
            "rubric_dimensions": list(
                (
                    "knowledge",
                    "condition_comprehension",
                    "modeling",
                    "logical_reasoning",
                    "calculation",
                    "integration",
                    "breakthrough_visibility",
                    "estimated_minutes",
                    "source_level_difference",
                )
            ),
            "empirical_calibration": False,
            "remaining_review": "新试卷还必须数学核查、仅PDF独立可读性审查及教师审核；本规则自身不认证高考质量",
        },
    )


def make_overrides(source_rows):
    row = next(r for r in source_rows if r["id"] == "2025-cn-math-national-1:q015")
    require(
        "独立性检验" in row["analysis"]["knowledge"]["primary"],
        "模块覆盖的题意证据已变，需重新审核",
    )
    c = row["candidate"]
    atomic_json(
        ROOT / "analysis/review-overrides.json",
        {
            "schema_version": 1,
            "version": "phase4-reviewed-module-overrides-v1",
            "reviewed_at": "2026-11-08",
            "purpose": "保留原始38分析，对完全匹配的候选与分析版本应用可追溯复核覆盖",
            "overrides": [
                {
                    "question_id": row["id"],
                    "candidate_sha256": fingerprint(c),
                    "analysis_sha256": fingerprint(row["analysis"]),
                    "field": "knowledge.module",
                    "original_value": row["analysis"]["knowledge"]["module"],
                    "reviewed_value": "概率统计",
                    "evidence": {
                        "topic_summary": "人群抽样、二维列联表、独立性检验；属于统计推断，不属于集合或复数运算",
                        "original_primary_knowledge": row["analysis"]["knowledge"][
                            "primary"
                        ],
                        "source_id": c["source_id"],
                        "pages": list(
                            range(c["page"], c.get("end_page", c["page"]) + 1)
                        ),
                        "source_files": c["source_files"],
                    },
                    "reviewer": "independent_host_AI_editorial_audit",
                    "model_version": "not_exposed_by_host",
                    "human_reviewed": False,
                    "review_status": "ai_reviewed_version_bound",
                    "application_rule": "候选哈希、分析哈希与原字段值必须全部匹配才可应用；不回写或删除原始分析",
                }
            ],
        },
    )


def make_markdown(summary, stats, generated):
    text = """# 第四阶段：真题语言与旧70题对照

本报告实际通过research接口读取了38道版本绑定的2025/2026候选，逐题阅读第三阶段70题的实际题面。原始真题全文、页图、恢复密钥均未复制进本报告。旧70题未修改。

## 证据边界

2025材料是回忆重排候选，2026是第三方扫描候选；命题机构逐题确认仍为0。仓库结构化文本本身有归一化、缩写与图表定位，所以文本长度统计是候选转写统计，不能称为官方原卷的逐字语言统计。图表的信息量未计入字符。

每个对照源的ID、版本、候选哈希、来源链接、原文件哈希和页码见phase4-legacy-audit.json的sources。规则中的evidence逐条绑定来源，原有38题分析保留不动。

## 能直接观察到的风格

候选通常直接定义对象、条件和问题，而不是让考生理解内部计算操作名。2025第16题在同一数列基础上继续研究以其项为系数的函数，前问建立关系，后问使用前面的数学对象。2026第17题在停止规则与随机变量的共同情境下研究概率和参数，理解模型本身构成考查；这不同于在很小样本空间上反复列举后给高分。

2025第18题、2026第18题需要由几何条件建立关系。旧fullA第18题则先给完整椭圆，再问半轴，同时把参数表示、代换和距离化简交给考生，原17分的工作量被提前削弱。旧fullB第18题直接给动点距离平方，第3问是第2问零距离情形，也没有形成足以解释17分的递进。

多选本来就是判断命题真值，不能把“真假判断”本身认定违规。2026第9题候选就是同一复数的几种基本性质，说明基础多选可以存在；2025第10题、2026第10题则要求在统一几何条件下组织多个关系。旧两卷的三道多选几乎都只做直接代入、恒等式或零内积判断，整组缺少梯度。规范应允许一道有共同对象的基础多选，再有约束推理与综合层次，不能把两套样本变成固定分配法。

## 70题实际问题

每题均有六个能力维度、整体难度依据、方法提示可见性、时间区间、原分值审查和对照源。维度是AI有据判断，整体难度不是按操作数或这些序号的算术平均生成。估计没有考生实测。

明显的发布阻断包括：验收第5题的“目标事件为1=1”；sequence10第10题第2问给出了第1问的求和闭式；derivative10第5题第2问写出了第1问待求参数。后两处不能只改字体，必须改写设问，避免反向透露答案。

“指定值1”未清楚说明求的是f'(1)，大量“求几何量/指定交点量/有序结果数”让考生承担程序协议解释。“u(n)”和嵌套括号应改成数列下标与常用代数式。概率题尤其要保留顺序、放回和条件事件的真实含义，不能为追求简短而改成另一个模型。

旧解答题有些数学想法值得保留：变系数递推、交错递推、参数在无穷区间的必要性、共同向量与空间角等。但一题仅有一个简单结果，或两个等价任务，并不因为排了两行就支持10分，更不能机械装入13/15/17分槽位。

干扰项也不能只检查错因非空。fullB第3题把9的错因标为极差，但样本极差是10；fullB第1题两根平均为-1而非选项1/2；fullB第4题一个错误选项并不等于所称的任一特殊角因子。这些错误不改变已有正确答案，却使认知错因归因失去依据。本次逐项检查了20道单选的错因，区分可复现、需明确和确定不符；即使可复现，也仍是设计假设，未获学生错误数据实证。

本次还发现2025第15题独立性检验的旧主模块误标为集合与复数。原分析不改动，另以review-overrides.json保存候选及分析双哈希、原值与复核后的概率统计。规划器只有版本全匹配才可应用。样本中没有排列组合主模块的直接对应，相关新题不能伪造同知识点真题参照，需另给课程依据或标清辅助样本。

报告里的“独立练习工作量分值带”不是新高考评分规则。完整卷若要保留原卷型分值，应重设计有实质关联的条件与小问，而不是把各题降分后仍称150分，也不能靠拉长文字、罕见术语或超纲工具提高表面难度。

## 本报告不是最终可读性验收

本审查读取了内部规格和解答记录，属于编辑与数学结构分析，不符合“只看PDF”的盲审条件。父流程必须先让新的5题样卷经过仅PDF独立审题，通过后才生成整卷，再绑定最终PDF/页面哈希进行审阅。数学程序验证与考生可读性都通过后，也仍需教师和实测来支持高考风格与难度结论。

"""
    text += "## 自动汇总\n\n"
    text += "小问统计区分顶层小问、叶子设问与数据记录；含子问的条件容器不重复计作一次设问。\n\n"
    text += f"实际审查{summary['reviewed']}题；{summary['route_disclosure']}题存在方法/突破口提示；{summary['score_depth_mismatch']}题原分值超出本次独立练习工作量判断区间。这些计数是本次AI审查结论，不是客观难度测量。\n\n"
    for kind, row in stats.items():
        text += f"- {kind}：{row['count']}道候选，含LaTeX原始字符长度中位数{row['raw_length_median']}，中文字符中位数{row['chinese_length_median']}，小问数量分布{row['subquestion_counts']}。\n"
    text += "\n同样题型下，两套旧150分卷共38题的实际转写统计如下，注意AST排版命令本身也会增加原始字符，不能据此判断数学深度。\n\n"
    for kind, row in generated["two_full_papers_38"].items():
        text += f"- {kind}：{row['count']}题，含LaTeX字符中位数{row['raw_length_median']}，中文字符中位数{row['chinese_length_median']}，显式左括号命令中位数{row['left_parenthesis_commands_median']}，{row['machine_term_count']}题含机器任务词。\n"
    (ROOT / "reports/phase4-source-style.md").write_bytes(text.encode("utf-8"))


if __name__ == "__main__":
    main()
