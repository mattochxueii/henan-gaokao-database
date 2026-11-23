"""Render original measurement plots, circuits and molecular diagrams for Phase 22."""
import argparse
from itertools import product
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "phase21" / "source"))
from figures import INK, LIGHT, MUTED, arrow, box, diagram, label, line, np, plt, table
from matplotlib.patches import Circle, Polygon, Rectangle

ACCENT = "#98432f"


def drawing(size=(8.7, 2.1), domain=(12, 4)):
    fig, ax = plt.subplots(figsize=size)
    fig.subplots_adjust(left=.035, right=.965, bottom=.06, top=.94)
    diagram(ax, *domain)
    return fig, ax


def chart(ylabel, xlabel, size=(7.2, 2.14)):
    fig, ax = plt.subplots(figsize=size)
    fig.subplots_adjust(left=.16, right=.97, bottom=.27, top=.94)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set(ylabel=ylabel, xlabel=xlabel)
    ax.grid(axis="y", alpha=.20)
    return fig, ax


def finish(fig, output, subject, number):
    output.mkdir(parents=True, exist_ok=True)
    fig.savefig(output / f"{subject}-{number:02d}.png", dpi=300, facecolor="white")
    plt.close(fig)


def distance(ax, x1, x2, y, name):
    ax.annotate("", (x2, y), (x1, y), arrowprops={"arrowstyle": "<->", "lw": 1.0, "color": INK})
    label(ax, (x1 + x2) / 2, y + .28, name)


def spring(ax, x1, x2, y):
    widths = np.linspace(x1, x2, 13)
    ax.plot(widths, y + np.asarray([0, 0, .2, -.2, .2, -.2, .2, -.2, .2, -.2, .2, 0, 0]),
            color=INK, lw=1.65)


def panel_plots():
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 2.28))
    fig.subplots_adjust(left=.048, right=.971, bottom=.235, top=.88, wspace=.47)
    return fig, axes


