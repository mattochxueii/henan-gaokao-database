"""Version-bound author/editor comparison, explicitly separate from PDF-only review."""

import bootstrap
import json
import re
from analysis_db import research, fingerprint
from gaokao import ROOT, read_json, require, digest
from storage import atomic_json
from mathgen.editorial import compile_writing

# Per-item judgments made after reading the actual final writing. Reference roles
# distinguish shared knowledge from a transfer of method or a broad adjacent area.
DATA = {
    "fullA": [
        (
            ["复数除法", "模"],
            [("26:09", "core"), ("25:01", "related")],
            "先给一个复数，再直接问距离型模；没有分子分母的教学提醒。",
            "实部、虚部和模由同一对象自然确定，未把实数化计算式放到题干。",
            "一次复数运算后求模，作为5分起始题；不因两步运算称综合难题。",
            "与源复数多性质/乘法共享基本运算，求模对象不同；基础层次相近。",
        ),
        (
            ["集合交集", "整数范围与端点"],
            [("25:02", "core"), ("26:03", "core")],
            "两个集合定义后问交集元素个数，有限/整数范围写入集合。",
            "区间开闭与整数限制均是数学条件，保留而非删成程序布尔式。",
            "筛选两个整数，5分基础题；关键是条件而不是计算量。",
            "源分别是补集计数和三角值集合求交，新题是区间与整数条件相交，并非同式换数。",
        ),
        (
            ["和角关系", "象限符号"],
            [("26:13", "core"), ("25:11", "related")],
            "角的范围与一个三角值集中陈述，直接问另一函数值。",
            "给的是原角范围，学生需要自行判定和角的象限；题干不提示先取负的余弦。",
            "5分中低档题，区间符号选择后作一次和角变换。",
            "与源相位/和角及三角恒等变形同核心，但源偶性/形状约束没有被照搬。",
        ),
        (
            ["均值修正", "二阶矩与方差"],
            [("26:01", "adjacent"), ("25:15", "adjacent")],
            "误录、原统计量和纠正对象只陈述一次，问纠正后的方差。",
            "原10个观测不必逐项给出，一阶与二阶矩足以确定目标；没有给出更新公式。",
            "5分中档，需同时更新和与平方和，不是只把误差平方加回。",
            "样本有统计量题但无直接误录方差修正题；本题考点不能声称已由两年真题频率证实。",
        ),
        (
            ["向量数量积", "参数二次方程", "对称根和"],
            [("25:17", "method"), ("26:02", "related")],
            "向量及夹角条件自然给定，问全部参数值的和。",
            "t>0排除符号歧义，问根和而非强行要求参数唯一。",
            "5分后部题，建立数量积方程并筛选两解；与实际源向量运算相比多一层参数约束。",
            "源空间角使用点积、另一源基底需系数唯一；这里只迁移数量积/条件组织，未宣称同构型。",
        ),
        (
            ["椭圆焦点定义", "边长比例", "三角形面积"],
            [("26:18", "core"), ("25:18", "related")],
            "标准椭圆、焦点与距离比例三项条件后问面积。",
            "不预给三角形三边或海伦公式，须从焦点定义恢复。",
            "5分中档，不是17分源题的同等难度；只取椭圆焦点与面积的基础连接。",
            "对应源有焦点弦与面积、椭圆约束，但本题不含动直线多问优化，明确降为前部计算层次。",
        ),
        (
            ["导数切线", "切点反求", "唯一性"],
            [("25:12", "core"), ("26:04", "core")],
            "给曲线与切线经过的原点，直接问斜率。",
            "切点未知而经过点已知，题面没有把切点方程替考生写好。",
            "5分后部，斜率与共点条件需要同时满足，还应排除其他实切点。",
            "源有给定点切线和反求常数，本题改为过外点反求切点；共同是斜率与点不能只取其一。",
        ),
        (
            ["位置排列", "奇偶分类", "对称计数"],
            [("26:07", "method")],
            "三位数的数字来源、互异、大小与奇偶条件分列成自然语句。",
            "计顺序体现在三位数的位置，避免“有序结果数”占位指令。",
            "5分末部，需两类奇偶构成再处理百位/个位对称；不是无约束列举。",
            "38题没有直接三位数排列题；源仅提供奇偶约束与构造的思路参照，不能伪称同知识点真题。",
        ),
        (
            ["交错数列", "子列等差", "分组求和"],
            [("26:07", "related"), ("26:14", "related")],
            "同一数列通项、正整数范围、前缀和定义后列四项性质。",
            "各选项仍为真假命题，但共享对象且涉及子列与总体，语句不重复计算指令。",
            "6分基础至中档多选，公差辨析和奇偶前缀和有联系；不要求每道多选都高难。",
            "源有奇偶分组、全局块和与局部等比存在性，本题较浅，不能据模块相同宣称难度等同。",
        ),
        (
            ["抛物线焦点", "切线", "弦长"],
            [("25:10", "core"), ("26:05", "core")],
            "同一抛物线下同时考焦点、不同切线条数、相切与割线。",
            "切线点、共点与两点条件由选项自然提出，不打印判定函数。",
            "6分中档，性质辨析需要关联方程和几何量；不是四个点代入同一式。",
            "源分别研究焦点弦多性质与抛物线参数，本题取经典共同对象，具体设问结构不同。",
        ),
        (
            ["对数导数", "极值", "水平集根位置"],
            [("26:04", "core"), ("25:19", "method")],
            "一个有定义域的函数，四项围绕图像整体性质。",
            "参数水平线和两根有序位置写清；没有把导数或最大点当条件。",
            "6分末部多选，需兼顾负水平线、两支正水平线和边界渐近行为。",
            "直接共享对数求导基本知识；全局极值/分层论证只参考源的方法，样本没有同式水平集题。",
        ),
        (
            ["二项式定理", "Laurent幂次筛选"],
            [],
            "直接给展开式与目标幂次，不额外包装成数列故事。",
            "负幂与整体六次幂保留原对象，求系数的请求明确。",
            "5分填空需匹配幂次与组合系数；不是记下某个展开答案。",
            "38题中没有直接二项式系数题，必须承认参考缺口；合理范围需课程依据而非伪造真题源。",
        ),
        (
            ["三角图像平移", "横向伸缩", "函数值"],
            [("25:04", "core"), ("26:13", "core")],
            "明确先后顺序的图像变换后问一个函数值。",
            "“先平移再缩放”是题目的数学操作条件，不是应删除的解题提示。",
            "5分中档，横坐标变换方向和先后不可交换，实际演算不长。",
            "源涉及平移周期、相位频率与函数值，新题改为复合图像操作，保留共同三角函数知识。",
        ),
        (
            ["正四面体", "体积与表面积", "内切球半径"],
            [("25:17", "related")],
            "正四面体与棱长足以确定内切球，无程序坐标。",
            "“内切”限定球与四面的接触，不是未定义的任意球心。",
            "5分后部填空，需从空间几何量得到半径；记忆公式与推导路径都应允许。",
            "源有共球球心与等距关系，但没有直接正四面体内切球题；仅空间球/距离方法相关。",
        ),
        (
            ["超几何分布", "条件概率", "依赖抽样"],
            [("26:17", "core"), ("25:15", "core"), ("25:14", "related")],
            "共享不放回取球模型，先定义随机变量，后问引用前次条件。",
            "每轮是否放回、剩余球与条件事件均明确，后问不偷换为独立抽样。",
            "13分是分布/期望→条件事件重权→受历史影响的后续概率，不是重复同一个均值。",
            "源独立投篮与医疗条件概率给分布/条件推理参照；无直接同超几何模型源，不能冒称模型本身由两样本固定。",
        ),
        (
            ["线面平行", "二面角", "受约束位置存在性"],
            [("25:17", "core"), ("26:15", "core")],
            "几何体、长度和两中点只给一次，三问沿同一构型组织。",
            "点Q限在棱上，存在性须含平面外判别，不可仅解平行方程。",
            "15分含证明、夹角计算及约束可行性，深度来自几何关系而非已给坐标。",
            "源四棱锥垂直/球心/异面角与棱柱中点平行/距离同属空间关系链，新卷任务不等于源题复制。",
        ),
        (
            ["二阶递推", "一阶变换", "全体整数范围不等式"],
            [("25:16", "core"), ("26:07", "method")],
            "初值、递推与n范围完整；第一问定义辅助数列，后两问回到原数列。",
            "辅助数列定义本身是题目要求，不是题前泄通项；第3问要求证明排除所有后续n。",
            "15分由降阶、恢复通项到无限整数域的严格界证明，不能以测试前若干n代替。",
            "源数列变换为后续任务铺路，另有必要条件与构造；这里在不同递推结构下增加离散全域判断。",
        ),
        (
            ["椭圆定参", "中点轨迹范围", "弦面积优化"],
            [("25:18", "core"), ("26:18", "core")],
            "先给决定椭圆的条件和外点弦关系，后问轨迹及最值。",
            "区分不垂直条件下的轨迹和全体弦下的面积，必须单独核查竖直边界。",
            "17分包含条件建模、消元、可行范围和上界可达性，不提前给弦中点/面积公式。",
            "与源椭圆轨迹、焦点弦面积优化同核心；外点中点轨迹与面积目标是新的组合，不声称固定压轴模式。",
        ),
        (
            ["对数函数极值", "水平集根分类", "两根和积界"],
            [("26:04", "core"), ("25:19", "method"), ("26:19", "method")],
            "一个函数及正定义域，先局部性质再水平参数，最后讨论根关系。",
            "参数a的一般性、两根顺序与同时两条不等式均明确，题面不给比较变换。",
            "17分难点是一般水平值下的两支根比较，需要两类变换，不是只求导一次。",
            "样本无同式对数双根和积界；直接参照仅对数导数，分层全域证明借鉴源组织方式，不把新结论称真题规律。",
        ),
    ],
    "fullB": [
        (
            ["共轭线性关系", "复数平方虚部"],
            [("26:09", "core"), ("25:01", "core")],
            "用共轭关系给出未知复数，直接问平方虚部。",
            "没有把实部虚部方程组打印出来，须自行辨明复数相等的含义。",
            "5分起始题，既有基本识别也有短计算，不把平方分拆成解答题高分。",
            "共享源共轭与基本运算，条件是待求复数的关系而非直接换已知复数数值。",
        ),
        (
            ["有限集合交集", "二次不等式"],
            [("25:02", "core"), ("26:03", "core")],
            "有限集合与不等式集合两项条件后直接问交集大小。",
            "严格不等号与0是否为元素都保留，不用内部事件计数术语。",
            "5分基础题，重点是开区间筛选；无需把所有集合操作写成任务标签。",
            "源有限集合边界/交集提供直接知识参照，本题不等式成集与三角值成集不同。",
        ),
        (
            ["正切倍角", "差角", "符号"],
            [("25:11", "core"), ("26:13", "related")],
            "角范围与正切值后问复合角正切，没有提示先变倍角。",
            "分母非零由实际给定角决定，符号来自关系而非额外教学旁白。",
            "5分中低档，用两次有关联的恒等变换，不依靠巨大数值演算。",
            "源有二倍角和和角等恒等变形；这里目标正切差角，非重复源三角形或偶性条件。",
        ),
        (
            ["独立不等概率试验", "并事件", "条件概率"],
            [("26:17", "core"), ("25:15", "core")],
            "射击对象、各自命中概率与独立性在自然情境中给出。",
            "“至少一人”与“恰有一人”不可混用，不额外列人造等可能变量。",
            "5分条件概率，重新归一和互斥事件区分构成主要推理。",
            "源有独立投篮与医疗条件概率；新题固定两次不等概率事件，不移植停止规则。",
        ),
        (
            ["圆与弦", "点到直线距离", "实参数"],
            [("25:07", "core"), ("26:11", "core")],
            "圆、直线和弦长后问实参数，数学对象自然明示。",
            "没有把半弦与圆心距的关系预给，学生须建距离约束。",
            "5分中档，建立几何量再解参数，计算短而有转换。",
            "源一圆直线位置与三圆弦长相关，本题单圆求参较源三圆多分支问题浅，分值相应为5。",
        ),
        (
            ["双曲线轴焦关系", "渐近线", "圆的相切"],
            [("25:03", "core"), ("26:12", "core"), ("25:07", "method")],
            "曲线参数正性、实轴长和渐近线相切集中陈述。",
            "焦距的对象清楚，不能把半焦距或实轴长混同；不给相切方程。",
            "5分后部题，两类几何对象联系，需标准式与距离条件。",
            "源双曲线半轴/离心率加圆直线距离方法在新条件下结合，不仅替换轴长数字。",
        ),
        (
            ["正项等比", "等比中项", "对称和"],
            [("25:13", "core"), ("26:14", "related")],
            "正项与相邻中项约束后问跨两端的对称和。",
            "不强加无关递增条件；两种公比可以对应同一个目标值。",
            "5分后部，识别对象不唯一但目标唯一，不能先求任意一支就默认答案。",
            "源正项等比与块和/局部等比存在性相关；本题取对称不变量，较源局部存在构造浅。",
        ),
        (
            ["绝对值分段", "方程根数", "范围筛选"],
            [("25:05", "method"), ("26:06", "related")],
            "只给一个清楚的方程并问不同实根数，无根数组件指令。",
            "分段符号与右端非负要同时检验，不因两段各有根就机械相加。",
            "5分末部，建立两个二次方程还要检验各自范围。",
            "样本没有直接绝对值二次方程题；只借鉴分段信息/参数条件核查，不伪称同题知识点出现。",
        ),
        (
            ["均值方差", "线性变换", "增加观测", "存在性"],
            [("26:01", "adjacent"), ("25:15", "adjacent")],
            "共享五项统计摘要及统一变换，选项覆盖计算和逻辑后果。",
            "只给均值方差足以判断命题；不需捏造五个观测，新增一项后的分母明确变化。",
            "6分基础至中档多选，最后一项要用方差正与偏差和为0，而非四项重复代入。",
            "样本统计题不是同均值方差变换题；直接知识点参照缺失，相关源只作数据分析领域背景。",
        ),
        (
            ["两圆位置", "距离范围", "切线边界", "弦长可达"],
            [("26:11", "core"), ("25:07", "core")],
            "同一两圆和动点条件下列四个几何结论。",
            "“任意一点”包括公共切点；割线要求两个不同交点，边界没有省略。",
            "6分中档，既需证明恒真也需给全称命题反例，最大值须能取到。",
            "与源圆/弦长多性质同核心，减少源三圆复杂分支并加入公共点边界，不能说一样难。",
        ),
        (
            ["三次函数单调", "参数平移", "零点个数与位置"],
            [("26:06", "method"), ("26:19", "method"), ("25:19", "method")],
            "一个参数函数串联四个性质，条件“任意/当/若”清楚区分。",
            "边界a=0、开区间参数和较大参数的唯一根位置分别考查。",
            "6分末部，导数分区要转成水平值与根位置分类，不只检验几个固定函数值。",
            "样本没有直接同三次参数零点题；参照的是参数/全域函数推理组织，不能据此立固定出题规则。",
        ),
        (
            ["对数运算", "定义域", "函数关系求值"],
            [("25:08", "core")],
            "定义函数及开区间，再用函数关系问未知自变量。",
            "t在定义域内写明，避免对数分式符号与指数化过程遗漏。",
            "5分中档填空，需把关系转回自变量，不把“指定值”留给读者猜。",
            "源对数比较中有公共值转化，本题利用加法转乘法求未知输入，目标不同。",
        ),
        (
            ["面积与正弦", "余弦定理", "两解分支"],
            [("25:11", "core"), ("26:16", "core")],
            "三角形边角命名、两边与面积后问所有可能边长。",
            "没有暗示夹角唯一，明确“所有可能值”保证双解是任务而非歧义。",
            "5分中档，正弦信息须保留锐钝两种并验证三角形有效。",
            "源面积/三角条件与两边夹角求边同核心，新题故意保留两种夹角，问题组织不同。",
        ),
        (
            ["正方体中点", "空间方向", "异面直线角"],
            [("25:17", "core"), ("25:09", "related")],
            "常见正方体命名与两中点后问两条直线角，配结构图。",
            "两个中点所在棱明确，问直线角而非有向向量夹角，需取非负余弦。",
            "5分后部空间填空，需要从构型自行定方向，不向考生给坐标。",
            "源异面角/空间线面关系提供核心方法；新体型与指定中点不同，没有同正方体原题。",
        ),
        (
            ["频率估计", "独立三次分布", "条件风险", "参数收益"],
            [("25:15", "core"), ("26:17", "core")],
            "先定义检验模型与通过规则，再给样本；三个请求按估计、风险、一般参数展开。",
            "样本估计与真实未知参数区别清楚，最后一问明确不再固定为估计值。",
            "13分涵盖模型假设、分布列、条件事件与收益参数阈值，数学挑战不靠重复小样本枚举。",
            "源样本统计推断与独立投篮分布提供共同知识，但没有同固定三件验收收益模型，构造为本轮实验。",
        ),
        (
            ["面面平行", "体积", "空间角最优"],
            [("26:15", "core"), ("25:17", "core")],
            "直棱柱与三中点条件一次给齐，先证明平行再量化并研究动线。",
            "Q限在线段，最优值需给等号位置；不直接给方向向量或角度函数。",
            "15分由几何证明、截面体积到受限动角最优，路径不同于A卷的二面角及平行存在。",
            "源棱柱中点平行/角距与空间向量同核心，加入体积与一元最优为新的组合，并非高创新证明。",
        ),
        (
            ["和项递推", "加权求和", "整数性排除"],
            [("25:16", "core"), ("26:07", "method")],
            "给前缀和关系而非现成递推，后两问连续使用同一通项。",
            "正整数范围写明，后问不给闭式T_n；必须证明没有其他n。",
            "15分含从S_n恢复递推、求加权和和整数分母的无限范围排除。",
            "源递推变换与必要条件/可实现性有联系，但样本无同分母整数性题；整除依据需高中可读解释。",
        ),
        (
            ["抛物线焦点弦", "切线交点轨迹", "面积最值"],
            [("25:10", "core"), ("26:05", "core"), ("25:18", "method")],
            "焦点、准线、焦点弦与两切线共同定义图形，后问轨迹和面积。",
            "不预给参数表示与面积式，轨迹须证明全范围且包括竖直弦。",
            "17分从定方程到轨迹必要充分再到面积界与等号，包含不止一次代入。",
            "源焦点弦多性质与轨迹最值提供核心/方法参照；新切线交点及最小面积不是源题换数字。",
        ),
        (
            ["参数对数导数", "三根分类", "倒数根关系"],
            [("26:04", "core"), ("25:19", "method"), ("26:19", "method")],
            "同一正定义域参数函数三层设问，末问提出根的关系而不提示倒数变换。",
            "参数退化值、全部不同零点及根的顺序明确，不把无定义的程序集合给考生。",
            "17分必须完整分类、处理临界参数并用隐藏函数变换证明三根关系。",
            "样本无同式对数三根倒数关系；直接参照只到对数导数，分层全域论证是方法参考，不是已发现命题定律。",
        ),
    ],
}

