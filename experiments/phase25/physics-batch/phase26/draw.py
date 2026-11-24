"""Regenerate both sets of print figures. All coordinates describe the givens in round 3."""
from pathlib import Path
import math
import sys

import matplotlib
matplotlib.use("Agg")
from matplotlib import font_manager, pyplot as plt
from matplotlib.patches import Circle, Rectangle, Arc
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from core.exam_qa import save_figure

for family in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Source Han Sans SC"):
    if family in {face.name for face in font_manager.fontManager.ttflist}:
        break
else:
    raise RuntimeError("需要可排印简体中文的字体")
plt.rcParams.update({"font.family": family, "font.size": 11, "axes.unicode_minus": False,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.linewidth": 1, "lines.solid_capstyle": "round"})
INK = "#182832"
FAINT = "#60717a"
PALE = "#dce5e8"


class Diagram:
    def __init__(self, width=12, height=4.6):
        self.fig = plt.figure(figsize=(5.6, 5.6 * height / width), dpi=320)
        self.ax = self.fig.add_axes((.012, .025, .976, .95))
        self.ax.set(xlim=(0, width), ylim=(0, height), aspect="equal")
        self.ax.axis("off")

    def wire(self, *points, color=INK, lw=1.4, ls="-", z=2):
        x, y = zip(*points)
        self.ax.plot(x, y, color=color, linewidth=lw, linestyle=ls, zorder=z)

    def arrow(self, p, q, *, both=False, color=INK, lw=1.25, size=10):
        self.ax.annotate("", xy=q, xytext=p, zorder=5,
                         arrowprops=dict(arrowstyle="<->" if both else "->", color=color,
                                         lw=lw, shrinkA=0, shrinkB=0, mutation_scale=size))

    def text(self, x, y, label, size=11, ha="center", va="center"):
        self.ax.text(x, y, label, ha=ha, va=va, fontsize=size, color=INK, zorder=6)

    def box(self, x, y, w, h, fill="white", **kw):
        self.ax.add_patch(Rectangle((x,y), w, h, edgecolor=INK, facecolor=fill,
                                    linewidth=1.3, zorder=3, **kw))

    def circle(self, x, y, r, fill="white"):
        self.ax.add_patch(Circle((x,y), r, edgecolor=INK, facecolor=fill, lw=1.2, zorder=3))

    def dot(self, x, y, r=.065):
        self.circle(x, y, r, INK)

    def ticks(self, x0, x1, y, length=.16, step=.33):
        for x in np.arange(x0, x1, step):
            self.wire((x,y), (x-length,y-length), color=FAINT, lw=.8)

    def dimension(self, p, q):
        self.arrow(p, q, both=True, color=FAINT, lw=.9, size=8)

    def field(self, x, y, outward=True):
        self.circle(x, y, .13)
        if outward:
            self.dot(x, y, .034)
        else:
            self.wire((x-.085,y-.085), (x+.085,y+.085), lw=.95, z=4)
            self.wire((x-.085,y+.085), (x+.085,y-.085), lw=.95, z=4)

    def vertical_battery(self, x, low, high):
        mid=(low+high)/2
        self.wire((x,low),(x,mid-.13)); self.wire((x,mid+.13),(x,high))
        self.wire((x-.23,mid-.13),(x+.23,mid-.13),lw=1.7)
        self.wire((x-.40,mid+.13),(x+.40,mid+.13),lw=1.7)


def energy():
    d=Diagram(11.8,3.9)
    for y,label in ((.45,"0"),(1.65,"2.0"),(3.45,"5.0")):
        d.wire((3.3,y),(10.5,y)); d.text(2.65,y,label,ha="right")
    d.text(1.7,2.55,"能量/eV")
    for x,y,z in ((4.6,3.42,.48),(6.8,3.42,1.68),(9,1.62,.48)):
        d.arrow((x,y),(x,z))
    return d.fig


def echo():
    d=Diagram()
    d.wire((1,.35),(9.9,.35),lw=2); d.ticks(1.3,9.9,.35)
    d.wire((1,1.45),(9.85,1.45),ls="--",color=FAINT)
    d.wire((1,2.35),(9.85,2.35))
    d.box(3.42,3.65,1.12,.42,PALE); d.text(2.3,3.88,"探头")
    d.arrow((3.83,3.62),(3.83,.38)); d.arrow((4.17,.38),(4.17,3.62))
    d.text(1.9,2.91,"空气"); d.text(1.9,.95,"液体")
    d.text(9.65,2.73,"升高后液面"); d.text(9.95,1.08,"原液面")
    d.dimension((6.3,1.48),(6.3,2.32)); d.text(7.37,1.91,"6.0 cm")
    d.text(10.62,.35,"槽底")
    return d.fig


def graph(xlabel, ylabel):
    fig, ax=plt.subplots(figsize=(5.15,2.05),dpi=320,layout="constrained")
    ax.set(xlabel=xlabel,ylabel=ylabel)
    ax.tick_params(length=3,labelsize=10)
    return fig,ax


def curve(code):
    if code=="A04":
        f,a=graph("温度 T/K","压强 p/kPa")
        a.plot([300,360,450],[90,108,108],"-o",color=INK);a.set(xticks=[300,360,450],yticks=[90,108],ylim=(82,115))
    elif code=="A06":
        f,a=graph("时间 t/ms","每匝磁通量 Φ/mWb")
        a.plot([0,20,30],[0,.60,0],"-o",color=INK);a.set(xticks=[0,20,30],yticks=[0,.30,.60],yticklabels=["0","0.30","0.60"],ylim=(-.05,.69))
    elif code=="B05":
        f,a=graph("位置 x/a","电势 φ/V")
        a.plot([0,1,2],[1,4,2],"-o",color=INK);a.set(xticks=[0,1,2],yticks=[0,1,2,3,4],ylim=(0,4.5))
    elif code=="B07":
        f,a=graph("时间 t/ms","开路电压 u/V")
        a.axhline(0,lw=.65,color=FAINT)
        a.plot([0,2,2,5,5,7],[3,3,-2,-2,3,3],color=INK,lw=1.7)
        a.set(xticks=[0,2,5,7],yticks=[-2,0,3],ylim=(-2.7,3.8))
    elif code in ("B02","B08"):
        binary=code=="B02"
        f,a=graph("时间 t/T" if binary else "时间 t/s","视向速度 v/(km/s)" if binary else "位移 y/A")
        t=np.linspace(0,1 if binary else .8,600)
        u,v=(24*np.sin(2*np.pi*t),-36*np.sin(2*np.pi*t)) if binary else (np.cos(5*np.pi*t),np.cos(5*np.pi*(t-.1)))
        a.axhline(0,color=FAINT,lw=.6)
        a.plot(t,u,color=INK,lw=1.7,label="Ⅰ星" if binary else "探头 P")
        a.plot(t,v,color=INK,ls="--",lw=1.45,label="Ⅱ星" if binary else "探头 Q")
        a.legend(loc="upper left",bbox_to_anchor=(1,.99),borderaxespad=0,frameon=False,fontsize=10)
        a.set(xticks=[0,.25,.5,.75,1] if binary else [0,.1,.2,.4,.6,.8],yticks=[-36,-24,0,24,36] if binary else [-1,0,1])
    return f


def ion_peaks():
    d=Diagram(12,5)
    x0,y=2.1,1.0
    d.wire((.7,y),(10.9,y)); d.arrow((x0,.15),(x0,.94))
    for r in (2.22,3.33):
        d.ax.add_patch(Arc((x0+r,y),2*r,2*r,theta1=0,theta2=180,color=INK,lw=1.35))
    for x in (.9,10.15):
        for h in (2.2,3.55): d.field(x,h)
    for x,name in ((x0+4.44,"P  4.0 cm"),(x0+6.66,"Q  6.0 cm")):
        d.dot(x,y);d.text(x,y-.38,name)
    d.text(x0-.84,.4,"入口")
    d.text(10.75,4.35,"磁场 B")
    return d.fig


def divider():
    d=Diagram(12,4.5)
    left,mid,right=2.05,6.8,10.1
    low,high=.5,3.55
    d.vertical_battery(left,low,high)
    d.wire((left,high),(3.25,high));d.box(3.25,high-.2,1.6,.4)
    d.text(4.05,high+.55,"R"); d.wire((4.85,high),(right,high),(right,2.45))
    d.wire((right,1.53),(right,low),(left,low))
    d.circle(right,1.99,.46);d.text(right,1.99,"V",12)
    d.wire((mid,high),(mid,2.65));d.box(mid-.21,1.35,.42,1.3)
    d.wire((mid,1.35),(mid,low));d.dot(mid,high);d.dot(mid,low)
    d.arrow((5.92,2.8),(6.5,2.44),size=7);d.arrow((5.88,2.49),(6.46,2.13),size=7)
    d.text(4.74,1.5,"光敏电阻")
    d.text(.86,1.99,"电源")
    return d.fig


def water_jet():
    d=Diagram(12,3.4)
    d.wire((7.7,.55),(7.7,2.62),lw=3)
    d.arrow((1.5,1.95),(7.55,1.95));d.arrow((7.55,1.22),(3.0,1.22))
    d.arrow((7.83,2.18),(10.6,2.18))
    d.text(4.1,2.52,"入射水流  6 m/s"); d.text(4.55,.63,"反向水流")
    d.text(9.52,2.82,"挡板  2 m/s")
    return d.fig


def pendulum():
    d=Diagram(12,4.9)
    x=3.65; top=4.52; cy=1.08; r=.45
    d.wire((2.5,top),(4.8,top),lw=2);d.ticks(2.8,4.75,top+.15)
    d.dot(x,top);d.wire((x,top),(x,cy+r))
    d.circle(x,cy,r,PALE);d.dot(x,cy,.04)
    d.wire((x+.13,top),(5.76,top),color=FAINT,ls=":",lw=.85)
    d.wire((x+.08,cy+r),(5.76,cy+r),color=FAINT,ls=":",lw=.85)
    d.dimension((5.63,cy+r+.04),(5.63,top-.04))
    d.text(6.06,3.04,"L")
    d.box(.65,cy-.22,.72,.44);d.box(7.03,cy-.22,.72,.44)
    d.wire((1.37,cy),(x-r,cy),ls="--",color=FAINT,lw=1)
    d.wire((x+r,cy),(7.03,cy),ls="--",color=FAINT,lw=1)
    d.text(1.02,.42,"发射端"); d.text(7.38,.42,"接收端")
    d.wire((7.75,cy),(8.47,cy));d.box(8.47,cy-.40,2.72,.8)
    d.text(9.83,cy,"标记记录器")
    d.text(1.72,3.8,"悬点");d.wire((2.37,3.91),(3.53,4.43),color=FAINT,lw=.85)
    return d.fig


def discharge():
    d=Diagram(12,4.6)
    x1,x2,x3=2.4,5.94,9.85;lo,hi=.63,3.64
    d.wire((x1,2.32),(x1,hi),(x3,hi),(x3,2.58))
    d.wire((x1,1.96),(x1,lo),(x3,lo),(x3,1.55))
    for y in (1.96,2.32):d.wire((x1-.48,y),(x1+.48,y),lw=1.75)
    d.text(1.14,2.12,"电容 C")
    d.box(x2-.24,1.47,.48,1.33);d.wire((x2,hi),(x2,2.8));d.wire((x2,1.47),(x2,lo))
    d.dot(x2,lo);d.dot(x2,hi);d.text(4.53,2.12,"电阻箱")
    d.box(x3-1.48,1.55,2.96,1.03);d.text(x3,2.07,"电压记录器")
    d.text(5.9,4.18,"放电时的连接")
    return d.fig


def buoy():
    d=Diagram(12,4.8); y=2.2; block=1.37
    for x,begin,end,title in ((3.85,.65,5.8,"释放时"),(8.44,6.25,11.55,"底面到达界面时")):
        d.wire((begin,y),(end,y),color=FAINT)
        d.box(x-.4, y-block if x<4 else y, .8, block,PALE)
        d.text((begin+end)/2,4.39,title)
    d.text(1.48,2.97,"淡水");d.text(1.48,1.46,"盐水")
    d.text(10.77,2.53,"界面")
    return d.fig


def alternator():
    d=Diagram(12,4.85)
    x,y=2.95,2.28
    for h in (1.13,3.36): d.arrow((.75,h),(5.14,h),color=FAINT)
    d.wire((1.53,.75),(4.37,3.81),lw=2.5);d.field(x,y)
    d.text(.97,2.23,"B");d.text(2.86,4.45,"沿转轴观察")
    d.text(3.07,.34,"线圈平面的侧影",10)
    d.wire((6.56,1.99),(6.56,1.03),(10.66,1.03),(10.66,1.7))
    d.wire((6.56,2.87),(6.56,3.65),(7.69,3.65))
    d.circle(6.56,2.43,.44)
    t=np.linspace(-np.pi,np.pi,80)
    d.wire(*zip(6.56+t*.09,2.43+.12*np.sin(t)),lw=1,z=4)
    d.box(7.69,3.45,1.24,.4);d.wire((8.93,3.65),(10.66,3.65),(10.66,2.83))
    d.box(10.43,1.7,.46,1.13)
    d.text(8.31,4.22,"内阻 r");d.text(9.19,2.24,"负载 R")
    d.text(8.72,.34,"等效电路",10)
    return d.fig


def board():
    d=Diagram(12,4.45); y=1.36
    d.wire((.82,y),(.82,3.67),lw=2.3)
    for a in np.arange(y+.16,3.7,.3):d.wire((.82,a),(.59,a-.2),color=FAINT,lw=.8)
    d.wire((.82,y),(11.25,y));d.ticks(1.15,11.25,y)
    d.box(3.22,y,6.63,.4,PALE)
    d.circle(3.22,y+.61,.19);d.dot(3.22,y+.61,.035)
    d.arrow((3.52,2.04),(5.58,2.04));d.text(4.62,2.49,"v")
    d.text(3.2,2.96,"小包 m");d.text(7.49,2.28,"长板 2m")
    d.text(1.38,3.87,"挡墙")
    d.dimension((.84,.63),(3.20,.63));d.text(2.02,.98,"d")
    d.dimension((3.24,.63),(9.83,.63));d.text(6.53,.98,"L")
    for x in (.82,3.22,9.85):d.wire((x,.43),(x,.94),lw=.75,color=FAINT)
    d.text(8.42,3.62,"滑入长板的瞬间")
    return d.fig


def reflection():
    d=Diagram(12,4.65); x,y=5.35,2.25
    d.wire((.8,y),(11.22,y));d.wire((x,.16),(x,4.2),color=FAINT,ls="--",lw=.95)
    d.text(8.70,3.35,"外介质（空气或水）")
    d.text(1.71,1.18,"透明棒")
    # The incident angle is measured from the normal inside the rod.
    delta=1.90; side=delta*math.tan(math.radians(55))
    d.arrow((x-side,y-delta),(x,y))
    d.ax.add_patch(Arc((x,y),2.18,2.18,theta1=215,theta2=270,color=FAINT,lw=1))
    d.text(4.60,.87,"55°");d.text(5.92,3.72,"法线")
    return d.fig


def gas_tubes():
    d=Diagram(12,4.95)
    # Gas lengths use the same scale; the mercury plug thickness is unchanged.
    base=.79; top=4.04; into=2.00; inverted=into*22/18
    for x,opened_up,gas in ((2.40,True,into),(7.50,False,inverted)):
        end=base if opened_up else top; op=top if opened_up else base
        d.wire((x,op),(x,end),(x+1.04,end),(x+1.04,op))
        bottom=end+gas if opened_up else end-gas-.36
        d.box(x+.015,bottom,1.01,.36,"#aebac0")
        gas_end=bottom if opened_up else bottom+.36
        d.dimension((x+1.36,min(end,gas_end)+.04),(x+1.36,max(end,gas_end)-.04))
        d.text(x+2.5,(end+gas_end)/2,"18 cm" if opened_up else "22 cm")
        d.text(x+.52,.29,"管口向上" if opened_up else "管口向下")
        d.text(x-.92,bottom+.18,"水银")
    return d.fig


def strobe():
    d=Diagram(12,4.30)
    for x,theta,label in ((2.0,90,"0"),(6,30,"0.040"),(10,-30,"0.080")):
        y=2.47;r=1.2;ang=math.radians(theta)
        d.circle(x,y,r);d.dot(x,y,.045)
        d.dot(x+r*math.cos(ang),y+r*math.sin(ang),.095)
        d.text(x,.50,label+" s")
    return d.fig


def selector():
    d=Diagram(12,4.52)
    d.text(3.67,4.04,"速度选择区");d.text(9.28,4.04,"磁偏转区")
    top,bottom,mid,gap=3.49,.57,2.03,.19
    for x0,x1 in ((1.3,6.48),(7.05,11.12)):
        d.wire((x0,mid+gap),(x0,top),(x1,top))
        d.wire((x0,mid-gap),(x0,bottom),(x1,bottom))
        if x0>2:d.wire((x1,bottom),(x1,top))
        else:
            d.wire((x1,bottom),(x1,mid-gap));d.wire((x1,mid+gap),(x1,top))
    for x in (2.18,5.33,8.24,10.30):
        for y in (1.17,2.92):d.field(x,y,False)
    d.arrow((.35,mid),(7.78,mid));d.arrow((3.72,3.08),(3.72,2.28))
    d.text(4.17,2.68,"E");d.text(6.75,.20,"狭缝")
    d.wire((6.75,.52),(6.75,mid-.21),color=FAINT,lw=.8,ls=":")
    return d.fig


def frames():
    d=Diagram(12,4.1); start=1.08; scale=.56; cy=2.36
    d.wire((.72,cy-.23),(11.13,cy-.23),color=FAINT,lw=.8)
    d.box(.80,.70,10.39,.48,fill="#f1f4f5")
    for v in range(18):
        x=start+scale*v
        d.wire((x,1.18),(x,1.18-(.29 if v%2==0 else .15)),lw=.75,z=4)
    for v in (0,4,8,12,16):d.text(start+scale*v,.34,str(v),10)
    d.text(11.46,.35,"cm",10)
    for xval,tag in ((0,"0"),(4.8,"4.8"),(9.2,"9.2"),(13.2,"13.2"),(16.8,"16.8")):
        x=start+scale*xval; d.circle(x,cy,.23,PALE);d.dot(x,cy,.04)
        d.wire((x,cy-.25),(x,1.2),color=FAINT,lw=.8,ls=":")
        d.text(x,2.92,tag,10)
    d.text(5.85,3.72,"球心位置/cm    相邻帧间隔 0.050 s")
    return d.fig


def cable_bridge(scale_marked=False):
    d=Diagram(14.5,6.05)
    a,b,tap=3.92,3.92,1.42
    top,lower,mid=3.50,.96,2.18
    # Slide wire from A to B and null detector between the two accessible cable ends.
    d.wire((a,top),(tap,top),(tap,3.13));d.box(tap-.17,1.31,.34,1.82)
    d.wire((tap,1.31),(tap,lower),(b,lower))
    d.wire((a,top),(a,2.65));d.circle(a,2.18,.47);d.text(a,2.18,"G",12)
    d.wire((b,1.71),(b,lower));d.dot(a,top);d.dot(b,lower)
    if scale_marked:
        d.text(2.92,3.89,"A（0 cm）",10);d.text(2.92,.49,"B（100 cm）",10)
        d.arrow((2.03,2.96),(2.03,1.40),size=7,color=FAINT,lw=.85)
        d.text(2.92,2.76,"电阻丝",9);d.text(2.85,1.57,"刻度",9)
    else:
        d.text(3.9,3.89,"A");d.text(3.90,.51,"B")
        d.text(2.57,2.19,"电阻丝",10)
    # Far short, fault, and an electrically continuous shell contacted at the near end.
    near,far,fault=5.85,12.9,9.63
    d.wire((a,top),(far,top),(far,lower),(b,lower))
    d.text(7.33,3.12,"故障线",10);d.text(7.34,1.39,"完好线",10)
    d.text(12.55 if scale_marked else 12.9,2.20,"远端短接",10,ha="right")
    shell_y=4.47
    d.wire((near,shell_y),(far+.13,shell_y),lw=2.3)
    d.text(11.44,4.87,"导电外壳",10)
    d.wire((fault,shell_y),(fault,top),lw=1.15);d.dot(fault,top)
    d.text(10.60,3.91,"碰壳点",10)
    d.dot(near,shell_y);d.wire((near,shell_y),(near,5.32),(3.47,5.32))
    d.wire((3.47,5.02),(3.47,5.62),lw=1.6)
    d.wire((3.16,4.86),(3.16,5.78),lw=1.6)
    d.wire((3.16,5.32),(.49,5.32),(.49,mid),(.78,mid))
    d.arrow((.78,mid),(tap-.18,mid),size=8)
    d.text(1.84,5.74,"电源",10)
    d.text(7.90,5.32,"近端接壳",10)
    d.text(7.5,.42,"每根导线长 100 m",10)
    return d.fig


def brakes():
    d=Diagram(12,4.9)
    d.wire((1.50,.56),(1.50,4.38),lw=2.0);d.wire((3.43,.56),(3.43,4.38),lw=2.0)
    d.box(1.59,2.61,1.75,.85,PALE);d.text(2.47,3.03,"设备",10)
    d.arrow((2.47,2.51),(2.47,1.14));d.text(3.90,1.45,"下行")
    y0,y1,y2=4.32,1.9,.69; x=6.3
    d.wire((x,y0),(x,y2),color=FAINT,lw=.8)
    for h,label in ((y0,"起点　静止"),(y1,"速度 4.0 m/s"),(y2,"终点　静止")):
        d.wire((x-.16,h),(x+.15,h));d.text(x+.31,h,label,10,ha="left")
    d.dimension((10.57,y0-.03),(10.57,y1+.03));d.text(11.27,(y0+y1)/2,"4.0 m",10)
    d.dimension((10.57,y1-.03),(10.57,y2+.03));d.text(11.27,(y1+y2)/2,"2.0 m",10)
    return d.fig


def cycle():
    f,a=graph("体积 $V/V_0$","压强 $p/p_0$")
    path=[(1,1),(1,2),(2,1),(1,1)]
    a.plot(*zip(*path),"-o",color=INK,lw=1.45,ms=4)
    for (x0,y0),(x1,y1) in zip(path,path[1:]):
        p=(x0+.45*(x1-x0),y0+.45*(y1-y0));q=(x0+.61*(x1-x0),y0+.61*(y1-y0))
        a.annotate("",xy=q,xytext=p,arrowprops=dict(arrowstyle="->",color=INK,lw=1.4))
    for x,y,s in ((.90,.92,"A"),(.91,2.09,"B"),(2.07,1.04,"C")): a.text(x,y,s,ha="center",va="center")
    a.set(xlim=(.57,2.43),ylim=(.64,2.40),xticks=[1,2],yticks=[1,2])
    return f


def rails():
    d=Diagram(12,4.85);l,r=2.76,9.84;b,t=.76,3.52;x=7.57
    d.wire((l,1.93),(l,b),(r,b),lw=1.65);d.wire((l,2.31),(l,t),(r,t),lw=1.65)
    for h in (1.93,2.31):d.wire((l-.48,h),(l+.48,h),lw=1.7)
    d.text(1.55,2.09,"电容 C")
    for xp in (4.17,5.79):
        for yp in (1.32,2.93):d.field(xp,yp)
    d.text(4.98,2.12,"B")
    d.box(x-.105,b-.13,.21,t-b+.26,PALE)
    d.text(x,4.06,"金属棒（m，R）")
    d.arrow((x+.14,2.16),(9.37,2.16));d.text(8.60,2.6,"F")
    d.dimension((10.42,b+.03),(10.42,t-.03));d.text(10.85,2.13,"ℓ",13)
    d.text(5.39,.31,"俯视图")
    return d.fig


FIGURES = {"A01":energy,"A03":echo,"A04":curve,"A05":ion_peaks,"A06":curve,
           "A08":divider,"A10":water_jet,"A11":pendulum,"A12":discharge,"A13":buoy,
           "A14":alternator,"A15":board,"B02":curve,"B03":reflection,"B04":gas_tubes,
           "B05":curve,"B06":strobe,"B07":curve,"B08":curve,"B09":selector,"B11":frames,
           "B12":cable_bridge,"B13":brakes,"B14":cycle,"B15":rails}


if __name__=="__main__":
    for code in sys.argv[1:] or FIGURES:
        maker=FIGURES[code]
        fig=maker(code) if maker is curve else maker()
        try:
            save_figure(fig,HERE/code[0]/"figures"/(code+".png"),subject="physics")
            print(code, flush=True)
        finally:
            plt.close(fig)
