"""Exact, unit-checked solvers for explicit high-school physics models."""

from fractions import Fraction
import re

from subjects.physics_models import SOLVERS as ADDITIONAL_SOLVERS


_QUANTITY_LITERAL = re.compile(
    r"[+-]?(?:[0-9]{1,16}(?:\.[0-9]{0,16})?|\.[0-9]{1,16})(?:[eE][+-]?[0-9]{1,2})?"
    r"|[+-]?[0-9]{1,16}/[0-9]{1,16}"
)


def _require(problem, expected):
    for key, value in expected.items():
        actual = problem.get(key)
        if type(actual) is not type(value) or actual != value:
            raise ValueError(f"物理模型的适用条件缺失或不一致：{key}")


def _quantity(problem, key, units, *, minimum=None, strictly_positive=False):
    field = problem.get(key)
    if not isinstance(field, dict) or set(field) != {"value", "unit"}:
        raise ValueError(f"{key} 必须同时给出量值和单位")
    unit = field["unit"]
    if not isinstance(unit, str) or unit not in units:
        raise ValueError(f"{key} 的单位不符，允许 {', '.join(units)}")
    raw = field["value"]
    if type(raw) not in (int, float, str) or not _QUANTITY_LITERAL.fullmatch(str(raw)):
        raise ValueError(f"{key} 的量值必须为有限数")
    try:
        value = Fraction(str(raw)) * units[unit]
    except (ValueError, ZeroDivisionError) as error:
        raise ValueError(f"{key} 的量值必须为有限数") from error
    if (strictly_positive and value <= 0) or (minimum is not None and value < minimum):
        raise ValueError(f"{key} 超出物理量取值范围")
    return value


def _display(value):
    return value.numerator if value.denominator == 1 else str(value)


def _direction(velocity):
    if velocity > 0:
        return "东"
    return "西" if velocity < 0 else "静止"


def _velocity_description(velocity):
    if velocity == 0:
        return "速度为零"
    return f"速度大小为 {_display(abs(velocity))} 米每秒，方向向{_direction(velocity)}"


MASS = {"kg": 1, "g": Fraction(1, 1000)}
DISTANCE = {"m": 1, "cm": Fraction(1, 100)}
TIME = {"s": 1, "ms": Fraction(1, 1000)}
VELOCITY = {"m/s": 1, "km/h": Fraction(5, 18), "cm/s": Fraction(1, 100)}
FORCE = {"N": 1}
RESISTANCE = {"Ω": 1, "mΩ": Fraction(1, 1000)}
VOLTAGE = {"V": 1, "mV": Fraction(1, 1000)}


def _signed_motion(problem):
    _require(problem, {"positive_direction": "east", "one_dimensional": True,
                       "constant_net_force": True})
    mass = _quantity(problem, "mass", MASS, strictly_positive=True)
    initial = _quantity(problem, "initial_velocity", VELOCITY)
    force = _quantity(problem, "net_force", FORCE)
    time = _quantity(problem, "duration", TIME, minimum=0)
    acceleration = force / mass
    final = initial + acceleration * time
    displacement = (initial + final) * time / 2
    # Constant acceleration allows at most one interior zero of v(t).
    if initial * final < 0:
        turning = -initial / acceleration
        distance = abs(initial * turning / 2) + abs(final * (time - turning) / 2)
    else:
        distance = abs(displacement)
    if distance < abs(displacement):
        raise ValueError("速度积分与路程边界不一致")
    return {
        "answer": {"velocity_m_s": _display(final), "direction": _direction(final),
                   "displacement_m": _display(displacement), "distance_m": _display(distance)},
        "checks": ["质量、力、速度、时间统一到 SI 单位，力除以质量得到加速度",
                   "东向为正，合力与加速度同向，末速度符号与方向一致",
                   "用有符号速度积分得位移，遇区间内反向点分段求路程"],
        "unverified": ["仅在净力恒定、轨道足够长且可按质点建模时成立。"],
        "explanation": (
            f"由牛顿第二定律得加速度为 {_display(acceleration)} 米每二次方秒。"
            f"时段末{_velocity_description(final)}。"
            f"速度图像的有符号面积为 {_display(displacement)} 米，绝对面积为 {_display(distance)} 米。"
        ),
    }


