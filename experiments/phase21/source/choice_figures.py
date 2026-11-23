"""Draw the information-bearing choice figures for the compact Phase 21 papers."""

import argparse
from itertools import product
from pathlib import Path

from figures import INK, LIGHT, MUTED, arrow, box, diagram, label, line, np, plt
from matplotlib.patches import Arc, Circle, Polygon, Rectangle


def sketch():
    fig, ax = plt.subplots(figsize=(8.4, 2.32))
    fig.subplots_adjust(left=.015, right=.985, bottom=.03, top=.97)
    diagram(ax, 12, 4)
    return fig, ax


def chart():
    fig, ax = plt.subplots(figsize=(8.4, 2.32))
    fig.subplots_adjust(left=.13, right=.95, bottom=.27, top=.91)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=.24)
    ax.set_axisbelow(True)
    return fig, ax


def save(fig, folder, number):
    directory = folder / "figures"
    directory.mkdir(parents=True, exist_ok=True)
    fig.savefig(directory / f"{folder.name}-{number:02}.png", dpi=285, facecolor="white")
    plt.close(fig)


def physics(folder):
    fig, ax = sketch()
    ax.set_aspect("equal")
    theta = np.linspace(0, 2*np.pi, 360)
    ax.plot(5.1 + np.cos(theta), 2 + np.sin(theta), "--", color=MUTED, lw=1.8)
    ax.plot(4.35 + 1.75*np.cos(theta), 2 + np.sqrt(2.5)*np.sin(theta), color=INK, lw=1.8)
    ax.scatter([5.1, 6.1], [2, 2], s=23, c=INK, zorder=4)
    label(ax, 4.98, 1.75, "O", 13)
    label(ax, 6.32, 2.03, "P", 13)
    arrow(ax, 6.1, 2.10, 6.1, 2.81)
    line(ax, 7.6, 2.55, 8.3, 2.55, color=MUTED, ls="--")
    line(ax, 7.6, 1.55, 8.3, 1.55)
    label(ax, 8.48, 2.55, "原圆轨道", 14, ha="left")
    label(ax, 8.48, 1.55, "新椭圆轨道", 14, ha="left")
    save(fig, folder, 3)

    fig, ax = sketch()
    for x in (4.95, 5.17):
        line(ax, x, .86, x, 3.20)
    for x, side in [(4.62, -1), (5.50, 1)]:
        for y in (1.26, 1.76, 2.26, 2.76):
            ax.add_patch(Arc((x, y), .50, .50, theta1=90 if side<0 else -90,
                             theta2=270 if side<0 else 90, color=INK, lw=1.5))
    ax.plot([4.62, 4.62, 1.6, 1.6], [3.01, 3.40, 3.40, 2.46], color=INK, lw=1.5)
    ax.plot([4.62, 4.62, 1.6, 1.6], [1.01, .56, .56, 1.52], color=INK, lw=1.5)
    ax.add_patch(Circle((1.60, 1.99), .46, ec=INK, fc="white", lw=1.4))
    label(ax, 1.60, 1.99, "～", 15)
    ax.plot([5.50, 5.50, 10.5], [3.01, 3.40, 3.40], color=INK, lw=1.5)
    ax.plot([5.50, 5.50, 10.5], [1.01, .56, .56], color=INK, lw=1.5)
    for x, y, name in [(7.65, 2.0, r"$R_1$"), (10.5, 1.35, r"$R_2$")]:
        ax.add_patch(Rectangle((x-.20, y-.35), .40, .70, ec=INK, fc="white", lw=1.45))
        label(ax, x+.46, y, name, 15)
        line(ax, x, .56, x, y-.35)
        line(ax, x, y+.35, x, 3.40 if x==7.65 else 2.18)
    line(ax, 10.5, 2.72, 10.5, 3.40)
    ax.scatter([10.5, 10.5], [2.18, 2.72], c=INK, s=17)
    line(ax, 10.5, 2.18, 10.93, 2.59)
    label(ax, 11.10, 2.72, "S", 14)
    ax.scatter([7.65, 7.65], [.56, 3.40], c=INK, s=19)
    label(ax, 5.06, .18, r"$n_1:n_2=3:1$", 15)
    save(fig, folder, 4)

    fig, ax = sketch()
    ax.add_patch(Rectangle((.75, .35), 6.05, 1.60, color=LIGHT, zorder=-1))
    line(ax, .75, 1.95, 6.80, 1.95)
    line(ax, 4.05, .48, 4.05, 3.5, color=MUTED, ls="--")
    arrow(ax, 2.87, .54, 4.05, 1.95)
    label(ax, 3.60, .97, "$i$", 15)
    label(ax, .97, 2.92, "空气", 14, ha="left")
    label(ax, .97, 1.16, "透明材料", 14, ha="left")
    label(ax, 4.24, 3.37, "法线", 13, ha="left")
    label(ax, 8.93, 3.04, r"$\sin i=0.64$", 16)
    label(ax, 8.93, 2.01, "红光折射率  1.50", 15)
    label(ax, 8.93, .94, "紫光折射率  1.60", 15)
    save(fig, folder, 5)

    fig, ax = sketch()
    ax.set_aspect("equal")
    ax.add_patch(Rectangle((6.84, .37), 4.46, 3.23, color=LIGHT))
    line(ax, 6.84, .32, 6.84, 3.68, ls="--")
    ax.add_patch(Rectangle((3.27, .94), 1.89, 1.89, fill=False, edgecolor=INK, lw=1.8))
    label(ax, 4.21, .59, "$l$", 16)
    arrow(ax, 5.47, 1.88, 6.55, 1.88)
    label(ax, 5.99, 2.27, "$v$", 15)
    for x, y in product((7.38, 8.17, 8.96, 9.75, 10.54), (1.02, 1.78, 2.54)):
        label(ax, x, y, "×", 13)
    label(ax, 8.96, 3.20, r"$B$", 16)
    save(fig, folder, 6)

    fig, axes = plt.subplots(1, 2, figsize=(8.4, 2.32))
    fig.subplots_adjust(left=.135, right=.98, top=.78, bottom=.24, wspace=.34)
    x = np.linspace(0, .80, 200)
    for i, (ax, direction) in enumerate(zip(axes, ("沿 x 轴正向", "沿 x 轴负向")), 1):
        ax.plot(x, np.cos(2*np.pi*x/.80), color=INK, lw=1.8)
        ax.axhline(0, color=MUTED, lw=.8)
        ax.set(xlim=(-.015,.83), ylim=(-1.12,1.12), xticks=[0,.20,.40,.60,.80],
               xticklabels=["0","0.20","0.40","0.60","0.80"], yticks=[-1,0,1],
               yticklabels=["$-A$","0","$A$"], xlabel="$x$ / m")
        ax.set_title(f"波 {i}，{direction}传播", fontsize=13)
        ax.spines[["right","top"]].set_visible(False)
    axes[0].set_ylabel("$y$")
    save(fig, folder, 8)

    fig, ax = sketch()
    for x, height, name in [(3.5, 2.37, "（a）平衡位置"), (8.0, 1.57, "（b）释放位置")]:
        line(ax, x-.95, .54, x+.95, .54, lw=2)
        trace = [.54] + list(np.linspace(.68, height-.11, 12)) + [height]
        ax.plot([x]+[x+(.23 if i%2 else -.23) for i in range(12)]+[x], trace, color=INK, lw=1.6)
        for i, who in enumerate(("乙","甲")):
            y = height+i*.47
            ax.add_patch(Rectangle((x-.65,y),1.30,.47,ec=INK,fc=LIGHT,lw=1.4))
            label(ax, x, y+.23, who, 13)
        label(ax, x, .20, name, 14)
    for y in (1.57,2.37):
        line(ax, 8.68, y, 9.81, y, color=MUTED, ls="--")
    ax.annotate("",(9.28,1.57),(9.28,2.37),arrowprops={"arrowstyle":"<->","lw":1.5,"color":INK})
    label(ax, 10.48, 1.97, r"$3mg/k$", 16)
    save(fig, folder, 9)

    fig, ax = sketch()
    for x, who, cap in [(2.65, "甲", "$C$"),(9.35, "乙", "$2C$")]:
        line(ax, x, .69, x, 1.68)
        line(ax, x, 2.10, x, 3.27)
        for y in (1.68,2.10):
            line(ax,x-.50,y,x+.50,y,lw=2.2)
        label(ax, x+.65, 1.89, who+"  "+cap, 15, ha="left")
    line(ax, 2.65, .69, 9.35, .69)
    line(ax, 2.65, 3.27, 4.05, 3.27)
    ax.scatter([4.05,5.19], [3.27,3.27], c=INK, s=19)
    line(ax,4.05,3.27,5.02,3.70)
    label(ax, 4.46, 2.83, "S", 15)
    line(ax, 5.19, 3.27, 6.48, 3.27)
    ax.add_patch(Rectangle((6.48,3.02),1.08,.50,ec=INK,fc=LIGHT,lw=1.4))
    line(ax, 7.56, 3.27, 9.35, 3.27)
    label(ax, 7.02, 2.73, "R", 15)
    save(fig, folder, 10)


