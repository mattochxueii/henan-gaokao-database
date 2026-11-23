"""Independent calculations from numbers and diagram readings transcribed from the student PDF."""
import argparse
from fractions import Fraction as F
from itertools import permutations, product
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from gaokao import digest


def physics():
    results = {}
    # Uniform light travel, adjacent fringe separation and two velocity traces.
    results[1] = int(F(3*10**8 * (120-100),10**9) / 2 / F(1,5))
    results[2] = F(600 * 2, 3)
    mass, t = 40, 2
    on, off = [6,2], [6,4]
    drag = F(mass*(off[0]-off[1]),t)
    brake = F(mass*(on[0]-on[1]),t)-drag
    distance = F(sum(on),2)*t
    results[3] = [drag, brake, distance, F(192,brake*distance)]
    # Orthogonal normals, so the side incidence uses cos r.
    r_sine = F(4,3)*F(3,4) / F(5,3)
    results[4] = [r_sine**2, F(5,3)**2*(1-r_sine**2)]
    # Independently differentiate overlap with each diagram band.
    def flux(right):
        intervals = [(0,1,1),(1,2,-1)]
        return sum(sign*max(0,min(right,r)-max(right-1,l)) for l,r,sign in intervals)

    dt = F(1,16)
    results[5] = [-(flux(t+dt)-flux(t-dt))/(2*dt) for t in (F(1,2),F(3,2),F(5,2),F(7,2))]
    # Total light and delayed light; reconstruct the two initial signals.
    a = (40-F(1,4)*100)/(F(1,2)-F(1,4))
    results[6] = [a,100-a,F(a,100-a)]
    results[7] = 1 + F(1,4)*2 + (1-F(1,2))/2
    results[8] = [2*F(40,100),F(1,2*F(10,1000)),2*F(40,100)*F(1,2*F(10,1000))]
    moved = (2-1-F(1,2))/(2+F(1,2))
    results[9] = [F(3,2),moved,2*(1-moved),moved/2]
    init_cap, final_cap = 1+F(1,2),F(1,2)+F(1,2)
    final_u = init_cap/final_cap
    results[10] = [final_u,(final_u-1)/2, final_u/2,(final_cap*final_u**2-init_cap)/2]
    slope = F(1,2*F(1,1000))
    intercept = F(1,2)-slope*F(2,1000)
    results[11] = [slope,intercept,slope*F(1,5),-intercept*F(1,5)/(2*F(2,5))]
    conductance = F(1,100)/(-F(8-10,100)*F(1,1000)*10**6)
    results[12] = [F(1000,10),conductance,F(10,8)-1]
    # Numerical border challenges with U/(EL²/h); at equality a hit is required.
    results[13] = [{"normalized_U":u,"y_at_exit_over_h":F(1,4)/u,
                    "screen_offset_over_h":F(3,4)/u,"passes":F(1,4)/u < F(1,2)}
                   for u in (F(2,5),F(1,2),F(3,5))]
    pressure = [F(3,2),F(3,2),F(5,2)]
    work = sum((p+q)/2 for p,q in zip(pressure,pressure[1:]))
    internal = F(3,2)*(pressure[-1]*3-pressure[0])
    results[14] = [3*pressure[-1]/pressure[0],work,internal,internal+work]
    # Motion in the cart frame: successive squared-speed losses equal 2a_rel*d.
    relative_accel_per_f_over_m = 1+F(1,3)
    first_cross = 2*relative_accel_per_f_over_m
    second_cross = 2*first_cross
    reverse = F(9,8)*second_cross
    results[15] = {"v2_thresholds_in_fd_over_m":[first_cross,second_cross,reverse],
                   "departure_checked": [
                       [v2,v2 > second_cross, 9*(v2-second_cross) > v2]
                       for v2 in (F(16,3),F(17,3),F(6),F(25,4))]}
    assert results[3][-1] == F(3,5) and results[4][-1] == F(16,9)
    assert results[5] == [-1,2,-1,0] and results[7] == F(7,4)
    assert results[11][-2:] == [100,F(1,8)] and results[12] == [100,F(1,2000),F(1,4)]
    assert results[15]["v2_thresholds_in_fd_over_m"] == [F(8,3),F(16,3),6]
    return results