def _parallel_circuit(problem):
    _require(problem, {"steady_dc": True, "switch_opens_only_second_branch": True,
                       "ideal_wires": True, "ohmic_resistors": True})
    emf = _quantity(problem, "emf", VOLTAGE, strictly_positive=True)
    inner = _quantity(problem, "internal_resistance", RESISTANCE, minimum=0)
    first = _quantity(problem, "first_resistance", RESISTANCE, strictly_positive=True)
    second = _quantity(problem, "second_resistance", RESISTANCE, strictly_positive=True)
    equivalent = first * second / (first + second)
    current = emf / (inner + equivalent)
    voltage = current * equivalent
    open_current = emf / (inner + first)
    open_voltage = open_current * first
    power_before, power_after = voltage**2 / first, open_voltage**2 / first
    if (voltage / first + voltage / second != current
            or emf * current != current**2 * inner + power_before + voltage**2 / second
            or emf * open_current != open_current**2 * inner + power_after):
        raise ValueError("节点电流或全电路功率不守恒")
    return {
        "answer": {"closed_source_current_A": _display(current),
                   "closed_first_power_W": _display(power_before),
                   "open_source_current_A": _display(open_current),
                   "open_first_power_W": _display(power_after)},
        "checks": ["电压和电阻单位一致，正电阻保证电路稳态解唯一",
                   "开关仅隔离第二支路，闭合时验证节点电流守恒",
                   "开关前后验证源功率、内阻损耗和外电路功率平衡"],
        "unverified": ["忽略开关暂态、导线阻抗和电阻随温度变化，结论仅适用于给出的欧姆模型。"],
        "explanation": (
            f"闭合时外电路等效电阻为 {_display(equivalent)} 欧姆。"
            f"全电路电流为 {_display(current)} 安培，路端电压为 {_display(voltage)} 伏，"
            f"第一支路功率为 {_display(power_before)} 瓦。"
            f"断开后只剩第一支路，源电流为 {_display(open_current)} 安培，"
            f"路端电压为 {_display(open_voltage)} 伏，第一支路功率为 {_display(power_after)} 瓦。"
        ),
    }


def _inelastic_collision(problem):
    _require(problem, {"positive_direction": "east", "stick": True,
                       "negligible_external_impulse": True, "one_dimensional": True,
                       "uniform_motion_until_collision": True})
    left_mass = _quantity(problem, "left_mass", MASS, strictly_positive=True)
    right_mass = _quantity(problem, "right_mass", MASS, strictly_positive=True)
    left_speed = _quantity(problem, "left_velocity", VELOCITY)
    right_speed = _quantity(problem, "right_velocity", VELOCITY)
    gap = _quantity(problem, "gap", DISTANCE, strictly_positive=True)
    if left_speed <= right_speed:
        raise ValueError("在相同惯性系内初始间距不会缩短，碰撞无法实现")
    time = gap / (left_speed - right_speed)
    momentum = left_mass * left_speed + right_mass * right_speed
    common = momentum / (left_mass + right_mass)
    loss = (left_mass * left_speed**2 + right_mass * right_speed**2
            - (left_mass + right_mass) * common**2) / 2
    expected_loss = left_mass * right_mass * (left_speed - right_speed)**2 / (2 * (left_mass + right_mass))
    if loss <= 0 or loss != expected_loss:
        raise ValueError("机械能减少量违反完全非弹性模型")
    return {
        "answer": {"collision_time_s": _display(time), "common_velocity_m_s": _display(common),
                   "direction": _direction(common), "kinetic_loss_J": _display(loss)},
        "checks": ["两个物体质量及初始间距均为正",
                   "后车速度大于前车速度，存在唯一正的碰撞时刻",
                   "有向动量守恒，独立用约化质量公式复核动能减少量"],
        "unverified": ["粘连由题设指定，模型不判断真实材料的形变和粘连概率。"],
        "explanation": (
            f"碰前间距以 {_display(left_speed - right_speed)} 米每秒缩小，"
            f"因此 {_display(time)} 秒后发生碰撞。"
            f"碰前总动量为 {_display(momentum)} 千克米每秒，粘连后两车共同的"
            f"{_velocity_description(common)}。"
            f"分别计算碰前和碰后总动能，两者之差为 {_display(loss)} 焦耳。"
        ),
    }


_SOLVERS = {
    **ADDITIONAL_SOLVERS,
    "signed_motion": _signed_motion,
    "parallel_circuit": _parallel_circuit,
    "inelastic_collision": _inelastic_collision,
}


def verify(problem):
    """Solve a supported structured problem independently of its proposed answer."""
    operation = problem.get("op") if isinstance(problem, dict) else None
    if not isinstance(operation, str) or operation not in _SOLVERS:
        raise ValueError("未支持的物理题型")
    return _SOLVERS[operation](problem)