def physics(output):
    def end(fig, number):
        finish(fig, output, "physics", number)

    fig, ax = drawing((7.2, 1.83), (18, 5))
    for y, dx, name in [(3.7, 3., "甲"), (2.02, 2., "乙")]:
        label(ax, .6, y, name, 14)
        for step in range(-2, 3):
            x = 8.7 + step * dx
            line(ax, x, y - .43, x, y + .43, lw=3.2 if step == 0 else 1.15)
    for offset in range(-6, 7):
        x = 8.7 + offset
        line(ax, x, .70, x, 1.01)
        if offset % 2 == 0:
            label(ax, x, .36, str(offset))
    label(ax, 16.2, .36, "$x$/mm", 13)
    end(fig, 2)

    fig, ax = chart("$v$/(m/s)", "$t$/s")
    ax.plot([0, 2], [6, 4], "o-", color=INK)
    ax.plot([0, 2], [6, 2], "o--", color=MUTED)
    label(ax, 1.42, 4.98, "甲")
    label(ax, 1.42, 2.84, "乙")
    ax.set(xlim=(-.05, 2.25), ylim=(0, 7), xticks=[0, 1, 2], yticks=[0, 2, 4, 6])
    end(fig, 3)

    fig, ax = drawing((7.5, 2.03), (12, 4))
    ax.set_aspect("equal")
    ax.add_patch(Rectangle((2.3, 1.2), 4.0, 2.4, edgecolor=INK, facecolor=LIGHT, linewidth=1.5))
    line(ax, 5.25, .2, 5.25, 2.33, ls="--", color=MUTED)
    line(ax, 5.7, 2.6, 7.25, 2.6, ls="--", color=MUTED)
    arrow(ax, 5.25 - 3 / np.sqrt(7), .2, 5.25, 1.2)
    arrow(ax, 5.25, 1.2, 6.30, 2.60)
    arrow(ax, 6.30, 2.60, 6.30, 3.83)
    label(ax, 3.70, 2.79, "玻璃")
    label(ax, 8.39, 2.21, "待测液体")
    label(ax, 7.48, .60, r"已知液体　$\sin i=3/4$", 15)
    label(ax, 5.02, .69, "$i$", 15)
    # Segment directions reflect the printed incidence and refracted angle.
    end(fig, 4)

    fig = plt.figure(figsize=(9.0, 2.25))
    grid = fig.add_gridspec(2, 4, left=.065, right=.972, bottom=.15, top=.98, hspace=.24, wspace=.60,
                            height_ratios=[1.0, 2.05])
    ax = fig.add_subplot(grid[0, :])
    diagram(ax, 12, 2.0)
    for x, symbol in [(5, "⊙"), (7, "⊗")]:
        ax.add_patch(Rectangle((x, .32), 2, 1.45, facecolor=LIGHT if x == 5 else "white",
                               edgecolor=INK, linewidth=1.1))
        label(ax, x + 1, 1.06, symbol, 16)
    ax.add_patch(Rectangle((3, .55), 2, 1, fill=False, edgecolor=INK, linewidth=1.4))
    arrow(ax, .8, 1.1, 2.75, 1.1)
    label(ax, 1.68, 1.60, "$v$")
    label(ax, 10.2, 1.02, "线框初始位置如图", 13)
    profiles = [(1,-2,1),(-1,1,-1),(-1,2,0),(-1,2,-1)]
    for i, levels in enumerate(profiles):
        ax = fig.add_subplot(grid[1, i])
        ax.axhline(0, color=MUTED, lw=.8)
        ax.stairs([*levels, 0], [0, 1, 2, 3, 3.25], baseline=None, color=INK, linewidth=1.6)
        ax.set(xlim=(0, 3.3), ylim=(-2.28, 2.67), xticks=[0, 1, 2, 3],
               yticks=[-2, -1, 0, 1, 2] if i == 0 else [])
        ax.set_xticklabels(["0", "$T$", "$2T$", "$3T$"])
        ax.tick_params(axis="both", labelsize=10, pad=1)
        ax.spines[["top", "right"]].set_visible(False)
        ax.text(.07, .82, "ABCD"[i], transform=ax.transAxes, fontsize=14)
        if i == 0:
            ax.set_ylabel("$I/I_0$", labelpad=1, fontsize=11)
    end(fig, 5)

    fig, ax = chart("归一化光强", "$t$/s")
    time = np.linspace(0, 3.2, 180)
    ax.plot(time, 2**(-time / 2), color=INK)
    ax.plot(time, 2**(-time), "--", color=MUTED)
    ax.scatter([2, 2], [.5, .25], color=INK, s=17)
    ax.vlines(2, 0, .50, color=MUTED, linestyles=":", lw=1)
    label(ax, 2.84, .45, "甲")
    label(ax, 2.84, .18, "乙")
    ax.set(xlim=(0, 3.2), ylim=(0, 1.05), xticks=[0, 1, 2, 3], yticks=[0, .25, .50, .75, 1])
    end(fig, 6)

    fig, ax = drawing()
    line(ax, .55, 1.02, 4.2, 1.02)
    line(ax, 1.05, 1.02, 1.05, 2.42)
    spring(ax, 1.05, 2.55, 1.42)
    ax.add_patch(Rectangle((2.55, 1.02), .51, .45, ec=INK, fc=LIGHT))
    x = np.linspace(4.2, 10.7, 180)
    ax.plot(x, 1.02 + 1.85 * np.sin((x - 4.2) * np.pi / 8.5)**2, color=INK, lw=1.8)
    ax.scatter([8.45], [2.87], color=INK, s=17, zorder=5)
    line(ax, 3.35, 1.02, 4.22, 1.02, lw=5, color=MUTED)
    label(ax, 3.73, 1.52, "粗糙段")
    distance(ax, 3.35, 4.22, .51, "$2R$")
    line(ax, 8.45, 1.02, 8.45, 2.86, ls="--", color=MUTED)
    label(ax, 8.73, 3.18, "P")
    label(ax, 8.68, 1.94, "$R$")
    label(ax, 10.30, 3.38, "P 点曲率半径为 $R$", 13)
    label(ax, 1.82, 2.42, "弹射起点")
    end(fig, 7)

    fig, ax = chart("位移", "$x$/m", (7.2, 2.13))
    x = np.linspace(0, 1.2, 400)
    for sign, style in [(1, "-"),(-1,"--")]:
        ax.plot(x, sign*np.sin(np.pi*x/.4), style, color=INK, lw=1.45)
    ax.axhline(0, color=MUTED, lw=.8)
    ax.scatter([0, .4, .8, 1.2], [0]*4, s=11, color=INK)
    ax.set(xlim=(-.02, 1.23), ylim=(-1.17, 1.17), yticks=[0], xticks=np.arange(0,1.21,.2),
           xticklabels=["0", "0.20", "0.40", "0.60", "0.80", "1.00", "1.20"])
    end(fig, 8)

    fig, ax = drawing()
    # A switch disconnects the supply from the common top node. Both lower plates share a node.
    line(ax, .95, 3.36, 2.40, 3.36)
    line(ax, 2.42, 3.36, 3.12, 3.76)
    ax.scatter([2.40, 3.18], [3.36, 3.36], color=INK, s=12)
    line(ax, 3.18, 3.36, 10.90, 3.36)
    line(ax, .95, .47, 10.90, .47)
    for x0, short, long in [(5.55, 1.77, 2.40), (8.12, 1.15, 2.40)]:
        line(ax, x0, 3.36, x0, long)
        line(ax, x0, .47, x0, short)
        line(ax, x0-.72, short, x0+.72, short, lw=2.1)
        line(ax, x0-.72, long, x0+.72, long, lw=2.1)
        label(ax, x0 + 1.02, (long+short)/2, "$d$" if x0 < 6 else "$2d$")
    line(ax, 4.83, 1.15, 6.27, 1.15, ls="--", color=MUTED)
    arrow(ax, 5.09, 1.67, 5.09, 1.23)
    line(ax, .95, 3.36, .95, 2.04)
    line(ax, .95, 1.63, .95, .47)
    line(ax, .54, 2.04, 1.36, 2.04)
    line(ax, .71, 1.63, 1.19, 1.63)
    for y1, y2 in [(.47, 1.56), (2.27, 3.36)]:
        line(ax, 10.90, y1, 10.90, y2)
    ax.add_patch(Circle((10.90, 1.92), .35, fc="white", ec=INK))
    label(ax, 10.90, 1.92, "V")
    label(ax, 2.72, 2.97, "S")
    label(ax, 7.12, 3.72, "a")
    end(fig, 10)

    fig, (ax, bx) = panel_plots()
    diagram(ax, 9, 4)
    line(ax, .4, 1.15, 8.8, 1.15)
    line(ax, .7, 1.15, .7, 2.6)
    spring(ax, .72, 2.45, 1.59)
    ax.add_patch(Rectangle((2.45, 1.15), 1.12, .67, fc=LIGHT, ec=INK))
    for x0 in np.linspace(4.4, 8.6, 18):
        line(ax, x0, 1.12, x0 - .22, .92, lw=.7)
    line(ax, 7.08, 1.16, 7.08, 2.76)
    ax.scatter([7.08, 4.24], [1.15, 1.15], color=INK, s=16)
    label(ax, 4.24, .74, "P")
    label(ax, 7.08, .74, "Q")
    label(ax, 7.08, 3.02, "光电门")
    distance(ax, 4.24, 7.08, .18, "0.40 m")
    label(ax, 3.60, 3.63, "图 1")
    bx.plot([2,4,6,8], [.5,1.5,2.5,3.5], "o-", color=INK)
    bx.spines[["top","right"]].set_visible(False)
    bx.set(xlim=(0,9), ylim=(0,4), xticks=[0,2,4,6,8], yticks=[.5,1.5,2.5,3.5],
           xlabel=r"$x^2/(10^{-3}\,\mathrm{m^2})$", ylabel=r"$v_Q^2/(\mathrm{m^2\,s^{-2}})$", title="图 2")
    bx.grid(alpha=.2)
    end(fig, 11)

    fig, (ax, bx) = panel_plots()
    diagram(ax, 9, 4)
    for p in [(1.0, .44, 1.0, 2.5),(1.0, 2.5, 7.8, 2.5),(7.8, 2.5, 7.8, .44), (1.0,.44,7.8,.44),
              (4.45, .44, 4.45, 1.38), (7.8, .44, 7.8, 1.38), (4.45,1.38,7.8,1.38)]:
        line(ax, *p)
    for x0,y0,txt in [(2.35,2.50,"a"),(6.11,1.38,"b")]:
        ax.add_patch(Circle((x0,y0),.38,fc="white",ec=INK,zorder=3))
        label(ax,x0,y0,txt,zorder=4)
    ax.add_patch(Rectangle((5.24,.25),1.68,.38,fc=LIGHT,ec=INK,zorder=3))
    label(ax,6.06,.17,"电阻丝",11,va="top")
    ax.add_patch(Rectangle((2.92,.19),1.14,.65,fc="white",ec="none",zorder=3))
    line(ax,3.18,.44,3.18,.85,zorder=4)
    line(ax,3.18,.44,3.18,.06,zorder=4)
    line(ax,3.49,.22,3.49,.66,zorder=4)
    line(ax,2.94,.44,3.18,.44,zorder=4)
    line(ax,3.49,.44,4.10,.44,zorder=4)
    ax.annotate("",(3.78,.91),(2.97,.12),
                arrowprops={"arrowstyle":"->","lw":1.0,"color":INK},zorder=5)
    label(ax,2.55,1.02,"可调直流电源",10)
    label(ax,4.35,3.62,"图 1")
    bx.plot([0,25,50,75,100], [10,9.5,9,8.5,8], "-", color=INK)
    bx.scatter([25, 50, 75, 100], [9.5, 9, 8.5, 8], color=INK, s=17)
    bx.spines[["top","right"]].set_visible(False)
    bx.set(xlim=(0,105), ylim=(7.78,10.2), xticks=[0,25,50,75,100], yticks=[8,8.5,9,9.5,10],
           xlabel=r"$I^2/(\mathrm{mA}^2)$", ylabel=r"$(1/R)/\mathrm{k\Omega}^{-1}$", title="图 2")
    bx.grid(alpha=.2)
    end(fig, 12)

    fig, ax = drawing()
    for y in [1.18, 3.02]:
        line(ax, 3.21, y, 7.15, y, lw=2.2)
    line(ax, 2.55, 2.10, 10.23, 2.10, ls="--", color=MUTED)
    line(ax, 10.23, .56, 10.23, 3.44, lw=2.3)
    label(ax, 10.92, 2.1,"荧光屏")
    arrow(ax, .85, 2.1, 2.58, 2.1)
    arrow(ax, 5.34, 1.44, 5.34, 2.73)
    label(ax, 5.66, 2.25, "$E$")
    distance(ax, 3.21, 7.15, .61, "$L$")
    distance(ax, 7.15, 10.23, .61, "$L$")
    ax.annotate("", (2.82,3.02),(2.82,1.18),arrowprops={"arrowstyle":"<->","color":INK})
    label(ax, 2.49, 2.47, "$h$")
    end(fig, 13)

    fig, ax = drawing((7.0,2.15),(12,4))
    ax.add_patch(Rectangle((4.15,.43),3.47,1.04,fc=LIGHT,ec="none"))
    for p in [(4.15,.43,4.15,3.55),(7.62,.43,7.62,2.74),(7.62,3.13,7.62,3.55),(4.15,.43,7.62,.43),(4.15,3.54,7.62,3.54)]:
        line(ax,*p)
    ax.add_patch(Rectangle((4.15,1.46),3.47,.22,fc=MUTED,ec=INK))
    ys = np.linspace(3.53,2.47,13)
    ax.plot(5.89+np.asarray([0,0,.25,-.25,.25,-.25,.25,-.25,.25,-.25,.25,0,0]),ys,color=INK,lw=1.55)
    line(ax, 4.68, 2.47, 7.12, 2.47, ls="--", color=MUTED)
    ax.annotate("",(6.93,2.47),(6.93,1.68),arrowprops={"arrowstyle":"<->","color":INK})
    arrow(ax, 7.52, 2.93, 8.45, 2.93)
    label(ax, 8.98, 2.93, "通大气", 12)
    label(ax, 8.35, 2.10, "$V_0/S$", 15)
    label(ax, 2.85, 1.60, "初始位置")
    label(ax, 5.89, .93, "气体")
    end(fig, 14)

    fig, ax = drawing()
    ax.add_patch(Rectangle((1.5,.78),9.0,.77,fc=LIGHT,ec=INK))
    for x0 in (2.13,9.89):
        ax.add_patch(Circle((x0,.53),.21,fill=False,ec=INK))
    for x0 in np.linspace(1.55,5.50,26):
        line(ax,x0,1.58,x0+.08,1.72,lw=.65)
    spring(ax,5.5,10.12,1.92)
    line(ax,10.12,1.55,10.12,2.70)
    ax.add_patch(Rectangle((.58,1.58),.87,.65,fc="white",ec=INK))
    label(ax,1.03,1.88,"$m$")
    label(ax,7.30,1.12,"$3m$")
    arrow(ax,.72,2.80,2.88,2.80)
    label(ax,1.76,3.20,"$v$")
    label(ax,1.50,2.44,"O")
    label(ax,5.50,2.44,"P")
    distance(ax,1.5,5.5,3.46,"$d$")
    end(fig, 15)


