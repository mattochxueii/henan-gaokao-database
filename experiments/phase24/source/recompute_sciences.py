"""Independent arithmetic, boundary checks and enumeration from the student pages."""
import argparse
from collections import Counter
from fractions import Fraction as F
from itertools import product
from pathlib import Path
import sys

SOURCE = Path(__file__).resolve().parent
ROOT = SOURCE.parents[2]
sys.path[:0] = [str(ROOT / "scripts"), str(SOURCE.parents[1] / "phase22/source")]
import check_exact
from gaokao import digest, require
from pypdf import PdfReader
from storage import atomic_json


def physics():
    data = check_exact.physics()
    gradient = (F(17, 10) - F(1, 2)) / (9 - 6)
    threshold = 6 - F(1, 2) / gradient
    outer_period = 4 ** F(3, 2)
    synodic_period = 1 / (1 - F(1, int(outer_period)))
    n, r_primary, r_secondary = 2, 5, 5
    reflected = n ** 2 * r_secondary
    rms = F(120 * reflected, reflected + r_primary) / n

    # Express all lengths in units of L. The entry condition is strict; touching the
    # screen at x=4L stops the particle even when horizontal velocity is zero there.
    def trajectory(radius):
        crosses = radius > 1
        x_max = 2 + radius if crosses else None
        return {"r_over_L": radius, "enters_II": crosses, "furthest_x_over_L": x_max,
                "returns_with_screen": crosses and x_max < 4}

    cases = [trajectory(r) for r in (F(3, 4), F(1), F(3, 2), F(2), F(9, 4))]
    assert [row["returns_with_screen"] for row in cases] == [False, False, True, False, False]
    assert threshold == F(19, 4) and synodic_period == F(8, 7) and rms == 48
    # At r=2L the entry sine is 1/2, so the second arc is 240 degrees.
    chord_squared = 4 * (F(2) ** 2 - 1)
    duration_in_pi_m_over_qB = F(240, 180)
    assert chord_squared == 12 and duration_in_pi_m_over_qB == F(4, 3)
    data.update({
        1: {"slope": gradient, "threshold_in_1e14_Hz": threshold},
        2: {"outer_period_over_T": int(outer_period), "same_ray_interval_over_T": synodic_period},
        4: {"equivalent_primary_load_ohm": reflected, "secondary_RMS_V": rms},
        14: {"cases": cases, "PQ_squared_over_L_squared": chord_squared,
             "transit_in_pi_m_over_qB": duration_in_pi_m_over_qB},
    })
    return data


def chemistry():
    data = check_exact.chemistry()
    # Vectors in order Ca, Mg, C, H, O, charge. Then separately check filtrate
    # speciation and net strong base demand under the stated pH regime.
    lhs = [(1,0,0,0,0,2), (0,1,0,0,0,2), (0,0,1,1,3,-1), (0,0,0,1,1,-1)]
    rhs = [(1,0,1,0,3,0), (0,1,0,2,2,0), (0,0,1,0,3,-2), (0,0,0,2,1,0)]

    def tally(species, coefficients):
        return [sum(v * n for v, n in zip(row, coefficients, strict=True)) for row in zip(*species)]

    totals = [tally(lhs, (1,1,2,4)), tally(rhs, (1,1,1,2))]
    assert totals[0] == totals[1]
    pilot = [(F(9,2),44,100), (F(11,2),2,100), (F(6),1,100), (F(21,2),78,F(3,5))]
    acceptable = [pH for pH, al, mg in pilot if al <= 2 and mg >= 98]
    assert min(acceptable) == F(11,2) and pilot[-1][1] > pilot[1][1]
    collected = (F(9,10) - F(12,100) / 4) / 2 * 74
    assert collected == F(3219,100)
    titrant = F(20,1000)
    net_mol = titrant * (F(26,1000) - F(14,1000)) / 2
    treated_mol = titrant * (F(20,1000) - F(14,1000)) / 2
    blank_consumption = F(2,10000) - titrant * F(14,1000) / 2
    assert net_mol / F(1,100) == F(12,1000) and blank_consumption * 1000 == F(6,100)
    data.update({
        6: {"atoms_and_charge": totals, "hydroxide_deprotonation": 2, "hydroxide_precipitation": 2},
        15: {"balanced_leach": data[15]["stoichiometric_balance"], "minimum_tested_pH": min(acceptable),
             "high_pH_Al_dissolved_percent": pilot[-1][1], "product_g": collected},
        16: {"original_mol_L": net_mol / F(1,100), "matrix_consumption_mmol": blank_consumption * 1000,
             "lost_mol_per_L_min": (net_mol - treated_mol) / F(1,100) / 10,
             "unremoved_solid_error": "continued peroxide decomposition and iodide oxidation have opposite signs"},
    })
    return data


