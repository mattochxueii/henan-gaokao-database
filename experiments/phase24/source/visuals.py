"""Figures for the revision and the biology benchmark."""
import argparse
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

from matplotlib.patches import Circle, Rectangle, Arc

EXPERIMENTS = Path(__file__).resolve().parents[2]
spec = spec_from_file_location("phase22_figures", EXPERIMENTS / "phase22/source/figures.py")
source = module_from_spec(spec)
spec.loader.exec_module(source)
from figures import INK, LIGHT, MUTED, arrow, box, diagram, label, line, np, plt, table

drawing, chart, distance, finish = source.drawing, source.chart, source.distance, source.finish
ACCENT = source.ACCENT


def physics(available):
    source.physics(available)
    fig, ax = chart(r"$U_{\mathrm{stop}}/\mathrm{V}$", r"$\nu/(10^{14}\,\mathrm{Hz})$", (7.65,2.13))
    ax.plot([6,9],[.5,1.7],"o-",color=INK)
    ax.set(xlim=(4,10),ylim=(0,2),xticks=[4,5,6,7,8,9,10],yticks=[0,.5,1.0,1.7])
    label(ax,6.10,.36,"(6.00, 0.50)",12,ha="left")
    label(ax,8.85,1.73,"(9.00, 1.70)",12,ha="right")
    finish(fig,available,"physics",1)

    fig, ax = drawing((7.2,2.05),(17,5))
    ax.set_aspect("equal")
    center = (6.4,2.44)
    for radius in (.48,1.92):
        ax.add_patch(Circle(center,radius,ec=INK,fill=False,lw=1.15))
    ax.scatter([6.4,6.88,8.32],[2.44]*3,color=INK,s=[23,15,18])
    line(ax,6.4,2.44,9.5,2.44,ls=":",color=MUTED)
    ax.text(6.2,2.1,"O",fontsize=12)
    ax.annotate("近卫星", (6.88,2.44), (5.6,3.92), arrowprops={"arrowstyle":"-","color":MUTED}, fontsize=12)
    ax.annotate("远卫星", (8.32,2.44), (9.10,3.39), arrowprops={"arrowstyle":"-","color":MUTED}, fontsize=12)
    ax.text(9.55,1.85,r"距地心分别为 $R$、$4R$",fontsize=13)
    finish(fig,available,"physics",2)

    fig, ax = drawing((8.6,2.13),(13,4))
    # Primary and secondary are galvanically separate.
    for edge in [(1.15,.78,1.15,1.58),(1.15,2.42,1.15,3.13),(1.15,3.13,2.6,3.13),
                 (4.3,3.13,5.28,3.13),(1.15,.78,5.28,.78),(7.7,3.13,11.7,3.13),
                 (7.7,.78,11.7,.78),(11.7,3.13,11.7,2.51),(11.7,1.39,11.7,.78)]:
        line(ax,*edge)
    ax.add_patch(Circle((1.15,2.0),.43,fc="white",ec=INK))
    label(ax,1.15,2.0,"～",15)
    label(ax,2.24,1.84,"120 V",12)
    ax.add_patch(Rectangle((2.6,2.96),1.7,.34,fc="white",ec=INK))
    label(ax,3.45,3.55,"5.0 Ω",12)
    ax.add_patch(Rectangle((11.51,1.39),.38,1.12,fc="white",ec=INK))
    label(ax,12.24,1.93,"5.0 Ω",12,ha="left")
    for x,n,angle in [(5.28,4,0),(7.70,2,180)]:
        step=2.35/n
        for j in range(n):
            ax.add_patch(Arc((x,.78+(j+.5)*step),.86,step,theta1=angle-90,theta2=angle+90,ec=INK,lw=1.1))
    for x in (6.39,6.63):
        line(ax,x,.66,x,3.29,lw=1.1)
    label(ax,6.49,3.59,"匝数比 2∶1",12)
    finish(fig,available,"physics",4)

    fig, ax = drawing((8.7,2.25))
    line(ax,.45,1.04,11.44,1.04,ls="--",color=MUTED)
    line(ax,.45,1.04,4.25,1.04,lw=1.5)
    x=np.linspace(4.25,11.3,180)
    ax.plot(x,1.04+1.85*np.sin((x-4.25)*np.pi/8.3)**2,color=INK,lw=1.5)
    line(ax,3.14,1.04,4.25,1.04,lw=4,color=MUTED)
    label(ax,3.67,1.55,"粗糙段",12)
    distance(ax,3.14,4.25,.38,"$2R$")
    ax.scatter([8.4],[2.89],color=INK,s=17)
    label(ax,8.36,3.18,"P",12)
    ax.annotate("",(8.4,2.87),(8.4,1.06),arrowprops={"arrowstyle":"<->","color":INK})
    label(ax,8.68,1.96,"$R$",13)
    label(ax,9.5,3.54,"P 点曲率半径为 $R$",12)
    ax.add_patch(Rectangle((1.08,1.04),.57,.45,fc=LIGHT,ec=INK))
    arrow(ax,.56,1.63,2.28,1.63)
    label(ax,1.46,2.26,"进入点",12)
    label(ax,10.33,.68,"水平基线",12)
    finish(fig,available,"physics",7)

    fig, ax = plt.subplots(figsize=(7.6,3.2))
    fig.subplots_adjust(left=.09,right=.955,bottom=.15,top=.86)
    ax.set(xlim=(-.35,4.55),ylim=(-1.08,3.0),xticks=[0,1,4],xticklabels=["O","$L$","$4L$"],yticks=[])
    ax.spines[["right","top","left","bottom"]].set_visible(False)
    ax.axvspan(0,1,color=LIGHT,alpha=.7)
    ax.axvline(1,color=MUTED,lw=1)
    ax.axvline(4,color=MUTED,lw=1,ls="--")
    arrow(ax,-.18,0,4.44,0)
    label(ax,4.46,.18,"$x$",11)
    for px,field in ((.46,r"$\odot$"),(2.5,r"$\otimes$")):
        label(ax,px,2.75,field+" "+r"$B$",13)
    label(ax,.45,2.45,"磁区 I",11)
    label(ax,2.5,2.45,"磁区 II",11)
    radius=1.6
    theta=np.arcsin(1/radius)
    phi=np.linspace(0,theta,45)
    ax.plot(radius*np.sin(phi),radius*(np.cos(phi)-1),color=INK)
    inner_y=radius*(np.cos(theta)-1)
    angle=np.linspace(-np.pi/2-theta,np.pi/2+theta,130)
    ax.plot(2+radius*np.cos(angle),inner_y+radius*np.cos(theta)+radius*np.sin(angle),color=INK)
    ax.scatter([1,1],[inner_y,inner_y+2*radius*np.cos(theta)],color=INK,s=19)
    label(ax,1.17,inner_y-.17,"P",12)
    label(ax,1.13,inner_y+2*radius*np.cos(theta)+.16,"Q",12)
    label(ax,3.95,2.75,"第（3）问的吸收屏",11,ha="right")
    finish(fig,available,"physics",14)


