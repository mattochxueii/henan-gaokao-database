"""Compute independent checkpoints from values transcribed from the student PDFs.

The script receives only a student PDF and a subject. It has no candidate or
answer-key inputs. The tables transcribed below cover only the named checks.
"""

import argparse
from collections import Counter
from fractions import Fraction as F
import hashlib
from itertools import product
import json
from pathlib import Path
import re

from pypdf import PdfReader
import sympy as S


def physics():
    u, resistance, field, width = S.symbols("u R B l", positive=True)
    current = field * width * u / resistance
    entry = width / u
    charge = S.simplify(current * entry)
    heat = S.simplify(current**2 * resistance * entry)
    assert S.simplify(charge.subs(u, 2*u)/charge) == 1
    assert S.simplify(heat.subs(u, 2*u)/heat) == 2

    a, b = F("2.0"), F("2.0")
    velocities = [F(0), F(4)]
    slips = [(b-v)**2/(2*a) for v in velocities]
    match_positions = [(b*b-v*v)/(2*a if v < b else -2*a) for v in velocities]
    assert slips == [1, 1] and match_positions == [1, 3]
    assert [S.simplify(S.cos(2*S.pi*x/F("0.8"))) for x in (F(".2"), F(".1"), F(".3"), F(".4"))] == [
        0, S.sqrt(2)/2, -S.sqrt(2)/2, -1]

    m, g, stiffness = S.symbols("m g k", positive=True)
    max_compression = 5*m*g/stiffness
    speed_sq = S.simplify((stiffness*max_compression**2/2-2*m*g*max_compression)/m)
    assert speed_sq/(2*g) == 5*g*m/(4*stiffness)
    capacitance, voltage = S.symbols("C U", positive=True)
    final_voltage = capacitance*voltage/(3*capacitance)
    heat_cap = S.expand(capacitance*voltage**2/2 - 3*capacitance*final_voltage**2/2)
    assert heat_cap == capacitance*voltage**2/3

    # A -> B: (A 10.00, B 8.00); B -> A: (B 10.00, A 20.00), in ms.
    speed = [F("0.012")/F(t) for t in (".010", ".008", ".010", ".020")]
    forward = (speed[1]**2-speed[0]**2)/(2*F(".500"))
    reverse = (speed[3]**2-speed[2]**2)/(2*F("-.500"))
    drag = (reverse-forward)/2
    assert forward == F(".81") and reverse == F("1.08") and drag == F(".135")

    # Coordinates read from the graph, with 100 mA converted to 0.100 A.
    u0 = F("4.80")
    slope = (F("2.40")-u0)/F(".100")
    r = (-slope)/(1+slope/F(120))
    e = u0*(1+r/F(120))
    assert (slope, r, e) == (F(-24), F(30), F(6))

    pressure = 100000 + F(20)*10/F(".010")
    t_stop = F(300)*4/3
    p_final = pressure*500/t_stop
    work = pressure*F(".001")
    assert (t_stop, p_final, work, 720-work) == (400, 150000, 120, 600)

    x = S.Symbol("x", positive=True)
    roots = S.solve(16*x*x+4*x-16, x)
    assert roots == [(S.sqrt(65)-1)/8]
    threshold, = S.solve(16*x*x-4*x, x)
    assert threshold == S.Rational(1, 4) and 32*threshold > 4
    v0 = 2*S.sqrt(16*threshold**2+4*threshold)
    assert v0 == 2*S.sqrt(2)

    # The calculation uses L=v=1, so both reach and landing-depth units are explicit.
    s = S.Symbol("s", positive=True)
    reaches_at = S.sqrt(2)/2
    normal_speed = S.sqrt(1-s*s)
    first_time = 2/(normal_speed+S.sqrt(S.Rational(1, 2)-s*s))
    reach_equation = normal_speed*first_time-first_time**2/8
    for test_s in (S.Rational(1, 4), S.Rational(1, 2), reaches_at):
        assert S.simplify(reach_equation.subs(s,test_s)) == 1
    depth = s/(1+normal_speed)+s*first_time
    assert S.simplify(depth.subs(s, S.Rational(1, 2))) == 1
    assert depth.subs(s,S.Rational(2, 5)).evalf() < 1 < depth.subs(s,S.Rational(3, 5)).evalf()
    assert (2*(1-s*s)).subs(s,S.Rational(3, 4)) < 1
    return {
        "6": {"double_speed_charge_ratio": 1, "heat_ratio": 2},
        "7": {"slip_m": [1, 1], "match_position_m": [1, 3]},
        "8": {"normalized_spatial_factors": ["0", "sqrt(2)/2", "-sqrt(2)/2", "-1"]},
        "9": {"post_separation_rise": str(5*g*m/(4*stiffness))},
        "10": {"end_voltage": str(final_voltage), "heat": str(heat_cap)},
        "11": {"forward_m_s2": float(forward), "reverse_m_s2": float(reverse), "drag_per_kg": float(drag)},
        "12": {"slope_ohm": int(slope), "internal_ohm": int(r), "emf_V": int(e)},
        "13": {"stop_K": 400, "final_Pa": 150000, "work_J": 120, "delta_U_J": 600},
        "14": {"compression_m": str(roots[0]), "critical_speed_m_s": str(v0)},
        "15": {"strict_field_entry": "s<1", "plane_reach_inclusive": str(reaches_at),
               "detector_threshold": "1/2", "first_arrival_branch": "checked at 1/4, 1/2, sqrt(2)/2"},
    }