def biology():
    result = {}
    result[3] = {"high_to_middle_increment_A": 6 - 5, "high_to_middle_increment_B": 16 - 4,
                 "transfer_rate_A_over_B_at_16": F(6,16)}
    aerobic = F(4,6)
    anaerobic = F(8 - 4,2)
    result[4] = {"anaerobic_glucose_share": anaerobic / (aerobic + anaerobic)}
    allele_a = F(30,100)
    result[7] = 2 * allele_a * (1 - allele_a)
    result[8] = {"single_depolarization_mV": -55 - (-70), "sum_stimulus_depolarization_mV": -63 - (-70)}
    result[10] = {"without_M_ABA_penalty_pp": 72 - 36, "with_M_ABA_penalty_pp": 76 - 70}
    result[11] = {"population_using_visible_marks": 80 * 60 // 12}
    assimilated = 900 - 300
    result[12] = {"insect_assimilation": assimilated, "bird_efficiency": F(120,assimilated),
                  "insect_growth": assimilated - 400}
    result[13] = {"remaining_relative_activity": [F(2,10),F(6,9)]}
    result[15] = F(21+19,400)
    result[17] = {"gross_CO2_enriched": [17+2,13+3], "relative_stomatal_conductance_ratio": F(1,2)}
    result[18] = {"block_versus_sham_hormone": 1-2, "rescue_versus_block_proliferation": 71-98}
    weights = F(2,5), F(3,5)
    cover_before = sum(w*c for w,c in zip(weights, (50,20), strict=True))
    cover_after = sum(w*c for w,c in zip(weights, (20,15), strict=True))
    result[19] = {"after_percent": cover_after, "decrease_pp": cover_before-cover_after}

    def zygote(g1, g2):
        return "".join("".join(sorted(alleles)) for alleles in zip(g1, g2))

    def phenotype(g):
        if g == "aabb": return "nonviable"
        if "A" in g and "B" in g: return "purple"
        return "red" if "A" in g else "white"

    parental = ("AB","Ab","aB","ab")
    f2 = Counter(zygote(p, q) for p, q in product(parental, repeat=2))
    purple_with_ab_gamete = sum(count for g, count in f2.items() if phenotype(g) == "purple" and g == "AaBb")
    purple_count = sum(count for g, count in f2.items() if phenotype(g) == "purple")
    cross = Counter(phenotype(zygote(p, q)) for p, q in product(parental, ("aB","ab")))
    result[20] = {"purple_ab_gamete": F(purple_with_ab_gamete, purple_count) / 4,
                  "cross_all_zygotes": dict(cross)}
    total_kb = F(4)+F(12,10)
    short_forward = F(8,10)+F(3,10)
    short_reverse = F(8,10)+(F(12,10)-F(3,10))
    result[21] = {"forward_bands_kb":[total_kb-short_forward,short_forward],
                  "reverse_bands_kb":[total_kb-short_reverse,short_reverse],"paired_primer_labels":"P/R"}
    assert result[4]["anaerobic_glucose_share"] == F(3,4)
    assert result[7] == F(21,50) and result[19] == {"after_percent": 17, "decrease_pp": 15}
    assert cross == {"purple":3,"red":1,"white":3,"nonviable":1}
    assert result[20]["purple_ab_gamete"] == F(1,9)
    return result


def json_number(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, dict):
        return {k: json_number(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)):
        return [json_number(v) for v in value]
    return value


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("subject", choices=("physics","chemistry","biology"))
    parser.add_argument("student_pdf", type=Path)
    parser.add_argument("sha256")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    require(digest(args.student_pdf) == args.sha256, "学生卷哈希与录入版不符")
    pages = PdfReader(args.student_pdf).pages
    text = "".join(p.extract_text() for p in pages)
    expect = {"physics":"物理","chemistry":"化学","biology":"生物学"}[args.subject]
    require(expect in text and "参考答案与解析" not in text, "只允许输入本学科终版学生 PDF")
    result = {"physics":physics, "chemistry":chemistry, "biology":biology}[args.subject]()
    atomic_json(args.output,{"subject":args.subject,"paper_sha256":args.sha256,
        "pages":len(pages),"scope":"只独立复算可量化的子结论。定性推理与评分需查重解记录。",
        "input":"从终版学生页转录，不读取候选答案。",
        "checked_items":{str(n):json_number(v) for n,v in sorted(result.items())}})
