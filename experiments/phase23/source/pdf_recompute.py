"""Recompute from the transcribed student PDF only, with no proposer inputs."""
from argparse import ArgumentParser
from fractions import Fraction
from itertools import combinations, permutations, product
from pathlib import Path
import sys

import sympy as sp
from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from gaokao import digest, require
from storage import atomic_json


def selected(judgments):
    return "".join(letter for letter, passes in zip("ABCD", judgments, strict=True) if passes)


def standard():
    x, y, u, v = sp.symbols("x y u v", real=True)
    key = {}
    supporting = {}
    key["1"] = "ABCD"[len((set(range(1, 7)) - {i for i in range(1, 7) if 6 % i == 0}) | {2, 4, 6}) - 2]
    val = sp.simplify(sp.Abs((3 + sp.I)/(1 + 2*sp.I) - sp.I))
    key["2"] = "ABCD"[[1, sp.sqrt(2), 2, sp.sqrt(5)].index(val)]
    a, b = sp.Matrix([1, 2]), sp.Matrix([3, -1])
    t = sp.solve((a + x*b).dot(b), x)[0]
    key["3"] = "ABCD"[[Fraction(-1,10), Fraction(1,10), Fraction(-1,3), 2].index(t)]
    records = [8]*6 + [11]*4
    records[0] -= 3
    records[1] -= 3
    mean = Fraction(sum(records), len(records))
    key["4"] = "ABCD"[[Fraction("8.9"),Fraction("9.2"),Fraction("9.0"),Fraction("8.6")].index(mean)]
    phase = sp.solve(v * sp.pi/12 - sp.pi/6, v)[0]
    height = 2*sp.sin(phase*sp.pi/3 - sp.pi/6)
    key["5"] = "ABCD"[[sp.sqrt(3),2,1,0].index(height)]
    sums = sp.solve([sum(u+i*v for i in range(n)) - total for n, total in ((4,14),(8,44))], (u,v))
    key["6"] = "ABCD"[[8,7,9,Fraction(15,2)].index((u+6*v).subs(sums))]
    allowed = [p for p in permutations((1,2,3,4,5))
               if abs(p.index(1)-p.index(2))==1 and p.index(3)<p.index(1) and p[0] != 4]
    key["7"] = "ABCD"[[9,18,21,24].index(len(allowed))]
    half = sp.Symbol("r", nonnegative=True)
    outer_at_boundary = (half**2 + v*half - 2).subs(half, 1)
    inner_positive = sp.solve(half*(v-half), half)
    assert set(inner_positive) == {sp.Integer(0), v} or set(inner_positive) == {v}
    feasible = sp.solve_univariate_inequality(outer_at_boundary < 0, v, relational=False) & sp.Interval.open(0, sp.oo)
    assert feasible == sp.Interval.open(0,1)
    m_values = [m for m in range(1,5) if feasible.contains(sp.Rational(m,4))]
    key["8"] = "ABCD"[[3,5,6,10].index(sum(m_values))]
    supporting["8"] = {"m": m_values, "boundary": "内外段在r=1相遇，外段严格增加由纸面证明"}
    legal = sp.solve([u**2+v**2-1, (sp.sqrt(5)-u)**2+v**2-4], (u,v))
    realizations = [(r + sp.I*s, sp.sqrt(5) - r - sp.I*s) for r,s in legal]
    claims = (
        lambda z,w: sp.re(z)-1/sp.sqrt(5),
        lambda z,w: sp.Abs(z-w)-sp.sqrt(5),
        lambda z,w: sp.re(z*w),
        lambda z,w: sp.im(z**2+w**2),
    )
    key["9"] = selected(all(sp.simplify(f(z,w)) == 0 for z,w in realizations) for f in claims)
    triples = [tuple(i < 4 for i in row) for row in permutations(range(7),3)]
    X = [row for row in triples if row[0]==row[2]]
    Y = [row for row in triples if row[1]]
    only_two = [row for row in triples if sum(row)==2]
    numerator = sum(row[1] for row in X)
    uncond = Fraction(sum(row[0]==row[2] for row in Y),len(Y))
    other = [row for row in triples if not row[1]]
    conds = [Fraction(sum(sum(row) in (0,3) for row in X),len(X)),
             Fraction(sum(row[0]==row[2] for row in only_two),len(only_two)),
             Fraction(numerator,len(X))]
    key["10"] = selected([conds[0]==Fraction(1,7),conds[1]==Fraction(1,3),
                          conds[2]==Fraction(8,15),
                          uncond>Fraction(sum(row[0]==row[2] for row in other),len(other))])
    supporting["10"] = {"labelled_draws":len(triples), "fractions":list(map(str,conds))}
    radii = sp.Interval.open(-4,4)
    pq = (36-v**2)/4
    cos_range = sp.calculus.util.function_range(10/pq-1, v, radii)
    height2 = (sp.Rational(6,2))**2 - (sp.Rational(4,2))**2
    ray = sp.solve((6-x)**2 - (x**2+16-2*x*4*sp.cos(sp.pi/3)),x)[0]
    key["11"] = selected([pq.subs(v,0)==9, height2==9,
                          cos_range==sp.Interval.Lopen(sp.Rational(1,9),1),ray==sp.Rational(5,2)])
    supporting["11"] = {"cosine_range":str(cos_range), "ray_length":str(ray)}
    f = x**3-3*x
    intercepts = [f.subs(x,p) - 9*p for p in sp.solve(sp.diff(f,x)-9,x)]
    key["12"] = str(abs(intercepts[1]-intercepts[0]))
    key["13"] = str(sp.Poly((1+2*x)**5*(1-x)**2, x).coeff_monomial(x**2))
    condition = sp.expand((x**2-(6-v)*x+((6-v)**2-(14-v**2))/2).subs(x,v))
    interval = sp.solve_univariate_inequality(condition<=0,v,relational=False)
    supporting["14"] = {"middle_condition":str(condition), "range":str(interval)}
    p = sp.Symbol("p",positive=True)
    supporting["15"] = {"endpoints": [str(sp.limit(36-144/p,p,6,dir="+")),str((36-144/p).subs(p,9))]}
    p_vec = sp.Matrix([4-v,v,4])
    normal = sp.Matrix([1,1,1])
    foot = p_vec - (p_vec.dot(normal)-4)*normal/normal.dot(normal)
    foot_interval = sp.reduce_inequalities([coord>=0 for coord in foot],v).as_set()
    plane_angle = p_vec.dot(normal)**2/(3*p_vec.dot(p_vec))
    rho = sp.calculus.util.function_range(plane_angle, v, foot_interval)
    supporting["16"] = {"projection_parameter":str(foot_interval), "angle_sine_squared":str(rho)}
    p=sp.Rational(2,3)
    q=1-p
    times = {}
    for cap in range(2,10):
        expectation=0
        for bits in product((0,1),repeat=cap):
            k = next((i+1 for i in range(1,cap) if bits[i]!=bits[i-1]), cap)
            w = p**sum(bits)*q**(cap-sum(bits))
            expectation += k*w
        closed = sp.Rational(7,2)-2*p**(cap-1)-q**(cap-1)/2
        assert expectation == closed
        times[str(cap)] = str(expectation)
    hazard = lambda n: (p**n*q+q**n*p)/(p**n+q**n)
    from_third = sum(p**sum(bits)*q**(3-sum(bits)) for bits in product((0,1),repeat=3)
                     if bits[0]==bits[1]!=bits[2])
    supporting["17"] = {"third":str(from_third), "finite_expectations":times,
                        "first_integer":next(n for n in range(1,10) if hazard(n)<=sp.Rational(7,20))}
    co = sp.expand(((x+v/2)**2+4)*((x-v/2)**2+4))
    pvar = sp.Symbol("z",nonnegative=True)
    as_polynomial = pvar**2+(8-v**2/2)*pvar+(v**2/4+4)**2
    assert sp.expand(as_polynomial.subs(pvar, x**2) - co) == 0
    vertex = sp.solve(sp.diff(as_polynomial,pvar),pvar)[0]
    supporting["18"] = {"vertex":str(vertex), "at_4":str(co.subs({v:4,x:0})),
                        "high_min_squared":str(sp.factor(as_polynomial.subs(pvar,vertex)))}
    cubic=x**3-3*x/4
    crit=[-1,*sp.solve(sp.diff(cubic,x),x),1]
    coeff = sp.Symbol("a",positive=True)
    bound_eq = (2*(coeff/3)**sp.Rational(3,2))**2 - sp.Rational(1,4)
    supporting["19"] = {"crit_and_endpoints":[str(cubic.subs(x,r)) for r in crit],
                        "max_a":str(sp.solve(bound_eq,coeff)[0])}
    assert key == dict(zip(map(str,range(1,14)),
                           ["C","D","A","D","B","A","B","C","AB","BC","AD","32","21"],strict=True))
    assert interval == sp.Interval(2-1/sp.sqrt(3),2+1/sp.sqrt(3))
    assert len(allowed)==18 and supporting["15"]["endpoints"]==["12","20"]
    assert foot_interval==sp.Interval(sp.Rational(4,3),sp.Rational(8,3))
    assert rho == sp.Interval(sp.Rational(6,7),sp.Rational(8,9))
    assert from_third==sp.Rational(2,9) and supporting["17"]["first_integer"]==5
    assert supporting["18"]["high_min_squared"]=="4*v**2"
    assert max(map(sp.Abs,[cubic.subs(x,r) for r in crit]))==sp.Rational(1,4)
    assert sp.simplify(sp.solve(bound_eq,coeff)[0]-3/4**sp.Rational(2,3))==0
    return key, supporting