GAPS = {
    ("fullA", 4): "无直接误录方差修正题，邻近统计题不能当同知识点证据。",
    ("fullA", 8): "无直接三位数排列组合题；只存在奇偶/构造的间接方法参照。",
    (
        "fullA",
        12,
    ): "38题无直接二项式系数题；当前课程规则文件也不是二项式范围的逐条官方证明。",
    ("fullA", 14): "无直接正四面体内切球题；仅空间球心/距离方法相关。",
    ("fullA", 19): "无同式对数双根和积界题，不能把方法关联说成同结构验证。",
    ("fullB", 8): "无直接绝对值二次方程根数题，参照仅分段与边界核查。",
    ("fullB", 9): "无直接均值方差变换/新增观测题；同属统计不等于同知识点。",
    ("fullB", 11): "无直接三次参数函数零点分类题，只有参数/全域推理方法参照。",
    ("fullB", 19): "无同式对数三根与倒数根关系题，不能声称其结构由两年真题证实。",
}


def full_id(short):
    year, n = short.split(":")
    return f"20{year}-cn-math-national-1:q{int(n):03d}"


def metrics(student):
    chunks = [
        student["stem"],
        *[p["text"] for p in student.get("parts", [])],
        *student.get("options", {}).values(),
    ]
    text = "\n".join(chunks)
    plain = re.sub(r"\\\(.*?\\\)", "□", text, flags=re.S)
    return {
        "raw_characters_with_latex": len(text),
        "chinese_characters": len(re.findall(r"[\u4e00-\u9fff]", plain)),
        "formula_count": text.count(r"\("),
        "left_parenthesis_commands": text.count(r"\left("),
        "machine_terms": [
            x
            for x in (
                "目标事件",
                "指定值",
                "有序结果数",
                "求几何量",
                "附加限制",
                "SymPy",
                "Interval(",
            )
            if x in text
        ],
    }