def ring(ax, cx, cy, size=.75, groups=None):
    angles = np.deg2rad(np.arange(0,360,60))
    vertices = np.column_stack([cx + size * np.cos(angles), cy + size * np.sin(angles)])
    ax.add_patch(Polygon(vertices, closed=True, fill=False, edgecolor=INK, linewidth=1.55))
    for i in (0, 2, 4):
        p, q = .75*vertices[[i,(i+1)%6]] + .25*np.array([cx,cy])
        p2, q2 = .84*p + .16*q, .84*q + .16*p
        line(ax,*p2,*q2,lw=1)
    for index, group in (groups or {}).items():
        dx, dy = np.cos(angles[index]), np.sin(angles[index])
        x, y = vertices[index]
        line(ax,x,y,x+.34*dx,y+.34*dy)
        label(ax,x+.40*dx,y+.46*dy,group,13,ha="left" if dx>0 else "right")
    return vertices


def chemistry(output):
    def end(fig, number):
        finish(fig, output, "chemistry", number)

    fig, ax = drawing((7.4,2.0),(12,4))
    ax.set_aspect("equal")
    for cx, cy in [(4.54,2.0),(6.0,2.84),(7.46,2.0),(6.0,1.16)]:
        for i in range(6):
            a, b = np.deg2rad([60*i, 60*(i+1)])
            line(ax,cx+.97*np.cos(a),cy+.97*np.sin(a),cx+.97*np.cos(b),cy+.97*np.sin(b),lw=1.1)
        for i in range(6):
            a = np.deg2rad(60*i)
            x,y = cx+.97*np.cos(a),cy+.97*np.sin(a)
            ax.add_patch(Circle((x,y),.17,fc=LIGHT if i%2==0 else "white",ec=INK,zorder=3))
            label(ax,x,y,"B" if i%2==0 else "N",9,zorder=4)
    end(fig, 2)

    fig, ax = drawing()
    for x, read, positions, title in [(3.35,3.10,[2,3,4],"滴定前"),(8.65,20.40,[19,20,21],"滴定后")]:
        y0=2.73
        line(ax,x-.55,.85,x-.55,3.28)
        line(ax,x+.55,.85,x+.55,3.28)
        for index in range(21):
            y = y0 - index*.102
            line(ax,x+.25 if index%10==0 else x+.37,y,x+.55,y,lw=.7)
            if index%10==0:
                label(ax,x+.90,y,str(positions[index//10]),11)
        lower = (read - positions[0])*1.02
        y = y0-lower
        xx=np.linspace(x-.52,x+.52,60)
        ax.plot(xx,y+.32*((xx-x)/.52)**2,color=INK,lw=1.35)
        for side in (-1,1):
            xx=x+side*.55
            line(ax,xx-.09,.95,xx+.09,1.12,lw=1.0)
        label(ax,x,3.69,title+" / mL",13)
        tip = x - 1.75
        label(ax,tip+.48,.55,"尖嘴",11,ha="left")
        label(ax,x,3.36,f"{read:.2f}",11)
        line(ax,tip-.22,.75,tip-.09,.57)
        line(ax,tip+.22,.75,tip+.09,.57)
        line(ax,tip-.09,.57,tip-.09,.39)
        line(ax,tip+.09,.57,tip+.09,.39)
        if title=="滴定前":
            ax.add_patch(Circle((tip,.52),.07,fc="white",ec=MUTED))
    end(fig, 3)

    fig, ax = drawing()
    for x,y,t in [(1.48,2.05,"脱硫石膏"),(4.51,2.05,"转化、过滤"),(9.06,3.06,"滤液 → 硫酸铵（氮肥原料）"),(9.06,1.03,"滤渣 → 碳酸氢钙溶液")]:
        box(ax,x,y,t)
    arrow(ax,2.50,2.05,3.60,2.05)
    label(ax,3.06,2.52,"加 X")
    for y in (3.06,1.03):
        arrow(ax,5.48,2.05,7.20,y)
    label(ax,10.73,.46,"水中通入 $CO_2$",12)
    end(fig, 4)

    fig, ax = chart("相对浓度", "", (6.9,2.0))
    ax.bar([0,1,2],[1,1,4],width=.52,color=LIGHT,edgecolor=INK)
    ax.set(xticks=[0,1,2],xticklabels=[r"$Ca^{2+}$",r"$Mg^{2+}$",r"$HCO_3^-$"],yticks=range(5),
           ylim=(0,4.5),xlim=(-.6,2.6))
    end(fig, 6)

    fig, ax = drawing((7.2,2.05),(12,4))
    r=1.05
    points=ring(ax,5.23,1.94,r,{3:"HO",2:r"$H_3CO$"})
    x,y=points[0]
    path=np.array([[x,y],[7.24,2.46],[8.41,1.94],[9.24,2.46]])
    ax.plot(*path.T,color=INK,lw=1.55)
    line(ax,7.24,2.24,8.41,1.74,lw=1.05)
    label(ax,9.34,2.48,r"$COOH$",17,ha="left")
    end(fig, 7)

    fig, ax = chart(r"相对焓 / $(\mathrm{kJ\cdot mol^{-1}})$", "反应进程", (8.1,2.32))
    ax.set(xticks=[0,1,2,3,4], xticklabels=["反应物","过渡态 1","吸附中间体","过渡态 2","产物"],
           xlim=(-.3,4.36),ylim=(-35,46),yticks=[-24,0,24])
    for energies, color, style in [([0,24,-24,18,-18],INK,"-"),([0,33,-12,25,-18],ACCENT,"--")]:
        x = np.arange(5)
        ax.plot(x,energies,"o"+style,color=color,lw=1.35,ms=3.3)
        for index in (1,2,3):
            if color == ACCENT:
                x_offset, y_offset = .07, 5
            else:
                x_offset, y_offset = -.17, -7
            label(ax,index+x_offset,energies[index]+y_offset,str(energies[index]),11,
                  ha="left" if color == ACCENT else "right")
    label(ax,.04,6,"0",11,ha="left")
    label(ax,4.05,-23,"−18",11,ha="left")
    label(ax,.05,40,"实线甲　虚线乙",11,ha="left")
    end(fig, 8)

    fig, ax = drawing((8.8,2.4),(12,4.6))
    ax.add_patch(Rectangle((4.22,.82),3.55,2.20,fc=LIGHT,ec="none"))
    ax.add_patch(Rectangle((1.20,.82),9.60,2.20,fill=False,ec=INK))
    for x, txt in [(2.74,"酸室"),(6.0,"盐室"),(9.29,"碱室")]:
        label(ax,x,1.70,txt,14)
    for x, txt in [(4.22,r"仅通 $SO_4^{2-}$"),(7.77,r"仅通 $Na^+$")]:
        line(ax,x,.82,x,3.02,color=MUTED,lw=2.2)
        label(ax,x,.40,txt,13)
    for p in [(1.75,1.95,1.75,3.92),(10.25,1.95,10.25,3.92),(1.75,3.92,5.05,3.92),
              (6.95,3.92,10.25,3.92)]:
        line(ax,*p)
    box(ax,6,3.92,"＋　直流　−")
    label(ax,1.99,2.53,"惰性电极",11)
    label(ax,9.47,2.53,"惰性电极",11)
    end(fig, 9)

    fig, ax = chart("分布分数","pH",(8.1,2.28))
    x=np.linspace(0,12,401)
    h=10**(-x)
    k1,k2=1e-4,1e-8
    denominator=h*h+k1*h+k1*k2
    for y, style, color in [(h*h,"-",INK),(k1*h,"--",MUTED),(k1*k2,"-.",ACCENT)]:
        ax.plot(x,y/denominator,style,color=color,lw=1.75)
    ax.set(xlim=(0,12),ylim=(0,1.08),xticks=range(0,13,2),yticks=[0,.5,1])
    for p in (4,8):
        ax.vlines(p,0,.5,colors=MUTED,linestyles=":",lw=1)
    for x0,t in [(1.75,r"$H_2A$"),(6,r"$HA^-$"),(10.3,r"$A^{2-}$")]:
        label(ax,x0,.79,t,13)
    end(fig, 10)

    fig, axes = plt.subplots(1, 4, figsize=(8.7,2.35))
    fig.subplots_adjust(left=.07,right=.98,bottom=.25,top=.79,wspace=.27)
    for ax,z in zip(axes,(0,.25,.5,.75)):
        ax.set(xlim=(-.09,1.09),ylim=(-.09,1.09),aspect="equal",xticks=[0,.25,.5,.75,1],
               yticks=[0,.25,.5,.75,1] if z==0 else [],title=f"$z={z:g}$")
        ax.set_xticklabels(["0",".25",".5",".75","1"])
        ax.tick_params(labelsize=9,pad=1)
        if z==0:
            ax.set_yticklabels(["0",".25",".5",".75","1"])
            ax.set_ylabel("$y$",labelpad=1,fontsize=10)
        ax.grid(alpha=.24,linewidth=.55)
        ax.add_patch(Rectangle((0,0),1,1,fill=False,ec=MUTED,lw=.8))
        if z == 0:
            coords=[*product((0,1),repeat=2),(.5,.5)]
        elif z == .5:
            coords=[(.5,0),(.5,1),(0,.5),(1,.5)]
        else:
            coords=list(product((.25,.75),repeat=2))
        ax.scatter(*zip(*coords),s=37,c=INK if z in (0,.5) else "white",edgecolors=INK,lw=1.0)
    fig.text(.5,.040,"各图横轴为 $x$、纵轴为 $y$　　● 氧离子　○ 锂离子　　底面与顶面点位相同",
             ha="center",fontsize=11)
    end(fig, 11)

    fig, ax = chart("质量占初始值 / %","温度升高",(7.7,2.25))
    ax.plot([0,1,1.7,3,3.6,5,5.8,7.6],[100,100,87.67,87.67,68.49,68.49,38.36,38.36],
            "-k",lw=1.6)
    ax.set(xticks=[],xlim=(0,7.9),ylim=(30,111),yticks=[40,60,80,100])
    for x,y,t in [(.6,103,"A　100.0"),(2.45,91.5,"B　87.7"),(4.42,73,"C　68.5"),(6.81,42.8,"D　38.4")]:
        label(ax,x,y,t,12)
    end(fig, 12)

    fig, ax = drawing((7.3,2.3),(12,4))
    vertices=ring(ax,5.3,1.6,1.05,{0:r"$COOH$"})
    x,y=vertices[1]
    line(ax,x,y,6.05,2.82)
    label(ax,6.16,2.96,"O",15)
    line(ax,6.34,2.96,6.87,2.96)
    label(ax,7.12,2.96,r"$^{13}C$",16)
    line(ax,7.12,3.24,7.12,3.62)
    line(ax,7.23,3.24,7.23,3.62,lw=1.0)
    label(ax,7.18,3.84,"O",15)
    line(ax,7.39,2.96,7.87,2.96)
    label(ax,7.97,2.97,r"$CH_3$",15,ha="left")
    end(fig, 13)

    fig, ax=chart("$pX$","$pCl$",(7.7,2.26))
    x=np.linspace(0,9,90)
    ax.plot(x,10-x,color=INK,lw=1.55)
    ax.plot(x,5-2*x,"--",color=ACCENT,lw=1.55)
    ax.axhline(2,color=MUTED,lw=.9,ls=":")
    ax.set(xlim=(0,9),ylim=(-1,11),xticks=range(0,10),yticks=range(0,11,2))
    label(ax,5.98,6.76,r"$pAg=10-pCl$",12)
    label(ax,1.97,3.27,r"$pPb=5-2pCl$",12)
    label(ax,6.35,1.29,"初始值 $pX=2$",11)
    end(fig, 14)

    fig, ax=drawing((8.9,2.47),(16,5.2))
    for x,y,t in [(1.22,3.26,"正极粉"),(4.04,3.26,"氧化浸出"),(7.34,3.26,"除铝"),(10.38,3.26,"除镁"),
                  (13.78,3.26,"沉锂、过滤"),(13.78,1.51,"母液")]:
        box(ax,x,y,t)
    for a,b in [(2.07,3.0),(5.22,6.58),(8.03,9.62),(11.09,12.53)]:
        arrow(ax,a,3.26,b,3.26)
    arrow(ax,12.85,1.51,11.23,1.51)
    arrow(ax,11.23,1.51,11.23,3.23)
    arrow(ax,14.49,1.51,15.61,1.51)
    arrow(ax,13.78,2.87,13.78,1.91)
    label(ax,11.76,1.05,"返回 $3/4$")
    label(ax,15.2,1.06,"排出")
    label(ax,4.03,4.55,r"酸、$H_2O_2$")
    label(ax,9.63,4.55,"分段加碱、过滤")
    label(ax,14.01,4.55,r"$Na_2CO_3$")
    end(fig, 15)

    fig, ax=drawing((8.1,1.87))
    table(ax,[["清洗液放置条件","原样滴定 / mL","配对空白滴定 / mL"],
              ["未加二氧化锰","26.00","14.00"],["接触二氧化锰","20.00","14.00"]],[.42,.27,.31])
    end(fig, 16)

    fig, ax=chart("分数","温度",(8.0,2.25))
    x=[0,1]
    ax.bar([t-.16 for t in x],[.75,.8],width=.31,fc=LIGHT,ec=INK,label=r"$CO_2$ 转化率")
    ax.bar([t+.16 for t in x],[2/3,.5],width=.31,fc="white",ec=INK,hatch="///",label=r"$CH_4$ 选择性")
    for location,h,t in [(-.16,.75,"0.75"),(.16,2/3,"$2/3$"),(.84,.8,"0.80"),(1.16,.50,"0.50")]:
        label(ax,location,h+.045,t,12)
    ax.set(xlim=(-.48,1.48),ylim=(0,1.18),xticks=x,xticklabels=["$T_1$","$T_2$"],yticks=[0,.25,.5,.75,1])
    ax.legend(frameon=False,loc="upper center",ncol=2,fontsize=11)
    end(fig, 17)

    fig, ax=drawing((8.9,2.81),(17,6))
    ring(ax,1.70,4.66,.56,{0:"CHO",3:"HO"})
    label(ax,1.70,3.67,"A")
    box(ax,5.61,4.66,"B")
    ring(ax,9.50,4.66,.56,{0:"CHO",3:"BnO",2:"Br"})
    label(ax,9.50,3.67,"C")
    box(ax,14.26,4.66,"D")
    ring(ax,14.26,1.47,.56,{0:"COOH",3:"BnO",2:r"$H_3CO$"})
    label(ax,14.26,.44,"E")
    box(ax,9.65,1.47,"F")
    box(ax,4.89,1.47,"G")
    for a,b,y,t in [(3.65,5.20,4.66,"① 单溴代"),(6.01,7.57,4.66,"② BnCl"),(11.59,13.83,4.66,"③ 信息Ⅰ"),
                    (12.31,10.11,1.47,"⑤ 酯化"),(9.25,5.40,1.47,"⑥ 信息Ⅱ")]:
        arrow(ax,a,y,b,y)
        label(ax,(a+b)/2,y+.49,t,12)
    arrow(ax,14.26,4.24,14.26,2.46)
    label(ax,15.60,3.28,"④ 选择性氧化",12)
    end(fig, 18)

    fig, ax=drawing((8.7,2.0),(17,4))
    ring(ax,1.67,2.0,.68,{0:"CHO",3:"BnO",2:"H₃CO"})
    label(ax,1.67,.58,"A")
    for x,t in [(6.3,"B"),(10.61,"C"),(15.40,"G")]:
        box(ax,x,2.0,t)
    for x1,x2,t in [(3.18,5.85,"① 氧化"),(6.82,10.15,"② 酯化"),(11.17,14.9,"③ 脱苄基")]:
        arrow(ax,x1,2.,x2,2.)
        label(ax,(x1+x2)/2,2.52,t)
    fig.savefig(output/"chemistry-18-draft.png",dpi=300,facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("subject",choices=("physics","chemistry"))
    parser.add_argument("output",type=Path)
    args=parser.parse_args()
    (physics if args.subject=="physics" else chemistry)(args.output)