def chemistry():
    results = {}
    # Electron number and effective nuclear charge order.
    results[5] = [(8+2,8),(9+1,9),(11-1,11),(12-2,12)]
    # Ca, Mg, C, H, O, charge vectors from the printed equation.
    ions = ((1,0,0,0,0,2),(0,1,0,0,0,2),(0,0,1,1,3,-1),(0,0,0,1,1,-1))
    solids = ((1,0,1,0,3,0),(0,1,0,2,2,0),(0,0,0,2,1,0))

    def tally(vectors, coefficients):
        return [sum(v*n for v,n in zip(col,coefficients,strict=True)) for col in zip(*vectors)]

    results[6] = [tally(ions,(1,1,1,3)),tally(solids,(1,1,1))]
    a, b = [0,24,-24,18,-18], [0,33,-12,25,-18]
    results[8] = [max(a[1]-a[0],a[3]-a[2]),b[3]-b[2],a[3]-a[4],(b[4]-b[0])-(a[4]-a[0])]
    charge = 2
    results[9] = {"Na":charge, "SO4":F(charge,2), "O2":F(charge,4),"H2":F(charge,2),
                  "anode_water_per_electron":F(1,2),"cathode_water_per_electron":1}
    h,k1,k2 = F(1,10**6), F(1,10**4), F(1,10**8)
    results[10] = h*h/(h*h+h*k1+k1*k2)
    step = F(1,4)
    li = list(product((step,3*step),repeat=3))
    o_count = 8*F(1,8)+6*F(1,2)
    neighbors = [c for c in product((step,-step),repeat=3) if sum(x*x for x in c) == 3*step**2]
    results[11] = [len(li),o_count,len(neighbors),3*step**2,len(li)*7+o_count*16]
    masses = [40+2*12+4*16+18,40+2*12+4*16,40+12+3*16,40+16]
    results[12] = {"platform_masses":masses,"steps":[m-n for m,n in zip(masses,masses[1:])]}
    initial, chlorine = F(1,100), F(1,100)
    results[14] = [F(1,10**10)/chlorine,F(1,10**5)/chlorine**2,
                   initial*chlorine>F(1,10**10),initial*chlorine**2<F(1,10**5)]
    # Li, Fe, P, H, O, charge vectors for the leach.
    pre = ((1,1,1,0,4,0),(0,0,0,2,2,0),(0,0,0,1,0,1))
    post = ((0,1,1,0,4,0),(1,0,0,0,0,1),(0,0,0,2,1,0))
    results[15] = {"stoichiometric_balance":[tally(pre,(2,1,2)),tally(post,(2,2,2))],
                   "pH_floor":14+F(-33+6,3), "pH_ceiling":14+F(-11+2,2),
                   "product_g":(F(900,1000)-F(120,1000)*F(1,4))*74/2}
    nominal, blank, treated = F(26,100),F(14,100),F(20,100)
    results[16] = [(nominal-blank)/10,F(2,10)-blank,(nominal-treated)/10/10]

    def equilibrium(x,z):
        n = (1-x,x-z,z,4-x-3*z,x+z)
        assert sum(n[:3]) == 1 and 2*n[3]+2*n[4]+4*n[2] == 8
        assert 2*n[0]+n[1]+n[4] == 2
        a,b,c,h,w = (F(4)*v/sum(n) for v in n)
        return [n,b*w/(a*h),c*w/(b*h**3)]

    results[17] = [equilibrium(F(3,4),F(1,2)),equilibrium(F(4,5),F(2,5))]
    # Hold the first substituent fixed; enumerate inequivalent placements of two others.
    placements = list(permutations(range(1,6),2))
    classes = {min((a,b),((-a)%6,(-b)%6)) for a,b in placements}
    results[18] = {"orbits_per_group_set":len(classes),"two_group_sets":2*len(classes),
                   "C_H_O": [sum(parts) for parts in zip((6,3,0),(0,1,1),(1,3,1),(3,5,2))]}
    assert results[6][0] == results[6][1]
    assert results[8] == [42,37,36,0] and results[10] == F(1,102)
    assert results[14][-2:] == [True,True]
    assert results[15]["stoichiometric_balance"][0] == results[15]["stoichiometric_balance"][1]
    assert results[15]["product_g"] == F(3219,100)
    assert results[16] == [F(12,1000),F(6,100),F(6,10000)]
    assert results[17][0][1:] == [F(5,7),F(160,343)]
    assert results[17][1][1] == F(6,5) and results[18]["two_group_sets"] == 20
    return results


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("subject",choices=("physics","chemistry"))
    p.add_argument("pdf",type=Path)
    p.add_argument("output",type=Path)
    a=p.parse_args()
    result=(physics if a.subject=="physics" else chemistry)()
    a.output.write_text(json.dumps({
        "subject":a.subject,"paper_sha256":digest(a.pdf),
        "method":"从学生版读输入，使用独立有理数验算、分段函数和枚举。未读取候选答案。",
        "scope":"只记录可计算子结论；完整推理及选项审查见独立重解。",
        "checked_items":result,
    },default=str,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