def original_profile(row):
    c = row["candidate"]
    a = row["analysis"]
    numbers = [p["number"] for p in c.get("subquestions", [])]
    leaves = [n for n in numbers if not any(m.startswith(n + "(") for m in numbers)]
    student = {
        "stem": c["stem"],
        "parts": c.get("subquestions", []),
        "options": {
            k: (v["text"] if isinstance(v, dict) else v)
            for k, v in (c.get("options") or {}).items()
        },
    }
    return {
        "question_id": row["id"],
        "candidate_version": c["version"],
        "candidate_sha256": fingerprint(c),
        "analysis_sha256": fingerprint(a),
        "source_id": c["source_id"],
        "source_url": c["source_url"],
        "pages": list(range(c["page"], c.get("end_page", c["page"]) + 1)),
        "source_file_hashes": [f["sha256"] for f in c["source_files"]],
        "kind": row["kind"],
        "points": row["points"],
        "knowledge": a["knowledge"],
        "reviewed_module": "概率统计"
        if row["id"] == "2025-cn-math-national-1:q015"
        else a["knowledge"]["module"],
        "leaf_questions": len(leaves),
        "condition_design": a["context_and_condition_design"],
        "reasoning": a["logical_reasoning"],
        "metrics": metrics(student),
        "official_body_confirmed": False,
    }


