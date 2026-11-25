"""Models for bounded motion, graphs and evidence-based physics experiments."""

from fractions import Fraction

from gaokao import require

ACCELERATION = {"m/s^2": 1}
CURRENT = {"A": 1, "mA": Fraction(1, 1000)}


def number(value):
    require(type(value) in (str,int,float), "读数须是数值")
    try:
        return Fraction(str(value))
    except (ValueError, ZeroDivisionError, OverflowError) as error:
        raise ValueError("无效数值") from error


def outcome(answer, checks, explanation):
    return {"answer":answer,"checks":checks,"explanation":explanation,
            "unverified":["独立审查须核对题图、题面与程序规格一致。"]}


def select(options, target):
    require(tuple(options)==tuple("ABCD"), "选项键不完整")
    require(all(isinstance(v,list) and len(v)==len(target) for v in options.values()), "选项规格不完整")
    matches = [key for key, values in options.items() if tuple(map(number,values))==target]
    require(len(matches)==1, "选项须恰有一个正确")
    return matches[0]


def field_direction(p):
    from subjects.physics import DISTANCE, VOLTAGE, _quantity, _require
    _require(p, {"uniform":True})
    x = _quantity(p,"x_offset",DISTANCE,strictly_positive=True)
    y = _quantity(p,"y_offset",DISTANCE,strictly_positive=True)
    v0, vx, vy = (_quantity(p,k,VOLTAGE) for k in ("origin_potential","x_potential","y_potential"))
    vector = ((v0-vx)/x,(v0-vy)/y)
    require(any(vector),"零场无方向")
    return outcome(select(p["options"],vector),["电势差和长度量纲","两个正交电势梯度","选项真值唯一"],
                   "匀强场两个正交分量分别为对应电势降除以距离。")


def _pairs(rows, count=None):
    require(isinstance(rows,list) and len(rows)>=2 and (count is None or len(rows)==count)
            and all(isinstance(row,list) and len(row)==2 for row in rows),"数据点格式无效")
    return [tuple(map(number,row)) for row in rows]


def velocity_graph(p):
    from subjects.physics import _require
    _require(p, {"time_axis":"s","velocity_axis":"m/s"})
    pts = _pairs(p["points"])
    require(pts[0][0]==0 and all(y[0]>x[0] for x,y in zip(pts,pts[1:])),"时间轴不连续或乱序")
    displacement = distance = Fraction(0)
    for (start,u),(end,v) in zip(pts,pts[1:]):
        dt = end-start
        displacement += (u+v)*dt/2
        if u*v<0:
            zero = u/(u-v)
            distance += (abs(u)*zero+abs(v)*(1-zero))*dt/2
        else:
            distance += abs(u+v)*dt/2
    return outcome(select(p["options"],(displacement,distance)),["轴单位", "有向面积", "过零拆分", "选项唯一"],
                   "速度曲线与时间轴间有向面积给位移，正负分段的面积绝对值之和给路程。")


def terminal_data(p):
    from subjects.physics import VOLTAGE, _display, _quantity, _require
    _require(p, {"ideal_meters":True,"constant_emf_and_resistance_model":True,"current_unit":"A","voltage_unit":"V"})
    max_i = _quantity(p,"current_range",CURRENT,strictly_positive=True)
    max_u = _quantity(p,"voltage_range",VOLTAGE,strictly_positive=True)
    tol = _quantity(p,"tolerance",VOLTAGE,minimum=0)
    (i1,v1),(i2,v2),(i3,v3) = _pairs(p["readings"],3)
    require(0<i1<i2<i3<=max_i and all(0<v<=max_u for v in (v1,v2,v3)),"数据超量程或电流顺序不符")
    r = (v1-v3)/(i3-i1)
    emf = v1+i1*r
    require(r>=0 and emf>0,"电源参数不可实现")
    residual = abs(v2-(emf-i2*r))
    return outcome(dict(emf_V=_display(emf),resistance_ohm=_display(r),middle_error_V=_display(residual),
                        within_tolerance=residual<=tol,open_in_range=emf<=max_u,evidence="sample_only"),
                   ["带单位量程并核查全部读数","校验非负内阻","以给定容差检查残差","有限观测不支持全范围结论"],
                   "首末两点给直线。开路估值与量程比较，中间读数与直线预测比较。")


def braking_crossing(p):
    from sympy import Rational, solve, symbols
    from subjects.physics import DISTANCE, TIME, VELOCITY, _display, _quantity, _require
    _require(p, {"positive_initial_motion":True,"stays_at_rest":True})
    v0 = _quantity(p,"initial",VELOCITY,strictly_positive=True)
    a = _quantity(p,"thrust",ACCELERATION,strictly_positive=True)
    boost = _quantity(p,"thrust_time",TIME,strictly_positive=True)
    b = _quantity(p,"braking",ACCELERATION,strictly_positive=True)
    target = _quantity(p,"target",DISTANCE,strictly_positive=True)
    v = v0+a*boost
    x = (v0+v)*boost/2
    stop = v/b
    # A stop exactly at the target is a valid first encounter.
    require(x<target<=x+v*stop/2, "目标不在制动阶段的可达范围")
    t = symbols("t",real=True)
    roots = solve(Rational(b)*t*t/2-Rational(v)*t+Rational(target-x),t)
    admissible = [t for t in roots if 0<t<=Rational(stop)]
    require(len(admissible)==1,"制动阶段首达解不唯一")
    # Compare energy to the motion solution at the accepted time.
    velocity = Rational(v)-Rational(b)*admissible[0]
    require((velocity**2-Rational(v*v-2*b*(target-x))).simplify()==0,"功与运动学求解不一致")
    return outcome(dict(switch_speed=_display(v),switch_distance=_display(x),
                        target_time_after_switch=str(admissible[0]),total_stop_time=_display(boost+stop)),
                   ["统一量纲","根据制动时间窗排根","速度平方与功关系交叉核对"],
                   "制动只持续到速度降为零。超过这段时间的方程根不属于题设运动。")


def plate_deflection(p):
    from subjects.physics import DISTANCE, VELOCITY, _display, _quantity, _require
    _require(p, {"uniform_vertical_field":True,"field_free_drift":True,"ignores_gravity":True,
                 "starts_centered":True,"charge_sign":"unknown"})
    speed = _quantity(p,"speed",VELOCITY,strictly_positive=True)
    length, gap, drift, offset = (_quantity(p,k,DISTANCE,strictly_positive=True)
                                   for k in ("length","gap","drift","screen_offset"))
    ratio = _quantity(p,"abs_charge_to_mass",{"C/kg":1},strictly_positive=True)
    t1,t2 = length/speed,drift/speed
    acceleration = offset/(t1*t1/2+t1*t2)
    exit_offset = acceleration*t1*t1/2
    require(exit_offset<gap/2,"到达屏幕前将撞板，理想路径不可实现")
    return outcome(dict(field_time_s=_display(t1),drift_time_s=_display(t2),
                        field_N_C=_display(acceleration/ratio),
                        spots_m={"positive":_display(offset),"negative":_display(-offset)},
                        exit_abs_m=_display(exit_offset),clears_plate=True),
                   ["电荷质量比与量纲","连接加速和漂移","遍历两种电荷符号","检查板内最大偏移"],
                   "两种电荷符号产生镜像轨迹。板内偏移绝对值单调增加，应比较出口偏移与半间距。")


SOLVERS = dict(field_direction=field_direction,velocity_graph=velocity_graph,
               terminal_data=terminal_data,braking_crossing=braking_crossing,plate_deflection=plate_deflection)