def chemistry(available):
    source.chemistry(available)
    fig, ax = chart("物质的量相对值","处理前",(7.55,2.27))
    ax.bar([0,1,2],[1,1,2],width=.39,ec=INK,fc=[LIGHT,"white",LIGHT])
    ax.set(ylim=(0,2.47),xticks=[0,1,2],xticklabels=[r"$Ca^{2+}$",r"$Mg^{2+}$",r"$HCO_3^-$"],yticks=[0,1,2])
    for x,y in [(0,1),(1,1),(2,2)]:
        label(ax,x,y+.13,str(y),12)
    label(ax,2.53,2.08,r"终态 pH≈12.5",12,ha="left")
    label(ax,2.53,1.43,r"固相 $CaCO_3$、$Mg(OH)_2$",12,ha="left")
    label(ax,2.53,.83,r"滤液中的无机碳以 $CO_3^{2-}$ 为主",12,ha="left")
    ax.set_xlim(-.55,4.1)
    finish(fig,available,"chemistry",6)

    fig, ax = drawing((8.65,3.38),(16,8))
    for x,y,t in [(1.33,6.6,"正极粉"),(4.42,6.6,"氧化浸出"),(7.32,6.6,"除铝、过滤"),
                  (10.46,6.6,"除镁、过滤"),(14.04,6.6,"沉锂"),(14.04,5.04,"母液")]:
        box(ax,x,y,t)
    for a,b in [(2.3,3.25),(5.37,6.27),(8.38,9.37),(11.53,13.01)]:
        arrow(ax,a,6.6,b,6.6)
    arrow(ax,14.04,6.24,14.04,5.47)
    arrow(ax,13.25,5.05,11.65,5.05)
    arrow(ax,11.65,5.05,11.65,6.51)
    label(ax,12.32,4.63,r"回用 $3/4$",12)
    label(ax,10.4,7.53,"pH 10.5",11)
    label(ax,4.43,7.53,r"酸、$H_2O_2$",12)
    rows=[["小试 pH","4.5","5.5","6.0","10.5"],["溶解态铝保留率","44%","2%","1%","78%"],
          ["溶解态镁保留率","100%","100%","100%","0.6%"]]
    bx=ax.inset_axes([.10,.015,.8,.47])
    diagram(bx,12,4)
    table(bx,rows,[.32,.17,.17,.17,.17])
    finish(fig,available,"chemistry",15)