def prepared_snapshot(document, name):
    folders = sorted(
        (ROOT / "experiments/phase4").glob(name + "-v*"),
        key=lambda p: int(p.name.rsplit("v", 1)[1]),
        reverse=True,
    )
    final = ROOT / "experiments/phase4/final" / name
    if final.exists():
        folders.insert(0, final)
    for folder in folders:
        manifest_path = folder / "review-manifest.json"
        if not manifest_path.exists():
            continue
        manifest = read_json(manifest_path)
        if manifest["candidate_sha256"] == fingerprint(document):
            require((folder / "student-text.json").exists(), "匹配候选未生成考生文本")
            return folder, manifest, read_json(folder / "student-text.json")
    raise ValueError("尚无与当前候选哈希匹配的真实排版快照：" + name)


def main():
    refs = {row["id"]: original_profile(row) for row in research(ROOT)}
    require(len(refs) == 38, "必须真实读取38题")
    all_rows = []
    paper_status = {}
    input_hashes = {}
    source_rows_used = {}
    for name, items in DATA.items():
        path = ROOT / "experiments/phase4/proposals" / (name + ".json")
        document = read_json(path)
        require(len(document["questions"]) == len(items) == 19, "逐题对照缺失")
        folder, manifest, paper = prepared_snapshot(document, name)
        input_hashes[name] = {
            "document_sha256": fingerprint(document),
            "file_sha256": digest(path),
            "snapshot": folder.relative_to(ROOT).as_posix(),
            "pdf_sha256": manifest["pdf_sha256"],
        }
        cert = folder / "publication.json"
        review = folder / "student-review.json"
        paper_status[name] = {
            "final_certificate_present": cert.exists(),
            "pdf_only_review_present": review.exists(),
            "status": "以最终publication及student-review为准，本报告不授予发布资格",
        }
        if cert.exists():
            paper_status[name]["publication_status"] = read_json(cert)["status"]
        for question, student, supplied in zip(
            document["questions"], paper["questions"], items
        ):
            concepts, raw_refs, organization, conditions, depth, difference = supplied
            # This is an actual compile/binding check, not a fallback render from AST.
            fresh = compile_writing(question)
            require(
                fingerprint(fresh) == fingerprint(student),
                "候选写作与实际已排文本不一致",
            )
            evidence = []
            for short, role in raw_refs:
                reference = refs[full_id(short)]
                source_rows_used[reference["question_id"]] = reference
                evidence.append(
                    {
                        **reference,
                        "comparison_role": role,
                        "role_note": {
                            "core": "共享主要知识或明确二级知识，不代表同结构同难度",
                            "related": "共享部分知识，情境与主要求不同",
                            "method": "仅推理/建模方法迁移，不是同知识点题",
                            "adjacent": "邻近领域背景，不作同知识点直接证据",
                        }[role],
                    }
                )
            options = question["math_spec"].get("options", {})
            if question["kind"] == "single_choice":
                distractors = {
                    "design_paths_present": all(
                        v.get("error_path") for v in options.values()
                    ),
                    "computable_expressions_present": sum(
                        "error_calculation" in v for v in options.values()
                    ),
                    "student_errors_empirically_validated": False,
                    "scope": "错因是设计假设；表达式与选项相同不自动证明其由原始条件的错误步骤得到。数值/语义一致与真实认知归因分开。",
                    "path_summaries": {
                        k: {
                            key: value[key]
                            for key in (
                                "semantic_value",
                                "error_path",
                                "error_calculation",
                            )
                            if key in value
                        }
                        for k, value in options.items()
                    },
                }
            elif question["kind"] == "multiple_choice":
                distractors = {
                    "shared_object": organization,
                    "logical_design": difference,
                    "scope": "真假判断本身是正常多选；考查关联、量词和边界才决定层次，非要求全部多选高难",
                }
            else:
                distractors = {"applicable": False}
            rows = {
                "question_id": question["id"],
                "paper": name,
                "order": question["order"],
                "kind": question["kind"],
                "points": question["points"],
                "math_spec_sha256": fingerprint(question["math_spec"]),
                "writing_sha256": fingerprint(question["writing"]),
                "student_text_sha256": fingerprint(student),
                "reviewed_topics": concepts,
                "original_module_label": question["module"],
                "reference_gap": GAPS.get((name, question["order"])),
                "comparisons": {
                    "stem_length_and_structure": {
                        "generated_metrics": metrics(student),
                        "source_metrics": [
                            {
                                "id": r["question_id"],
                                "kind": r["kind"],
                                "metrics": r["metrics"],
                            }
                            for r in evidence
                        ],
                        "interpretation": "字符数含LaTeX与候选转写，不是官方字数分布或难度指标；公式宏计数只反映样式负担。",
                    },
                    "language": organization,
                    "condition_organization": conditions,
                    "request_organization": organization,
                    "knowledge_integration": {
                        "concepts": concepts,
                        "count": len(concepts),
                        "not_a_difficulty_formula": True,
                        "basis": difference,
                    },
                    "reasoning_depth": depth,
                    "score_and_gradient": {
                        "points": question["points"],
                        "design_level": question["assessment"]["level"],
                        "estimated_minutes": question["assessment"][
                            "estimated_minutes"
                        ],
                        "basis": question["assessment"]["points_justification"],
                        "editorial_judgment": depth,
                        "empirical": False,
                        "teacher_certified": False,
                    },
                    "distractor_quality": distractors,
                    "layered_questions": {
                        "new_part_count": len(student["parts"]),
                        "part_points": question["assessment"].get("part_points", []),
                        "progression": question["assessment"].get("linked_progression")
                        or "选择/填空不强行分成程序小问",
                        "source_leaf_counts": [
                            {"id": r["question_id"], "count": r["leaf_questions"]}
                            for r in evidence
                        ],
                        "count_alone_does_not_certify_depth": True,
                    },
                    "similarities_and_differences": difference,
                },
                "evidence": evidence,
                "review_identity": "author_editor_comparison_not_blind",
                "model_version": "not_exposed_by_host",
                "independent_student_quality_pass_granted_by_this_report": False,
            }
            all_rows.append(rows)
    require(
        len(all_rows) == 38 and len({r["question_id"] for r in all_rows}) == 38,
        "38题未唯一覆盖",
    )
    examples = before_after()
    summary = {
        "new_questions_compared": 38,
        "source_candidates_read": 38,
        "source_questions_actually_referenced": len(source_rows_used),
        "source_papers": 2,
        "author_editor_report": True,
        "pdf_only_independent_review": False,
        "missing_direct_references": [
            {"id": r["question_id"], "gap": r["reference_gap"]}
            for r in all_rows
            if r["reference_gap"]
        ],
        "paper_estimated_minutes": {
            name: sum(
                r["comparisons"]["score_and_gradient"]["estimated_minutes"]
                for r in all_rows
                if r["paper"] == name
            )
            for name in DATA
        },
        "paper_status": paper_status,
        "global_originality_proven": False,
        "high_exam_standard_certified": False,
    }
    distractor_path = ROOT / "reports/phase4-distractor-audit.json"
    report = {
        "schema_version": 1,
        "created_at": "2026-11-08",
        "scope": "38道新题的实际写作与两个候选样本的作者/编辑对照；不是独立盲审",
        "inputs": input_hashes,
        "summary": summary,
        "questions": all_rows,
        "before_after_examples": examples,
        "additional_error_model_experiment": {
            "path": "reports/phase4-distractor-audit.json",
            "present": distractor_path.exists(),
            "sha256": digest(distractor_path) if distractor_path.exists() else None,
            "scope": "另行从原始条件重建错误操作的可复现计算；与候选中常量表达式对齐选项的证据级别区分，不是考生真实错误频率实测",
        },
        "limits": [
            "作者之一参与卷B设计，本报告不能替代只看PDF的独立审题",
            "源题是第三方版本候选并有归一化文字，不是官方原卷逐字认证",
            "样本仅2套，不设置固定题材/知识点比例/压轴规律",
            "长度与步数不作为独立难度或创新评分",
            "图表信息未计入文本字符统计；图形、公式与版面可读性必须另经实际PDF视觉审查",
            "干扰项认知归因是设计假设，未有真实考生错因实测",
            "132分钟等估时如实保留；试卷完成负担以独立PDF审题及后续考生实测为准",
            "最终发布状态需读取publication.json、student-review.json与数学对照证书",
        ],
    }
    atomic_json(ROOT / "reports/phase4-new-style-comparison.json", report)
    markdown(report)
    print(
        json.dumps(
            {
                "compared": 38,
                "snapshots": input_hashes,
                "estimated_minutes": summary["paper_estimated_minutes"],
                "reference_gaps": len(summary["missing_direct_references"]),
            },
            ensure_ascii=False,
        )
    )