def chemistry(folder):
    fig, ax = sketch()
    ax.set_aspect("equal")
    theta = np.arange(7)*np.pi/3
    center = np.array([3.55,1.97])
    ring = center+np.column_stack([np.cos(theta),np.sin(theta)])
    ax.plot(*ring.T,color=INK,lw=2)
    for i in (0,2,4):
        a, b = .80*ring[i:i+2]+.20*center
        line(ax,*a,*b)
    chain = np.array([[4.55,1.97],[5.43,2.55],[6.36,1.97],[7.22,2.55],[8.02,2.08]])
    ax.plot(*chain.T,color=INK,lw=2)
    line(ax,5.48,2.76,6.41,2.18)
    label(ax, 8.13, 2.01, "OH", 17, ha="left")
    save(fig, folder, 3)

    fig, ax = sketch()
    def project(p):
        x, y, z = p
        return (2.1+2.27*x+1.45*y, .62+2.12*z+.72*y)

    corners = list(product((0,1),repeat=3))
    for i, p in enumerate(corners):
        for q in corners[i+1:]:
            if sum(abs(a-b) for a,b in zip(p,q))==1:
                line(ax,*project(p),*project(q),color=MUTED,ls="--" if p[1]==q[1]==1 else "-")
    for shape, vertices, legend, marker, shade in [
        ("A",corners,3.00,"o","white"),
        ("X",[tuple(v if i==k else .5 for i in range(3)) for k,v in product(range(3),(0,1))],
         1.00,"s",LIGHT),
        ("B",[(.5,.5,.5)],2.00,"o",INK),
    ]:
        xs, ys = zip(*(project(p) for p in vertices))
        ax.scatter([*xs,8.15],[*ys,legend],s=68,marker=marker,edgecolor=INK,facecolor=shade,zorder=6)
        label(ax, 8.53, legend, shape+" 粒子", 16, ha="left")
    save(fig, folder, 5)

    fig, ax = sketch()
    wall = [(3.48,3.52),(4.12,3.52),(4.12,3.18),(5.06,2.71),(5.42,2.24),
            (5.10,1.76),(4.10,.91),(4.10,.42),(3.50,.42),(3.50,.91),
            (2.50,1.76),(2.18,2.24),(2.54,2.71),(3.48,3.18)]
    ax.add_patch(Polygon(wall,closed=True,fill=False,edgecolor=INK,lw=1.55))
    top = [(2.43,2.56),(5.17,2.56),(5.42,2.24),(5.34,2.10),(2.26,2.10),(2.18,2.24)]
    bottom = [(2.26,2.10),(5.34,2.10),(5.10,1.76),(4.10,.91),(3.50,.91),(2.50,1.76)]
    ax.add_patch(Polygon(top,facecolor="#f4f7fa",edgecolor=INK,lw=.95))
    ax.add_patch(Polygon(bottom,facecolor=LIGHT,edgecolor=INK,lw=.95))
    line(ax, 3.26,3.52,4.34,3.52,lw=2.4)
    line(ax,3.18,.79,4.42,.79,lw=2.3)
    label(ax, 3.80, 2.31, "上层", 13)
    label(ax, 3.80, 1.63, "下层", 13)
    label(ax, 8.39, 2.70, r"乙酸乙酯  $\rho\approx0.90\,\mathrm{g/cm^3}$", 15)
    label(ax, 8.39, 1.51, r"水  $\rho\approx1.00\,\mathrm{g/cm^3}$", 15)
    save(fig, folder, 6)

    fig, ax = chart()
    x = np.linspace(0, 7, 180)
    ax.plot(x, .8+.2*np.exp(-.9*x), c=INK, lw=1.9)
    ax.axhline(.80, color=MUTED, ls="--")
    ax.set(xlim=(0,7),ylim=(.768,1.02),xticks=[],yticks=[.80,.90,1.00],
           yticklabels=["0.80","0.90","1.00"],xlabel="时间",ylabel="$p/p_0$")
    save(fig, folder, 7)

    fig, ax = chart()
    bars = ax.bar([0,1],[.48,.30],.42,facecolor=LIGHT,edgecolor=INK)
    ax.bar_label(bars,labels=["0.48","0.30"],padding=3)
    ax.set(ylim=(0,.58),xlim=(-.6,1.6),yticks=[0,.2,.4],
           xticks=[0,1],xticklabels=["加配体溶液","加水"],ylabel="吸光度")
    save(fig, folder, 9)

    fig, ax = sketch()
    ax.add_patch(Rectangle((2.5,.64),7.0,1.98,ec=INK,fc=LIGHT,lw=1.5))
    line(ax, 6.0,.65,6.0,2.61,ls="--",lw=2)
    ax.plot([4.03,4.03,7.97,7.97],[1.82,3.43,3.43,1.82],c=INK,lw=1.6)
    for x in (4.03,7.97):
        line(ax,x,.96,x,1.97,lw=3)
    label(ax, 3.32, 2.25, "负极区", 13)
    label(ax, 8.68, 2.25, "正极区", 13)
    label(ax, 6., 3.62, "外电路", 13)
    label(ax, 6., .35, r"膜仅允许 $\mathrm{H^+}$ 通过", 14)
    arrow(ax, .92,1.69,2.50,1.69)
    arrow(ax, 11.08,1.69,9.50,1.69)
    label(ax, 1.60,2.19,"葡萄糖",14)
    label(ax,10.35,2.19,"氧气",14)
    save(fig, folder, 11)

    fig, ax = chart()
    x = np.array([0,1])
    for i, (values, name, color, hatch) in enumerate([
        ([1.0,2.0],"低转速",LIGHT,""),([1.8,2.0],"高转速","white","///"),
    ]):
        bars = ax.bar(x+(i-.5)*.29,values,.27,facecolor=color,edgecolor=INK,hatch=hatch,label=name)
        ax.bar_label(bars,fmt="%.1f",padding=2,fontsize=11)
    ax.set(xticks=x,xticklabels=["较大颗粒","较小颗粒"],ylim=(0,2.58),yticks=[0,1,2],ylabel=r"$v/v_0$")
    ax.legend(loc="upper left",ncol=2,frameon=False,fontsize=10)
    save(fig, folder, 12)

    fig, ax = sketch()
    arrow(ax,1.25,.35,1.25,3.80)
    label(ax, .92,3.65,"焓",14)
    for y, x, state in [
        (3.01,2.0,r"$\mathrm{C(s)+O_2(g)}$"),
        (2.08,4.95,r"$\mathrm{CO(g)}+\frac{1}{2}\mathrm{O_2(g)}$"),
        (.69,7.92,r"$\mathrm{CO_2(g)}$"),
    ]:
        line(ax,x,y,x+2.38,y,lw=1.9)
        label(ax,x+1.19,y+.38,state,16)
    for x, y0, y1, text in [(4.48,3.01,2.08,r"$\Delta H_1$"),(7.44,2.08,.69,r"$\Delta H_2$")]:
        arrow(ax,x,y0,x,y1)
        line(ax,x,y1,x+.42,y1,ls=":")
        label(ax,x-.68,(y0+y1)/2,text,15)
    save(fig, folder, 13)