def trend():
    masks = [(1<<i)|(1<<((i+1)%6)) for i in range(6)]
    reached = [{0}]
    for _ in range(6):
        reached.append({state ^ mask for state in reached[-1] for mask in masks})
    two_four = {sum(1<<i for i in c) for c in combinations(range(6),4)}
    result = selected([set.union(*reached) == {i for i in range(64) if i.bit_count()%2==0},
                       next(n for n,states in enumerate(reached) if 0b001001 in states)==3,
                       two_four <= reached[2], 63 in reached[4]])
    x=sp.Symbol("x",positive=True)
    products=sp.solve((1+x)**2-4*(16-4*x),x)
    ans=4/(1-products[0])
    assert result=="AB" and ans==-2
    u,v=sp.symbols("u v",positive=True)
    a,b=2*u*v/(u+v),2/(u+v)
    shared=(2*u*b+a*2/v)/2
    union=sp.factor(4-shared)
    assert union==4*v/(u+v) and sp.factor(1-a*b)==(u-v)**2/(u+v)**2
    circular=sp.Matrix([[sp.Rational(1,2) if j in (i,(i+1)%4) else 0 for j in range(4)] for i in range(4)])
    z=sp.Matrix([u,v,-u,-v])
    assert circular**2*z == sp.Matrix([v/2,-u/2,-v/2,u/2])
    assert circular*sp.Matrix([1,-1,1,-1]) == sp.zeros(4,1)
    checks = {"1":{"reachable":[len(i) for i in reached],"four_lamp_sets_at_two":len(two_four & reached[2])},
              "2":{"admissible_products":list(map(str,products))},
              "3":{"overlap_area":str(sp.factor(shared)), "union_area":str(union)},
              "4":{"two_round_deviations":list(map(str,circular**2*z)), "alternating_offset_erased":True}}
    return {"1":result,"2":str(ans)}, checks


if __name__ == "__main__":
    parser=ArgumentParser(description=__doc__)
    parser.add_argument("edition", choices=("standard","trend"))
    parser.add_argument("student_pdf", type=Path)
    parser.add_argument("sha256")
    parser.add_argument("output", type=Path)
    args=parser.parse_args()
    require(digest(args.student_pdf)==args.sha256,"只验算录入时绑定的学生卷版本")
    reader=PdfReader(str(args.student_pdf))
    text="".join(page.extract_text() for page in reader.pages)
    expect="河南新高考数学标准模拟卷" if args.edition=="standard" else "数学趋势研判专题"
    require(expect in text.replace(" ","") and "参考答案与解析" not in text,"须输入学生卷")
    keys, partial = (standard if args.edition=="standard" else trend)()
    atomic_json(args.output, {"edition":args.edition,"pdf_sha256":args.sha256,"pages":len(reader.pages),
                             "scope":"图文由终版PDF独立抄读。采用枚举、线性代数及符号表达式比对。全域论证与可达性见另行重解。",
                             "keys":keys,"checks":partial})