def bands(ax, names, observed, marks):
    diagram(ax,len(names)+1.2,4)
    loc = {length: y for length,y in marks}
    ax.add_patch(Rectangle((.34,.35),len(names)+.38,3.05,ec=MUTED,fc=LIGHT,lw=.9))
    for pos,(name,sizes) in enumerate(zip(names,observed,strict=True),1):
        label(ax,pos,3.72,name,12)
        for size in sizes:
            line(ax,pos-.24,loc[size],pos+.24,loc[size],lw=3.1)
    for size,y in marks:
        label(ax,.14,y,str(size),11,ha="right")


def biology(available):
    out=lambda fig,num: finish(fig,available,"biology",num)
    fig, ax = chart("摄取初速 / 相对单位","外液浓度 / 相对单位",(7.2,2.38))
    ax.plot([1,4,16],[2,5,6],"o-",color=INK,label="甲")
    ax.plot([1,4,16],[1,4,16],"s--",color=ACCENT,label="乙")
    ax.set(xlim=(0,17.4),ylim=(0,17.6),xticks=[0,1,4,16],yticks=[0,2,5,6,10,16])
    ax.legend(loc="upper left",frameon=False,ncols=2)
    out(fig,3)

    fig, ax = chart("细胞比例 / %","单个细胞的 DNA 含量",(7.6,2.45))
    x=np.arange(3)
    for offset, data, c, name in [(-.17,[55,25,20],LIGHT,"对照组"),(.17,[23,12,65],"white","介入组")]:
        ax.bar(x+offset,data,width=.32,fc=c,ec=INK,hatch="///" if offset>0 else "",label=name)
        for n,y in enumerate(data):
            label(ax,n+offset,y+3,str(y),11)
    ax.set(ylim=(0,79),xticks=x,xticklabels=["$2C$","$2C$ 与 $4C$ 之间","$4C$"],yticks=[0,20,40,60])
    ax.legend(loc="upper center",frameon=False,ncols=2)
    out(fig,5)

    fig, ax = chart("膜电位 / mV","刺激后的时间 / 相对单位",(8.0,2.38))
    t=np.linspace(0,6,350)
    peak=lambda x: np.where(t<=1,0,np.exp(-((t-2.6)/x)**2) * np.minimum(1,(t-1)**2))
    ax.axhline(-50,ls=":",color=MUTED,lw=1)
    ax.axhline(-70,ls=":",color=MUTED,lw=1)
    for delta,width,style,color,name in [(15,1.06,"-",INK,"仅甲"),(-8,1.03,"--",MUTED,"仅乙"),(7,.75,"-.",ACCENT,"甲、乙同时")]:
        ax.plot(t,-70+delta*peak(width),style,lw=1.5,color=color,label=name)
    ax.set(xlim=(0,7),ylim=(-81,-47),xticks=[0,1,3,5],yticks=[-78,-70,-63,-55,-50])
    ax.legend(loc="lower left",bbox_to_anchor=(0,1.01),frameon=False,ncols=3,fontsize=10)
    out(fig,8)

    fig, ax = chart("萌发率 / %","处理",(7.25,2.40))
    for offset, data, name in [(-.17,[72,76],"无 ABA"),(.17,[36,70],"有 ABA")]:
        ax.bar(np.array([0,1])+offset,data,width=.32,fc=LIGHT if offset<0 else "white",ec=INK,label=name,
               hatch="" if offset<0 else "///")
        for n,x in enumerate(data):
            label(ax,n+offset,x+4,str(x),11)
    ax.set(xlim=(-.55,1.55),ylim=(0,98),xticks=[0,1],xticklabels=["不加 M","加 M"],yticks=[0,20,40,60,80])
    ax.legend(loc="upper center",frameon=False,ncols=2)
    out(fig,10)

    fig, ax = drawing((8.25,2.17),(16,5))
    for x,y,t in [(1.55,3.29,"昆虫摄入 900"),(6.52,3.29,"同化量 M"),(12.91,3.29,"食虫鸟同化 120"),
                  (3.3,1.11,"粪便排出 300"),(8.7,1.11,"昆虫呼吸 400")]:
        box(ax,x,y,t)
    arrow(ax,2.7,3.29,5.49,3.29)
    arrow(ax,7.47,3.29,11.53,3.29)
    arrow(ax,3.3,3.29,3.3,1.51)
    arrow(ax,8.7,3.29,8.7,1.51)
    label(ax,10.12,4.27,"以上数字为同一统计口径下的能量单位",11)
    out(fig,12)

    fig, ax = plt.subplots(figsize=(7.2,2.30))
    fig.subplots_adjust(left=.16,right=.89,bottom=.10,top=.92)
    bands(ax,["标记 / bp","甲","乙","丙"],[[480,300,180],[480],[300,180],[480,300,180]],
          [(480,2.79),(300,1.97),(180,1.14)])
    out(fig,14)

    fig, (a,b) = plt.subplots(1,2,figsize=(8.3,2.66),gridspec_kw={"width_ratios":[1.46,1]})
    fig.subplots_adjust(left=.13,right=.975,bottom=.22,top=.72,wspace=.42)
    for x,vals,h in [(a,[[12,17],[6,13]],"净光合速率"),(b,[[1.0],[.5]],"相对气孔导度")]:
        width=.31 if len(vals[0])==2 else .50
        for idx, group in enumerate(vals):
            for z,y in enumerate(group):
                off=(z-.5)*.36 if len(group)==2 else 0
                x.bar(idx+off,y,width=width,ec=INK,fc=[LIGHT,"white"][z],hatch=["","///"][z])
                label(x,idx+off,y+(.55 if x is a else .045),str(y),11)
        x.set(xticks=[0,1],xticklabels=["常规组","盐处理组"],ylim=(0,21 if x is a else 1.2))
        x.set_title(("图 1  " if x is a else "图 2  ")+h+(" / μmol·m⁻²·s⁻¹" if x is a else ""),fontsize=11)
        x.spines[["top","right"]].set_visible(False)
    a.legend(handles=[Rectangle((0,0),1,1,fc=LIGHT,ec=INK,label="常规 CO₂"),
                      Rectangle((0,0),1,1,fc="white",ec=INK,hatch="///",label="升高 CO₂")],
             loc="lower left",bbox_to_anchor=(0,1.20),frameon=False,ncols=2,fontsize=9)
    b.text(.47,1.10,"常规 CO₂ 下",fontsize=10,ha="center")
    out(fig,17)

    fig, ax=drawing((8.8,2.61))
    table(ax,[["处理","神经信号","激素 C","淋巴细胞增殖"],
              ["A 无噪声","假处理","1.0","100"],["B 有噪声","假处理","2.0","67"],
              ["C 有噪声","阻断","1.0","98"],["D 有噪声","阻断后补激素","2.0","71"]],
          [.24,.31,.20,.25])
    out(fig,18)

    fig, ax=chart("入侵草平均盖度 / %","样方所在水文带",(7.5,2.52))
    for off,d,form in [(-.17,[50,20],"恢复开始"),(.17,[20,15],"三年后")]:
        ax.bar(np.array([0,1])+off,d,width=.31,ec=INK,fc=LIGHT if off<0 else "white",
               hatch="" if off<0 else "///",label=form)
        for i,y in enumerate(d):
            label(ax,i+off,y+3,str(y),11)
    ax.set(ylim=(0,65),xticks=[0,1],xticklabels=["近水带（占 40%）","远水带（占 60%）"],yticks=[0,20,40,60])
    ax.legend(loc="upper right",frameon=False,ncols=2)
    out(fig,19)

    fig,axes=plt.subplots(1,2,figsize=(9.4,3.12),gridspec_kw={"width_ratios":[1.79,1]})
    fig.subplots_adjust(left=.03,right=.978,bottom=.06,top=.90,wspace=.21)
    a,b=axes
    diagram(a,10.6,6.2)
    a.set_title("图 1  引物取向与载体定位",fontsize=12)
    for y in (5.02,3.94):
        line(a,1.0,y,9.53,y)
        label(a,.50,y,"5′" if y>4 else "3′",11)
        label(a,10.0,y,"3′" if y>4 else "5′",11)
    for x,y,dx,tag in [(2.2,5.02,-1,"Q"),(8.1,5.02,-1,"R"),(2.2,3.94,1,"P"),(8.1,3.94,1,"S")]:
        arrow(a,x,y+.22,x+dx*.98,y+.22)
        label(a,x,y+.51 if y>4 else y-.34,tag,12)
    a.annotate("",(8.1,3.03),(2.2,3.03),arrowprops={"arrowstyle":"<->","color":INK})
    label(a,5.1,2.69,"F   1.2 kb",12)
    line(a,1.1,1.27,4.26,1.27)
    arrow(a,4.26,1.27,9.4,1.27)
    for x,t in [(1.1,"X"),(4.26,"插入起点"),(5.76,"Y")]:
        line(a,x,1.00,x,1.54)
        label(a,x,1.72,t,10)
    label(a,2.65,.83,"0.8 kb",11)
    label(a,5.06,.83,"0.3 kb",11)
    label(a,7.9,.49,"骨架 4.0 kb",10)
    b.set_title("图 2  双酶切泳道",fontsize=12)
    bands(b,["标记 / kb","甲","乙"],[[4.1,3.5,1.7,1.1],[4.1,1.1],[3.5,1.7]],
          [(4.1,2.91),(3.5,2.51),(1.7,1.59),(1.1,1.06)])
    out(fig,21)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("subject", choices=("physics","chemistry","biology"))
    p.add_argument("output", type=Path)
    a=p.parse_args()
    {"physics":physics,"chemistry":chemistry,"biology":biology}[a.subject](a.output)
