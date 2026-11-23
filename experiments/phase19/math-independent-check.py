"""Independent computations from the final printed HN19-M150-v1 problem statements.

This script only reads the student PDF. Essential quantities visible as formula
images are transcribed below. No candidate specification or answer is loaded.
"""
from fractions import Fraction
from itertools import combinations, product
from pathlib import Path
import hashlib
import json
import sys

import sympy as s
from pypdf import PdfReader


def solve(pdf):
    rendered = " ".join(page.extract_text() for page in PdfReader(pdf).pages)
    assert "河南新高考数学模拟卷" in rendered
    assert all(f"{i}." in rendered for i in range(1, 20))
    x, t, k = s.symbols("x t k", real=True)
    n=s.symbols("n", integer=True,positive=True)
    keys={}
    keys[1]="ABCD"[[1,2,3,4].index(len({v for v in (0,2,3,4) if not -1<=v<3}))]
    z=(2+s.I)/(1-s.I)
    keys[2]="ABCD"[[3,2,s.Rational(1,2),1].index(s.simplify(z+s.conjugate(z)))]
    a=s.sqrt(2**2+4**2-2*2*4*s.cos(s.pi/3))
    keys[3]="ABCD"[[2,2*s.sqrt(2),2*s.sqrt(3),4].index(a)]
    new=[13,19,19,25]
    mean=s.Rational(sum(new),len(new))
    keys[4]="ABCD"[[2,6,7,18].index(sum((v-mean)**2 for v in new)/4)]
    dot=(4+4-4)//4
    keys[5]="ABCD"[[1,0,-1,2].index(dot)]
    keys[6]="ABCD"[[3,4,5,s.Rational(12,5)].index(s.Line(s.Point(0,0),s.Point(3,4)).distance(s.Point(5,0)))]
    assert s.solve(3*t**2-10*t+3,t)==[s.Rational(1,3),3]
    keys[7]="C"
    high=s.solve((3-x)**2-4*(x*x-3*x+2),x)[-1]
    assert (3-high)/2>0
    assert s.simplify(((3-high)/2)**2+(3-high)*high)==2
    keys[8]="ABCD"[[2,s.sqrt(5),1+s.sqrt(2),1+2*s.sqrt(3)/3].index(high)]
    sequence=[2]
    for _ in range(1,9):
        sequence.append(2*sequence[-1]-1)
    assert sequence[:3]==[2,3,5] and set((a-1)//(b-1) for a,b in zip(sequence[1:],sequence))=={2}
    keys[9]="AB"
    pairs=list(combinations(range(1,5),2))
    a={pair for pair in pairs if sum(pair)%2==0}
    b={pair for pair in pairs if pair[0]*pair[1]%2==0}
    assert Fraction(len(a),6)==Fraction(1,3) and Fraction(len(b),6)==Fraction(5,6)
    assert Fraction(len(a&b),len(b))==Fraction(1,5) and Fraction(len(a&b),6)!=Fraction(len(a)*len(b),36)
    keys[10]="ABD"
    shifted=x*x-4*x+3
    assert s.diff(shifted,x).subs(x,s.Rational(1,2))<0
    assert s.Poly((shifted-t)*(shifted+t),x).shift(2).TC()==1-t*t
    assert [len(s.solve(shifted**2-u**2,x)) for u in (0,s.Rational(1,2),1,2)]==[2,4,3,2]
    keys[11]="ABD"
    f=x**3-3*x+2
    keys[12]=str(f.subs(x,2)-2*s.diff(f,x).subs(x,2))
    plane=s.Plane(s.Point3D(3,0,0),s.Point3D(0,4,0),s.Point3D(0,0,6))
    keys[13]=str(plane.distance(s.Point3D(0,0,0)))
    trials=[seq for seq in product((0,1),repeat=8) if sum(seq)==4]
    assert len(trials)==70
    keys[14]=str(Fraction(sum(sum(a==b for a,b in zip(seq,seq[1:]))==3 for seq in trials),len(trials)))
    formula=2/(2*n-1)
    assert s.simplify(formula.subs(n,n+1)-formula/(1+formula))==0
    assert next(j for j in range(1,40) if 2-s.Rational(2,2*j+1)>s.Rational(19,10))==10
    keys[15]={"general_term":str(formula),"min_n":10}
    balls=list(combinations(range(1,6),2))
    future=[r for r in balls if r[1]>=4]
    keys[16]={"mean":str(Fraction(sum(b for a,b in balls),len(balls))),
              "one_white":str(Fraction(sum(a<=3 for a,b in future),len(future))),
              "remaining":str(Fraction(sum(b-3 for a,b in future),len(future)))}
    target=s.Matrix((3,4,6))
    assert s.solve(target.dot(s.Matrix((-2,0,t))),t)==[1]
    normal=s.Matrix((-2,3,0)).cross(s.Matrix((-2,0,1)))
    keys[17]={"AE":1,"cosine":str(s.simplify(s.Abs(normal.dot(target))/(normal.norm()*target.norm())))}
    # Treat the chord as x = 4+ky. Use area = base * perpendicular height / 2.
    ys=s.solve(t*t-4*k*t-16,t)
    center=s.Point(-4,2*k)
    pts=[s.Point(4+k*y,y) for y in ys]
    delta=[p-center for p in pts]
    dot=s.simplify(sum(a*b for a,b in zip(*delta)))
    assert s.simplify(dot-12*(4+k*k))==0
    area=4*(4+k*k)**s.Rational(3,2)
    tangent=s.simplify(2*area/dot)
    assert s.simplify(tangent**2-4*(k*k+4)/9)==0
    keys[18]={"x_T":-4,"area_min":str(area.subs(k,0)),"area_max":str(area.subs(k,s.sqrt(11)/2))}
    # Re-derive direct rational factors with x=t^3. Positive factors show strictness.
    f=x-1-s.log(x)
    upper=(x+1)*s.log(x)-2*(x-1)
    assert s.simplify(s.diff(upper,x,2)-(x-1)/x**2)==0
    t=s.symbols("t",positive=True)
    lower=t-1/t+(t*t-1)/(t*t+1)-3*s.log(t)
    factor=(t-1)**4*(t**2+t+1)/(t**2*(t*t+1)**2)
    assert s.factor(s.diff(lower,t)-factor)==0
    keys[19]={"best_upper_exponent":1,"lower_comparison_derivative":str(factor),
              "scope":"symbolic derivatives and algebra; inequalities, existence and sharpness also require the reasoning record"}
    return {"pdf_sha256":hashlib.sha256(pdf.read_bytes()).hexdigest(),
            "input":"student_pdf_with_manual_formula_transcription","answers":keys}


if __name__=="__main__":
    print(json.dumps(solve(Path(sys.argv[1])),ensure_ascii=False,indent=2))
