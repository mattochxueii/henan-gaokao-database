"""Bounded chemistry models for redox, equilibrium, structure and experiment evidence."""

from fractions import Fraction

from gaokao import require

CELL = "https://openstax.org/books/chemistry-2e/pages/17-2-galvanic-cells"
EQUILIBRIUM = "https://openstax.org/books/chemistry-2e/pages/13-3-shifting-equilibria-le-chateliers-principle"
INTERMOLECULAR = "https://openstax.org/books/chemistry-2e/pages/10-1-intermolecular-forces"
ESTER = "https://openstax.org/books/organic-chemistry/pages/21-6-chemistry-of-esters"


def assumptions(p, expected):
    for key, value in expected.items():
        require(type(p.get(key)) is type(value) and p[key] == value,
                f"化学模型缺少适用条件或条件冲突：{key}")


def quantity(p, key, *, nonnegative=False):
    value = p[key]
    require(type(value) in (int, float, str), f"无效量值：{key}")
    value = Fraction(str(value))
    require(value >= 0 if nonnegative else value > 0, f"量值超出范围：{key}")
    return value


def result(answer, checks, note, explanation, *sources):
    return {"answer":answer,"checks":checks,"unverified":[note],
            "explanation":explanation,"science_sources":list(sources)}


def single(options, assertions):
    require(isinstance(options,dict) and set(options)==set("ABCD"), "缺少四个选择项")
    require(all(isinstance(v,str) and v in assertions for v in options.values()), "选择项含未知断言")
    correct=[key for key, meaning in options.items() if assertions[meaning]]
    require(len(correct)==1, "选择题有多项正确或无正确项")
    return correct[0]


def galvanic_choice(p):
    assumptions(p,{"anode":"Zn","cathode":"Cu","anolyte":"ZnSO4","catholyte":"CuSO4","bridge":"KNO3"})
    # Reduction consumes two electrons per deposited Cu(0). Oxidation
    # delivers the same amount of charge for each Zn(II) formed.
    metal_charge = {"zinc_atom":0,"zinc_ion":2,"copper_ion":2,"copper_atom":0}
    donated = metal_charge["zinc_ion"]-metal_charge["zinc_atom"]
    taken = metal_charge["copper_ion"]-metal_charge["copper_atom"]
    require(donated==taken, "标准电池的半反应电子数不守恒")
    answer=single(p["options"],{"electrons_cu_to_zn":False,"two_e_per_cu":taken==2,
               "one_e_per_cu":taken==1,"anions_to_copper":False,"anode_mass_increases":False,
               "zinc_anode_oxidizes":True})
    return result(answer,["核对半电池和电解质","核对电子流、电荷补偿及析铜计量","选择唯一性"],
                  "真实电流、液接电势和副反应不由此模型预测。",
                  "负极锌失电子成 Zn²⁺，正极 Cu²⁺ 得两个电子成铜，盐桥阴离子补偿锌半电池。",CELL)


# Neutral Lewis connectivity and counts for this pair only.
MOLECULES = {"ethanol":("CH3","CH2","OH"),"dimethyl_ether":("CH3","O","CH3")}


def structure_choice(p):
    assumptions(p,{"pair":["ethanol","dimethyl_ether"],"same_pressure":True})
    left,right = (MOLECULES[k] for k in p["pair"])
    from collections import Counter
    def composition(fragments):
        from re import findall

        atoms = Counter()
        for fragment in fragments:
            for element, count in findall(r"([A-Z][a-z]?)(\d*)", fragment):
                atoms[element] += int(count or 1)
        return atoms
    answer=single(p["options"],{"different_formula":composition(left)!=composition(right),
                  "ether_higher_bond_polarity":False,"ethanol_oh_hydrogen_bond":"OH" in left and "OH" not in right,
                  "ether_cannot_accept_h_bond":False,"same_formula":composition(left)==composition(right)})
    return result(answer,["由连接片段重新统计原子","辨别氢键给体与受体","同压下比较沸点"],
                  "仅覆盖这两个已知分子，不可泛化为按氢键数预测任意物质沸点。",
                  "两者分子式相同。纯乙醇有 O—H 给体和氧受体；醚氧可作受体，纯二甲醚自身没有 O—H 给体。",INTERMOLECULAR)


def dimer_equilibrium(p):
    from sympy import Rational, solve, symbols

    assumptions(p,{"reaction":"N2O4(g)<=>2NO2(g)","closed":True,"isothermal":True,
                   "ideal_gas":True,"only_reaction":True,"unit":"mol/L"})
    dimer = quantity(p,"dimer")
    monomer = quantity(p,"monomer")
    ratio = quantity(p,"volume_ratio")
    kc = monomer**2/dimer
    d0,m0 = map(Rational,(dimer/ratio,monomer/ratio))
    q = monomer**2/dimer/ratio
    x = symbols("x",real=True)
    roots = solve((m0+2*x)**2-Rational(kc)*(d0-x),x)
    legitimate = [value for value in roots if -m0/2<value<d0]
    require(len(legitimate)==1, "找不到唯一满足浓度范围的平衡解")
    extent = legitimate[0]
    new_dimer = (d0-extent).simplify()
    new_monomer = (m0+2*extent).simplify()
    require((2*new_dimer+new_monomer-2*d0-m0).simplify()==0 and
            (new_monomer**2-Rational(kc)*new_dimer).simplify()==0,
            "平衡或氮原子守恒交叉检查失败")
    expected = "forward" if q<kc else "reverse" if q>kc else "unchanged"
    require((extent>0 and expected=="forward") or (extent<0 and expected=="reverse")
            or (extent==0 and expected=="unchanged"),"反应商与进度符号冲突")
    return result({"Kc":str(kc),"Q_after":str(q),"direction":expected,
                   "dimer_final":str(new_dimer),"monomer_final":str(new_monomer)},
                  ["明确温度、体系和理想近似","计算瞬时反应商","检查物理根","独立核对氮原子守恒"],
                  "平衡模型不推断动力学或实测数据精度。",
                  "体积改变后的初值与随后的新平衡区别计算。反应进度须使两组分浓度均为正。",EQUILIBRIUM)


