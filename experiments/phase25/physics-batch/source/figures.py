"""Draw the information-bearing student figures; pixel checks use the export renderer."""
from pathlib import Path
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Arc, Rectangle
from core.exam_qa import save_figure

def draw(code, dest):
    f,a=plt.subplots(figsize=(4.9,1.9),dpi=195,layout="constrained")
    a.spines[["right","top"]].set_visible(False)
    def diagram(x=10,y=5):
        a.set(xlim=(0,x),ylim=(0,y),aspect="equal")
        a.axis("off")
    def label(x,y,s,**kw):
        a.text(x,y,s,ha="center",va="center",fontsize=9,**kw)
    def line(x,y,**kw):
        a.plot(x,y,color="#203447",lw=1.55,**kw)
    def arrow(p,q):
        a.annotate("",xy=q,xytext=p,arrowprops=dict(arrowstyle="->",color="#244754",lw=1.5))
    if code=="A01":
        diagram(9,6)
        for y,v in [(0.7,0),(2.5,2),(5.2,5)]:
            line([2,7],[y,y]);label(1,y,f"{v:.1f} eV")
        arrow((3,5.1),(3,0.77));arrow((5,5.1),(5,2.6));arrow((6,2.4),(6,.78))
    elif code=="A03":
        diagram()
        line([1,9],[.6,.6]);line([1,9],[2.1,2.1],ls="--");line([1,9],[3.1,3.1])
        arrow((4.8,4.65),(4.8,.7));arrow((5.4,.7),(5.4,4.65));label(7.5,2.6,"6.0 cm")
        label(2,4.1,"air");label(2,1.3,"liquid")
    elif code=="A04r":
        line([300,360,450],[90,108,108],marker="o");a.set(xlabel="T / K",ylabel="p / kPa",xticks=[300,360,450],yticks=[90,108],ylim=(84,116))
    elif code in ("A04","A06","B05","B07","B02","B08"):
        if code=="A04":
            line([1,2,2],[2,1,2],marker="o");a.set(xlim=(.65,2.4),ylim=(.7,2.42),xticks=[1,2],yticks=[1,2],xlabel=r"$V/V_0$",ylabel=r"$p/p_0$")
            for x,y,s in [(1,2.19,"A"),(2.14,.98,"B"),(2.14,2.02,"C")]:label(x,y,s)
        if code=="A06":
            line([0,20,30],[0,.60,0],marker="o");a.set(xlabel="t / ms",ylabel="Flux / mWb",xticks=[0,20,30],yticks=[0,.3,.6],ylim=(-.03,.73))
        if code=="B05":
            line([0,1,2],[1,4,2],marker="o");a.set(xlabel="x / a",ylabel="Potential / V",xticks=[0,1,2],yticks=[1,2,3,4])
        if code=="B07":
            line([0,2,2,5,5,7],[3,3,-2,-2,3,3]);a.axhline(0,color=".7",lw=.7);a.set(xlabel="t / ms",ylabel="u / V",xticks=[0,2,5,7],yticks=[-2,0,3],ylim=(-3.2,4.3))
        if code in ("B02","B08"):
            t=np.linspace(0,1,300) if code=="B02" else np.linspace(0,.8,300)
            y=24*np.sin(2*np.pi*t) if code=="B02" else np.cos(5*np.pi*t)
            z=-36*np.sin(2*np.pi*t) if code=="B02" else np.cos(5*np.pi*(t-.1))
            line(t,y);line(t,z,ls="--");a.legend(["I","II"] if code=="B02" else ["P","Q"],loc="upper left",bbox_to_anchor=(1.01,1),frameon=True)
            a.set(xlabel="t / T" if code=="B02" else "t / s",ylabel="v / (km/s)" if code=="B02" else "y / A")
            if code=="B02":a.set(yticks=[-36,-24,0,24,36],xticks=[0,.25,.5,.75,1])
            else:a.set(xticks=[0,.1,.2,.4,.6,.8],yticks=[-1,0,1])
    elif code=="A05":
        diagram(10,5);line([.6,9.5],[.9,.9])
        for x,r in [(1.7,2),(1.7,3)]:
            a.add_patch(Arc((x+r,.9),2*r,2*r,theta1=0,theta2=180,lw=1.5))
        arrow((1.7,.12),(1.7,.85));label(5.7,.45,"P  4 cm");label(8,.45,"Q  6 cm");label(1.1,3.6,"B")
    elif code=="A08":
        diagram(12,5)
        line([1,1,3],[.6,4,4]);line([5,9.4,9.4],[4,4,3.35]);line([9.4,9.4,1],[2.45,.6,.6]);line([6.7,6.7],[4,3.3]);line([6.7,6.7],[1.5,.6])
        a.add_patch(Rectangle((3,3.7),2,.6,fill=False));label(4,4.65,"R")
        a.add_patch(Rectangle((6.35,1.5),.7,1.8,fill=False));label(5.25,2.4,"LDR");a.add_patch(plt.Circle((9.4,2.9),.45,fill=False));label(9.4,2.9,"V")
        a.add_patch(Rectangle((.7,1.8),.6,.9,fc="white",ec="none",zorder=3));line([.4,1.6],[2.48,2.48],zorder=4);line([.7,1.3],[2.0,2.0],zorder=4)
    elif code=="A10":
        diagram();arrow((.8,2.7),(6.6,2.7));arrow((6.6,2.05),(3.2,2.05));line([7,7],[1.2,3.55]);arrow((7.1,3.8),(9.5,3.8));label(3,3.35,"6 m/s");label(8.3,4.45,"2 m/s")
    elif code=="B03":
        diagram();line([.6,9.4],[2.4,2.4]);line([5,5],[.4,4.6],ls="--");arrow((1.8,.35),(5,2.4));arrow((5,2.4),(8.2,.35));label(4,.8,"55°");label(2,3.5,"air / water")
    elif code=="B04":
        diagram(11,6)
        for x,y,inv in [(2,3.25,False),(7.3,2.5,True)]:
            line([x,x],[.5,5.5]);line([x+1,x+1],[.5,5.5]);line([x,x+1],[5.5 if inv else .5]*2)
            a.add_patch(Rectangle((x,y),1,.45,fc=".4"));label(x+2.25,y+(-1.25 if not inv else 1.35),"22 cm" if inv else "18 cm")
    elif code=="B06":
        diagram(13,4)
        for i,theta in enumerate([90,30,-30]):
            x=2+4.4*i;a.add_patch(plt.Circle((x,2.4),1.2,fill=False));r=np.deg2rad(theta)
            a.plot(x+1.2*np.cos(r),2.4+1.2*np.sin(r),"ko");label(x,.48,f"{40*i} ms")
    elif code in ("B09","B09r"):
        diagram(13,5)
        for i in range(2):
            x=1+6*i
            if code=="B09r":
                line([x,x],[.6,1.85]);line([x,x],[2.45,4]);line([x,x+4.1],[.6,.6]);line([x,x+4.1],[4,4])
                line([x+4.1,x+4.1],[.6,1.85]);line([x+4.1,x+4.1],[2.45,4])
                if i==0:label(5.8,2.75,"slit")
            else:a.add_patch(Rectangle((x,.6),4.1,3.4,fill=False))
            for sx in [x+.55,x+3.55]:
                for y in [1.1,3.45]:label(sx,y,"×")
        arrow((.25,2.15),(7.9,2.15));arrow((3,3.5),(3,2.55));label(3.7,3.05,"E");label(9,4.55,"B")
    else:
        raise ValueError(code)
    save_figure(f,dest/(code+".png"))
    plt.close(f)

if __name__=="__main__":
    dest=Path(sys.argv[1])
    for code in "A01 A03 A04 A05 A06 A08 A10 B02 B03 B04 B05 B06 B07 B08 B09 A04r B09r".split():
        draw(code,dest)