def before_after():
    cases = [
        (
            "同一数学核心重写",
            "acceptance5",
            1,
            "pilot-v2",
            4,
            "旧题在递推前明确提示阶乘权重，并打印移项为0的嵌套AST。",
            "新小样使用数列下标、首项和递推等式，分开通项与后续和；分值10调整为8，保持核心递推语义。",
        ),
        (
            "替换而非语义等价改写",
            "acceptance5",
            5,
            "fullA-v7",
            8,
            "旧计数题出现目标事件为1=1，并把0-1约束打印成逻辑与。",
            "新三位数题用数字来源、不同位置、大小和奇偶条件直接定义计数对象；这是新题，不称只改语言但语义完全相同。",
        ),
        (
            "替换并深化",
            "fullA",
            18,
            "fullA-v7",
            18,
            "旧17分题直接给椭圆、参数表示、代换和距离化简，半轴还重复待求。",
            "新题由离心率和过点条件定椭圆，再研究外点弦中点轨迹范围与面积上界可达，未预给中间公式。",
        ),
        (
            "替换多选设计",
            "fullA",
            9,
            "fullB-v2",
            9,
            "旧多选把四个恒等命题包装成重复计算/判断指令。",
            "新题共享统计摘要，覆盖变换、新增观测与存在性逻辑；仍判断真假但推理目标有关联。",
        ),
        (
            "替换数列任务",
            "fullB",
            17,
            "fullB-v2",
            17,
            "旧题先提示奇偶抵消，直接给递推后再求前缀和。",
            "新题从和项关系恢复递推，进入加权和并证明整数性全范围；未把前问的闭式打印在后问。",
        ),
        (
            "替换解答关系链",
            "fullB",
            18,
            "fullB-v2",
            18,
            "旧题给出动点距离平方函数，后问再求零距离参数，17分缺乏层次。",
            "新题由焦点和准线定抛物线，研究两切线交点的全轨迹，再构造面积函数证明最优与等号。",
        ),
        (
            "替换函数综合",
            "fullB",
            19,
            "fullB-v2",
            19,
            "旧两问是参数单调和常规对数不等式的并排计算。",
            "新题完整研究临界参数、三个零点必要充分分类和隐含倒数根关系，三问共享前面的结构。",
        ),
    ]
    out = []
    for kind, oldpaper, oldn, newfolder, newn, before, after in cases:
        old = read_json(ROOT / "experiments/phase3/deliveries" / oldpaper / "run.json")[
            "questions"
        ][oldn - 1]
        folder = ROOT / "experiments/phase4" / newfolder
        if not (folder / "student-text.json").exists():
            continue
        new = read_json(folder / "student-text.json")["questions"][newn - 1]
        out.append(
            {
                "change_type": kind,
                "old_id": old["id"],
                "old_question_sha256": fingerprint(old),
                "new_id": new["id"],
                "new_student_text_sha256": fingerprint(new),
                "before": before,
                "after": after,
                "semantic_equivalence_claimed": False,
                "same_recurrence_core_preserved": kind == "同一数学核心重写",
                "core_change_note": "仅核心递推语义保留；新增后续和设问，不声称新旧整题严格等价"
                if kind == "同一数学核心重写"
                else "数学任务/题材已替换，不声称语义等价",
                "identity_warning": "题材/结构已替换的例子不声称旧题与新题数学语义完全一致",
            }
        )
    return out