def chemistry():
    assert (18-16)*2 == 4
    offsets = list(product((-1, 0, 1), repeat=3))
    nearest = [d for d in offsets if sum(abs(x) for x in d) == 1]
    constituents = (8//8, 1, 6//2)
    assert len(nearest) == 6 and constituents == (1, 1, 3)
    extent = (1-F(".80"))/2
    assert extent == F(".10") and 2*extent/F(".80") == F("0.25")
    x = S.Symbol("x", real=True)
    assert [s for s in S.solve(x*x/(1-x)**2-100, x) if 0 < s < 1] == [S.Rational(10, 11)]

    # Coordinates of a signed formula vector are O, H, Fe, and net charge.
    peroxide_reactants = S.Matrix([2, 2, 0, 0])+2*S.Matrix([0, 0, 1, 2])+2*S.Matrix([0, 1, 0, 1])
    peroxide_products = 2*S.Matrix([0, 0, 1, 3])+2*S.Matrix([1, 2, 0, 0])
    assert peroxide_reactants == peroxide_products
    assert S.Matrix([2, 4, 0, 0]) == S.Matrix([2, 0, 0, 0])+S.Matrix([0, 4, 0, 4])+S.Matrix([0, 0, 0, -4])
    phs = [3, F("4.5"), 7]
    hydroxide = [10**(float(p)-14) for p in phs]
    feasible_phs = [float(p) for p, oh in zip(phs, hydroxide)
                    if min(.0100, 1e-38/oh**3) <= 1e-8 and .100*oh**2 < 3e-17]
    assert feasible_phs == [4.5]
    n_zinc = (F(".400")+F(".0200"))*F(".750")
    charge = 2*n_zinc/F(".800")
    net_acid = charge-(charge-2*n_zinc)
    assert (n_zinc,charge,net_acid) == (F(".315"),F(".7875"),F(".630"))

    # Blank-correct each independent aliquot at its own volume and endpoint.
    total = (F("13.80")-F(".30"))*F(".01000")/F("50.00")
    ca = (F("8.60")-F(".10"))*F(".01000")/F("50.00")
    assert ca == F(".00170") and total-ca == F(".00100")

    reacted = F(".60")
    acetaldehyde = reacted*F(2, 3)
    ethylene = reacted-acetaldehyde
    original_moles = 1+reacted
    pa, pb, pc = [(100*n)/original_moles for n in (1-reacted, acetaldehyde, ethylene)]
    kp1, kp2 = (pb/100)**2/(pa/100), (pc/100)**2/(pa/100)
    pinert = 100*(original_moles+F(".50"))/original_moles
    assert (pa, pb, pc, kp1, kp2, pinert) == (
        25, 25, F("12.5"), F(".250"), F(".0625"), F("131.25"))

    # Enumerate mirror orbits with the aldehyde carbon fixed at ring index zero.
    arrangements = [(a, b) for a, b in product(range(1, 6), repeat=2) if a != b]
    unique = {min((a, b), (6-a, 6-b)) for a, b in arrangements}
    assert len(unique) == 10 and all(a != 6-a or b != 6-b for a, b in arrangements)
    return {
        "2": {"difference_in_neutrons_per_molecule": 4},
        "5": {"nearest_X": len(nearest), "constituents_A_B_X": constituents},
        "7": {"ammonia_mole_fraction": float(2*extent/F(".80")), "nitrogen_conversion": float(extent/F(".250"))},
        "14": {"physical_extent_fraction": "10/11"},
        "15": {"balanced_oxidation_and_anode": True, "viable_pH": feasible_phs,
               "charge_unit_F": float(charge), "net_protons_mol": float(net_acid)},
        "16": {"calcium_mol_per_L": float(ca), "magnesium_mol_per_L": float(total-ca)},
        "17": {"partial_pressures_kPa": [float(pa), float(pb), float(pc)], "Kp": [float(kp1), float(kp2)],
               "inert_feed_pressure_kPa": float(pinert)},
        "18": {"ordered_placements": len(arrangements), "isomer_orbits": len(unique)},
    }


def biology():
    assert 60*(1-F(60, 120)) == 30
    assert (1/F(".20"))/(1/F(".20")**2) == F(1, 5)
    red_classes = set(product(("R", "r"), ("R", "Y"))) - {("r", "Y")}
    assert len(red_classes) == 3 and ("r", "R") in red_classes

    light = (0, 50, 100, 200, 400)
    group_a, group_b = (-3, -1, 0, 5, 8), (-2, 0, 3, 5, 5)
    compensation = [light[values.index(0)] for values in (group_a, group_b)]
    totals = [values[-1]-values[0] for values in (group_a, group_b)]
    assert compensation == [100, 50] and totals == [11, 7]
    control, hormone, inhibitor, combined = 100, 58, 98, 96
    assert control-hormone > 5 and combined-hormone > 5
    assert abs(inhibitor-control) <= 5 and abs(combined-inhibitor) <= 5
    density = F(".30")*12+F(".70")*4
    assert density == F("6.4")

    genotype_counts = Counter(
        ("".join(sorted(a)), "".join(sorted(b)))
        for a, b in product(product("Aa", repeat=2), product("Bb", repeat=2))
    )

    def color(genotype):
        a, b = genotype
        if a == "aa" and b == "bb":
            return "aborted"
        if "A" not in a:
            return "white"
        return "purple" if "B" in b else "yellow"

    phenotypes = Counter()
    for genotype, count in genotype_counts.items():
        phenotypes[color(genotype)] += count
    yellow_total = phenotypes["yellow"]
    a_given_yellow = sum(
        F(a.count("a"), 2)*F(count, yellow_total)
        for (a, b), count in genotype_counts.items() if color((a, b)) == "yellow"
    )
    assert phenotypes == {"purple": 9, "yellow": 3, "white": 3, "aborted": 1}
    assert a_given_yellow**2 == F(1, 9)
    assert [color(("Aa", "".join(sorted(b+"b")))) for b in ("B", "b")] == ["purple", "yellow"]
    small, large = [F("8.0"), F("7.6")], [F("5.0"), F("4.9")]
    assert all(s > l for s, l in zip(small, large))
    return {
        "11": {"growth_multiple_of_r": 30},
        "12": {"direct_to_indirect": "1:5"},
        "13": {"red_heterozygote_proportion": "1/3"},
        "17": {"light_compensation": compensation, "gross_CO2": totals},
        "18": {"hormone_difference": hormone-control, "with_inhibitor_difference": combined-inhibitor},
        "19": {"weighted_plants_per_square_meter": float(density)},
        "20": {"phenotypes": phenotypes, "abortion_in_yellow_crosses": str(a_given_yellow**2)},
        "21": {"small_bead_advantage_mmol_round_1_and_3": [float(s-l) for s, l in zip(small, large)]},
    }


if __name__ == "__main__":
    checks = {"physics": physics, "chemistry": chemistry, "biology": biology}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("subject", choices=checks)
    parser.add_argument("student_pdf", type=Path)
    args = parser.parse_args()
    number_counts = {"physics": 15, "chemistry": 18, "biology": 21}
    pages = [p.extract_text() for p in PdfReader(args.student_pdf).pages]
    printed = [int(n) for page in pages for n in re.findall(r"(?m)^\s*(\d+)\.\s*（\d+分）", page)]
    assert printed == list(range(1, number_counts[args.subject]+1))
    assert not any("参考答案与解析" in page for page in pages)
    result = checks[args.subject]()
    print(json.dumps({
        "subject": args.subject, "scope": "partial_calculation_checks_only",
        "input": "student PDF and separately transcribed visible numbers",
        "paper_sha256": hashlib.sha256(args.student_pdf.read_bytes()).hexdigest(),
        "checked_question_count": len(result), "checkpoints": result,
    }, ensure_ascii=False, indent=2))