def iodine_evidence(p):
    assumptions(p,{"same_conditions":True,"stoichiometry":"1:1"})
    require(type(p["possible_co_reductants"]) is bool and p["possible_co_reductants"],
            "需明确未排除共存还原物，不能把给定表当成特异性测量")
    c = quantity(p,"iodine_mol_l")
    v = quantity(p,"sample_ml")
    blank = quantity(p,"blank_ml",nonnegative=True)
    sample = quantity(p,"sample_read_ml")-blank
    spiked = quantity(p,"spiked_read_ml")-blank
    spike_mol = quantity(p,"spike_mol")
    require(0<=sample<=spiked, "空白与加标读数的净消耗量不自洽")
    recovery = c*(spiked-sample)/1000/spike_mol*100
    return result({"iodine_equivalent_mol_L":str(c*sample/v),
                   "spike_recovery_percent":int(recovery) if recovery.denominator==1 else str(recovery),
                   "native_vitamin_c_identified":False},
                  ["扣除空白并核对体积","计算加标增量","区分回收率与分析选择性"],
                  "还原性杂质和基质干扰无法由同一组模拟读数辨认。须评审鉴别对照的适用条件。",
                  "在相同条件下加标前后差值可计算增量回收率，原有碘消耗仍可能包括共存还原物。")


# Saturated, acyclic, monofunctional esters split into the two carbon skeletons.
ESTERS = {"ethyl_acetate":(2,2,"ethanol"),"methyl_propionate":(3,1,"methanol"),
          "propyl_formate":(1,3,"propanol")}


def ester_inference(p):
    assumptions(p,{"complete_saponification":True,"only_reaction":True,"pure_ester":True,
                   "complete_alcohol_combustion":True})
    candidates=p["candidates"]
    require(isinstance(candidates,list) and len(candidates)>1 and len(set(candidates))==len(candidates)
            and all(name in ESTERS for name in candidates),"有机候选超出已核证的酯结构模型")
    ester=quantity(p,"ester_mol")
    carbon=quantity(p,"carbon_dioxide_mol")
    base=quantity(p,"hydroxide_mol")
    require(base>=ester,"碱不足，完全皂化假设不成立")
    choices=[name for name in candidates if ESTERS[name][1]*ester==carbon]
    require(len(choices)==1, "燃烧数据与候选不符或不能唯一辨认")
    name,=choices
    acid_c,alcohol_c,alcohol=ESTERS[name]
    total=acid_c+alcohol_c
    formula=f"C{total}H{2*total}O2"
    if "formula_claim" in p:
        require(p["formula_claim"]==formula,"分子式与酯骨架不一致")
    return result({"ester":name,"formula":formula,"alcohol":alcohol,
                   "hydroxide_remaining_mol":str(base-ester)},
                  ["用燃烧碳守恒识别醇骨架","核对候选唯一性和总分子式","按单酯水解 1∶1 验算碱"],
                  "反应式写法和科学等效解法由独立审查核对。",
                  "每摩尔单酯提供一摩尔醇。醇的平均每分子碳数等于 CO₂ 与酯的量之比。",ESTER)


# Ion positions per conventional cell for these ideal rock-salt and cesium-chloride cells.
CELLS = {"rock_salt": {"Na": {"edge":12,"body":1}, "Cl":{"corner":8,"face":6}},
         "cesium_chloride":{"Cs":{"body":1}, "Cl":{"corner":8}}}
SHARES = {"corner":Fraction(1,8),"edge":Fraction(1,4),"face":Fraction(1,2),"body":Fraction(1)}
DOMAINS = {"BF3":(3,0),"NH3":(3,1),"H2O":(2,2),"CO2":(2,0)}
SHAPES = {(3,0):"trigonal_planar",(3,1):"trigonal_pyramidal",(2,2):"bent",(2,0):"linear"}


def cubic_occupancy(p):
    assumptions(p,{"conventional_cell":True})
    ideal = CELLS.get(p["type"])
    require(ideal is not None and ideal==p["sites"],"晶胞占位与已核模型不一致")
    counts = {atom:sum(n*SHARES[site] for site,n in sites.items()) for atom,sites in ideal.items()}
    require(all(value.denominator==1 for value in counts.values()),"晶胞共享后原子计数无效")
    return result({atom:int(value) for atom,value in counts.items()},["核对角、棱、面及内部位置","按占有比例分配晶胞粒子"],
                  "只支持已登记理想晶胞，实际缺陷和转变不在覆盖范围。",
                  "角、棱、面上的粒子由相邻晶胞共享，胞内粒子完全属于一个晶胞。")


def vsepr(p):
    assumptions(p,{"isolated_neutral_molecule":True})
    pair = DOMAINS.get(p["molecule"])
    require(pair is not None,"分子未纳入已核构型")
    bonding,lone = pair
    return result({"bond_domains":bonding,"lone_pairs":lone,"shape":SHAPES[pair]},
                  ["分开统计成键方向与孤电子对","按构型模型确定分子几何"],
                  "理想局部构型不提供实测键角。","双键按一个成键电子域计入。")


SOLVERS = dict(galvanic_choice=galvanic_choice,structure_choice=structure_choice,
               dimer_equilibrium=dimer_equilibrium,iodine_evidence=iodine_evidence,ester_inference=ester_inference,
               cubic_occupancy=cubic_occupancy,vsepr=vsepr)