def markdown(report):
    summary = report["summary"]
    lines = [
        "# 第四阶段新卷与候选真题风格对照",
        "",
        "本报告逐题比较两套新卷38题与实际读取的2025、2026候选。它是作者/编辑对照：审查者参与卷B创作，读取内部规格，不能称为只看PDF的独立盲审。最终结论以student-review、数学对照及publication证书为准。",
        "",
        "## 方法与来源限制",
        "",
        "按实际知识点、次要知识和解题关系选择来源，不盲信旧module标签。核心知识参照、部分相关、方法迁移与邻近领域分别标记。2025第15题旧模块误标按双哈希复核映射识别，原分析不覆盖。所有源都保留ID、版本、候选和原文件哈希、页码、链接；不复制真题全文。",
        "",
        "仅有两套第三方转写/扫描候选，未获命题机构逐题确认。含LaTeX字符统计不等于官方卷面的字数；题干更短、题量分值相同，也不能证明更有高考风格。",
        "",
        "## 逐题对照",
        "",
    ]
    for name in DATA:
        lines += ["### " + ("模拟卷一" if name == "fullA" else "模拟卷二"), ""]
        for row in report["questions"]:
            if row["paper"] != name:
                continue
            c = row["comparisons"]
            ref = (
                "、".join(
                    r["question_id"] + "（" + r["comparison_role"] + "）"
                    for r in row["evidence"]
                )
                or "当前样本无直接来源"
            )
            lines += [
                f"**第{row['order']}题，{row['points']}分：{'、'.join(row['reviewed_topics'])}**",
                "",
                c["language"] + c["condition_organization"],
                "",
                c["reasoning_depth"],
                "",
                c["similarities_and_differences"],
                "",
                "参照：" + ref + "。",
                "",
            ]
            if row["reference_gap"]:
                lines += ["参照缺口：" + row["reference_gap"], ""]
    lines += ["## 修前修后实证", ""]
    for case in report["before_after_examples"]:
        lines += [
            "- " + case["change_type"] + "：" + case["before"] + " " + case["after"],
            "",
        ]
    lines += [
        "## 仍不能由本报告认证的事项",
        "",
        "两卷估计完成时间分别为"
        + "、".join(
            str(v) + "分钟" for v in summary["paper_estimated_minutes"].values()
        )
        + "；这是设计估计，不能为匹配120分钟而改标签。特别是卷B的132分钟估计意味着可能偏紧，独立学生审查与实测需继续评估。",
        "",
        "干扰项的数值表达式与选项一致，不自动证明它来自声称的错误过程；由原始条件出发的错误操作才是更强证据。另行可复现实验见reports/phase4-distractor-audit.json（本次报告生成时"
        + (
            "已存在"
            if report["additional_error_model_experiment"]["present"]
            else "尚待补充"
        )
        + "）。即便路径可复现，也仍是设计假设，不是学生错误率实证。",
        "",
        "解答题难度依据来自条件理解、模型建立、论证和全范围/等号处理，不按小问数量或程序任务数评分。经典方法重用正常，不能证明全网首次原创。最终独立PDF审题若否决，作者对照不能覆盖该否决。",
        "",
    ]
    (ROOT / "reports/phase4-new-style-comparison.md").write_bytes(
        "\n".join(lines).encode("utf-8")
    )


if __name__ == "__main__":
    main()