def biology(folder):
    fig, ax = chart()
    x = np.linspace(1.45,4.55,250)
    peaks = np.exp(-((x-2)/.19)**2)+.48*np.exp(-((x-4)/.22)**2)+.085*np.exp(-((x-3)/.78)**2)
    ax.fill_between(x,peaks,color=LIGHT)
    ax.plot(x,peaks,color=INK,lw=1.8)
    ax.set(ylim=(0,1.15),xticks=[2,4],xticklabels=["$2C$","$4C$"],yticks=[],
           xlabel="单个细胞的核 DNA 含量",ylabel="相对细胞数")
    save(fig, folder, 3)

    fig, ax = sketch()
    ax.add_patch(Circle((1.75,1.95),.56,ec=INK,fc=LIGHT,lw=1.6))
    line(ax,2.31,1.95,6.7,1.95,lw=2.0)
    ax.add_patch(Polygon([(6.69,1.65),(7.36,1.45),(7.36,2.45),(6.69,2.25)],closed=True,
                         facecolor=LIGHT,edgecolor=INK,lw=1.4))
    ax.add_patch(Rectangle((7.82,1.36),3.1,1.18,ec=INK,fc="white",lw=1.6))
    for y in (1.67,1.97,2.27):
        line(ax,9.52,y,10.91,y,color=MUTED,lw=.75)
    for x, y, who in [(4.23,1.95,"刺激位置①"),(9.0,2.54,"刺激位置②")]:
        arrow(ax,x,3.19,x,y+.10)
        label(ax,x,3.58,who,14)
    label(ax, 3.2,1.25,"运动神经纤维",14)
    label(ax, 7.60,.76,"化学突触",14)
    label(ax, 9.25,1.95,"肌细胞",14)
    line(ax,7.60,1.32,7.60,1.05)
    save(fig, folder, 8)

    fig, ax = chart()
    for k, style, txt in [(60,"--","修复前"),(120,"-","修复后")]:
        n=np.linspace(0,k,200)
        ax.plot(n,n*(1-n/k),style,c=INK,lw=1.7,label=txt)
    ax.axvline(60,color=MUTED,ls=":",lw=.8)
    ax.set(xlim=(0,125),ylim=(0,34),xticks=[0,60,120],yticks=[],xlabel="种群数量 $N$",ylabel="数量变化率")
    ax.legend(frameon=False,loc="upper left",ncol=2,fontsize=10)
    save(fig, folder, 11)

    fig, ax = sketch()
    box(ax,2.05,1.05,"P  生产者")
    box(ax,5.88,3.05,"Q  初级消费者")
    box(ax,9.84,1.05,"R  杂食消费者")
    arrow(ax,2.97,1.41,4.93,2.69)
    arrow(ax,6.93,2.72,8.93,1.39)
    arrow(ax,3.08,1.05,8.37,1.05)
    label(ax,5.89,.43,"箭头表示能量流向",13)
    save(fig, folder, 12)

    fig, ax = chart()
    groups = np.array([0, 1])
    for i, (values, name, color, hatch) in enumerate([
        ([.40,.06],"溶剂组",LIGHT,""),([.15,.06],"X 组","white","///"),
    ]):
        bars=ax.bar(groups+(i-.5)*.24,values,.22,facecolor=color,edgecolor=INK,hatch=hatch,label=name)
        ax.bar_label(bars,fmt="%.2f",padding=2,fontsize=10)
    ax.set(xlim=(-.53,1.53),ylim=(0,.49),yticks=[0,.2,.4],xticks=groups,
           xticklabels=["空气","低氧"],ylabel="褐变指数")
    ax.legend(frameon=False,loc="upper right",ncol=2,fontsize=10)
    save(fig, folder, 16)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    workspace = parser.parse_args().workspace
    for draw in (physics,chemistry,biology):
        draw(workspace/draw.__name__)
