"""Draw the original high-resolution line diagrams and model data for Phase 21."""

from pathlib import Path
import argparse

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import fontManager
from matplotlib.patches import Circle, Rectangle
import numpy as np

AVAILABLE_FONTS = {font.name for font in fontManager.ttflist}
CJK = next((name for name in ("Microsoft YaHei", "Noto Sans CJK SC", "SimHei")
            if name in AVAILABLE_FONTS), None)
if CJK is None:
    raise RuntimeError("需要微软雅黑、思源黑体或黑体以绘制中文题图")
plt.rcParams.update({
    "font.family": [CJK, "DejaVu Sans"],
    "mathtext.fontset": "stix",
    "font.size": 12,
    "axes.unicode_minus": False,
})
INK = "#182633"
MUTED = "#476777"
LIGHT = "#e4edf1"


def diagram(ax, xmax, ymax):
    ax.set(xlim=(0, xmax), ylim=(0, ymax))
    ax.axis("off")


def line(ax, x1, y1, x2, y2, **kw):
    ax.plot([x1, x2], [y1, y2], color=kw.pop("color", INK), lw=kw.pop("lw", 1.6), **kw)


def arrow(ax, x1, y1, x2, y2):
    ax.annotate("", (x2, y2), (x1, y1),
                arrowprops={"arrowstyle": "->", "color": INK, "lw": 1.5, "mutation_scale": 15})


def label(ax, x, y, text, size=12, **kw):
    ax.text(x, y, text, ha=kw.pop("ha", "center"), va=kw.pop("va", "center"),
            fontsize=size, color=INK, **kw)


def box(ax, x, y, text):
    label(ax, x, y, text, 13.5, bbox={"boxstyle": "round,pad=.30", "fc": "#f4f7f9", "ec": INK})


def table(ax, rows, widths):
    ax.axis("off")
    cells = ax.table(cellText=rows[1:], colLabels=rows[0], cellLoc="center",
                     colWidths=widths, bbox=(.015, .15, .97, .70))
    cells.auto_set_font_size(False)
    cells.set_fontsize(13.5)
    for (r, _), cell in cells.get_celld().items():
        cell.set_edgecolor(MUTED)
        cell.set_text_props(color=INK)
        cell.set_facecolor(LIGHT if r == 0 else "white")


def save(fig, out, name):
    fig.savefig(out / f"{name}.png", dpi=230, facecolor="white")
    plt.close(fig)


def physics(out):
    fig, (ax, data) = plt.subplots(1, 2, figsize=(10.9, 3.15), gridspec_kw={"width_ratios": [1, 1.12]})
    fig.subplots_adjust(left=.02, right=.98, wspace=.05)
    diagram(ax, 10, 5)
    line(ax, .7, 1.4, 9.4, 1.4, lw=2.5)
    for x, name in [(2, "A"), (8, "B")]:
        ax.add_patch(Rectangle((x-.25, 1.4), .50, 1.25, fill=False, ec=INK, lw=1.5))
        label(ax, x, 2.96, f"{name} 门")
    ax.add_patch(Rectangle((4.2, 1.62), 1.9, .64, facecolor=LIGHT, edgecolor=INK))
    for x in (4.55, 5.78):
        ax.add_patch(Circle((x, 1.57), .17, ec=INK, fc="white"))
    ax.add_patch(Rectangle((5.01, 2.26), .27, .6, facecolor=INK))
    line(ax, 4.14, 3.35, 5.03, 2.80)
    label(ax, 3.72, 3.58, "遮光片")
    arrow(ax, 2, .68, 8, .68)
    label(ax, 5, .23, "正方向")
    table(data, [["运动方向", "A 门 / ms", "B 门 / ms"],
                 ["A → B", "10.00", "8.00"], ["B → A", "20.00", "10.00"]], [.34, .33, .33])
    save(fig, out, "physics-11")

    fig, (ax, graph) = plt.subplots(1, 2, figsize=(10.8, 3.6), gridspec_kw={"width_ratios": [1, 1]})
    fig.subplots_adjust(left=.035, right=.97, top=.88, bottom=.2, wspace=.26)
    diagram(ax, 6, 4.1)
    left, right = .65, 5.28
    for x in (left, right):
        line(ax, x, .55, x, 3.37)
        ax.plot(x, 2.05, "o", ms=4, color=INK)
    for y in (.55, 2.05, 3.37):
        line(ax, left, y, 2.58, y)
        line(ax, 3.39, y, right, y)
    line(ax, 2.78, .24, 2.78, .86, lw=2)
    line(ax, 3.15, .38, 3.15, .72, lw=2)
    line(ax, 2.58, .55, 2.78, .55)
    line(ax, 3.15, .55, 3.39, .55)
    label(ax, 2.56, .91, "+")
    label(ax, 3.4, .91, "−")
    for y, name in [(2.05, "V"), (3.37, "A")]:
        ax.add_patch(Circle((2.985, y), .405, edgecolor=INK, facecolor="white", lw=1.4))
        label(ax, 2.985, y, name, 13)
    ax.add_patch(Rectangle((4.07, 3.18), .79, .38, ec=INK, fc="white", lw=1.3))
    arrow(ax, 4.82, 3.89, 4.32, 3.47)
    label(ax, 5.12, 3.90, "$R$")
    ax.set_title("图甲")
    values = np.array([0, 20, 40, 60, 80, 100])
    graph.plot(values, 4.8-.024*values, color=INK, linewidth=1.5)
    graph.scatter(values[1:], 4.8-.024*values[1:], color=INK, s=20, zorder=3)
    graph.scatter([0], [4.8], edgecolor=INK, facecolor="white", zorder=4, s=25)
    graph.annotate("4.80", (0, 4.8), xytext=(9, 5), textcoords="offset points", color=INK)
    graph.annotate("2.40", (100, 2.4), xytext=(-29, 15), textcoords="offset points", color=INK)
    graph.set(xlim=(-3, 108), ylim=(1.9, 5.17), xticks=values, yticks=[2, 3, 4, 5],
              xlabel="$I$ / mA", ylabel="$U$ / V", title="图乙")
    graph.grid(alpha=.25)
    save(fig, out, "physics-12")

    fig, ax = plt.subplots(figsize=(10, 3.05))
    fig.subplots_adjust(left=.04, right=.96, top=.96, bottom=.06)
    diagram(ax, 11, 4.1)
    for center, piston, title in [(2.65, 1.51, "初态：3.00 L"), (8.35, 2.56, "刚到挡块：4.00 L")]:
        left, right = center-.96, center+.96
        ax.add_patch(Rectangle((left, .70), right-left, piston-.70, fc=LIGHT, ec="none"))
        ax.plot([left, left, right, right], [3.64, .70, .70, 3.64], color=INK, lw=2)
        ax.add_patch(Rectangle((left, piston), right-left, .16, fc=MUTED, ec=INK))
        for start, end in [(left, left+.30), (right-.30, right)]:
            line(ax, start, 2.72, end, 2.72, lw=4)
        label(ax, center, .31, title, 13)
        label(ax, center, 3.52, "大气")
    line(ax, 4.25, 2.94, 3.61, 2.72)
    label(ax, 4.73, 3.08, "挡块")
    arrow(ax, 5.05, 1.73, 6.65, 1.73)
    save(fig, out, "physics-13")

    fig, ax = plt.subplots(figsize=(10.5, 2.65))
    fig.subplots_adjust(left=.04, right=.96, top=.95, bottom=.10)
    diagram(ax, 12, 3.6)
    line(ax, .47, 1.25, 11.51, 1.25, lw=2)
    for x in np.linspace(5.3, 11.4, 21):
        line(ax, x-.16, .99, x, 1.25, lw=.8)
    for x, name in [(1.7, "A"), (5.06, "B")]:
        ax.add_patch(Circle((x, 1.63), .38, fc=LIGHT, ec=INK, lw=1.4))
        label(ax, x, 1.63, name)
    arrow(ax, 2.13, 2.35, 3.82, 2.35)
    label(ax, 2.96, 2.68, "$v_0$")
    label(ax, 5.06, .85, "O")
    label(ax, 2.85, .49, "光滑段")
    label(ax, 8.53, .49, "粗糙段")
    ax.plot(np.linspace(5.06, 11.3, 20), [1.72]+[1.72+(-1)**i*.29 for i in range(18)]+[1.72],
            color=INK, lw=1.45, zorder=0)
    line(ax, 11.3, 1.25, 11.3, 2.59, lw=3)
    save(fig, out, "physics-14")

    fig, ax = plt.subplots(figsize=(10.7, 3.68))
    fig.subplots_adjust(left=.03, right=.97, top=.96, bottom=.04)
    diagram(ax, 12, 4.5)
    ax.add_patch(Rectangle((2.1, .37), 3.7, 3.77, fc="#f1f4f6", ec="none"))
    ax.add_patch(Rectangle((5.8, .37), 3.7, 3.77, fc="#fbfcfc", ec="none"))
    for x in (5.8, 9.5):
        line(ax, x, .35, x, 4.13, ls="--", lw=1)
    arrow(ax, .53, 2.86, 11.13, 2.86)
    arrow(ax, 2.1, .38, 2.1, 4.30)
    label(ax, 11.39, 2.86, "$x$")
    label(ax, 1.87, 4.25, "$y$")
    label(ax, 1.85, 2.59, "O")
    label(ax, 5.99, 3.11, "$L$")
    label(ax, 9.66, 3.12, "$2L$")
    ax.plot(2.1, 2.86, "o", ms=4, color=INK)
    arrow(ax, 2.10, 2.86, 3.28, 2.86)
    label(ax, 2.71, 3.18, "$v$")
    for x in (3.15, 4.68):
        for y in (1.15, 2.12):
            label(ax, x, y, "⊙", 20)
    label(ax, 3.97, 3.68, "磁场  $B$")
    label(ax, 7.64, 3.68, "电场  $E$")
    for y in (1.15, 2.12):
        arrow(ax, 8.45, y, 6.84, y)
    line(ax, 9.5, 1.03, 9.5, 2.86, lw=5)
    line(ax, 9.39, 1.03, 9.61, 1.03)
    label(ax, 9.80, .99, "$-L$")
    label(ax, 10.38, 1.86, "探测片")
    save(fig, out, "physics-15")


def chemistry(out):
    fig, ax = plt.subplots(figsize=(11, 3.85))
    fig.subplots_adjust(left=.02, right=.98, top=.98, bottom=.07)
    diagram(ax, 15, 5)
    centers = [1.10, 4.20, 7.00, 9.70, 12.48]
    y = 3.60
    for x, text in zip(centers, ["炉尘", "浸出液", "除铁滤液", "除铜滤液", "锌 / 电解液"]):
        box(ax, x, y, text)
    for x1, x2, text in zip(centers, centers[1:], ["酸浸、过滤", "氧化、调 pH", "置换、过滤", "电解"]):
        arrow(ax, x1+.80, y, x2-.91, y)
        label(ax, (x1+x2)/2, y+.63, text, 13.5)
    for x, name in [(2.64, "浸出渣"), (5.60, "铁渣"), (8.35, "铜")]:
        arrow(ax, x, y-.17, x, y-1.10)
        label(ax, x, y-1.42, name, 13)
    line(ax, 12.48, y-.29, 12.48, .85)
    line(ax, 12.48, .85, 1.32, .85)
    arrow(ax, 1.32, .85, 1.32, y-.34)
    label(ax, 7.1, .40, "收集电解液，返回酸浸", 14)
    save(fig, out, "chemistry-15")

    fig, (ax, data) = plt.subplots(1, 2, figsize=(11.25, 3.6), gridspec_kw={"width_ratios": [1, 1]})
    fig.subplots_adjust(left=.03, right=.98, top=.95, bottom=.08, wspace=.08)
    diagram(ax, 11, 5)
    for y, name, text in [(3.65, "甲", "pH 约 10，直接滴定"), (1.55, "乙", "pH 约 12，过滤、洗涤")]:
        label(ax, .60, y, name, 14)
        box(ax, 4.08, y, text)
        arrow(ax, 6.46, y, 7.43, y)
        label(ax, 9.20, y, "总量" if name == "甲" else "滴定滤液和洗液", 12)
    table(data, [["流程", "样品耗量 / mL", "空白耗量 / mL"],
                 ["甲", "13.80", "0.30"], ["乙", "8.60", "0.10"]], [.19, .405, .405])
    save(fig, out, "chemistry-16")

    fig, (ax, selectivity) = plt.subplots(1, 2, figsize=(10.7, 3.80))
    fig.subplots_adjust(left=.105, right=.975, top=.91, bottom=.21, wspace=.38)
    pressure = np.linspace(50, 400, 300)
    for a, style, name in [(.1681, "--", "$T_1$"), (.5625, "-", "$T_2$")]:
        ax.plot(pressure, 100*np.sqrt(a/(pressure/100+a)), style, color=INK, lw=1.7, label=name)
    ax.scatter([100], [60], c=INK, s=22, zorder=4)
    ax.annotate("60.0%", (100, 60), xytext=(8, 7), textcoords="offset points")
    ax.set(xlabel="总压 / kPa", ylabel="乙醇平衡转化率 / %", xticks=[50, 100, 200, 300, 400],
           yticks=[20, 30, 40, 50, 60, 70], ylim=(16, 78))
    ax.legend(loc="upper right")
    ax.grid(alpha=.25)
    for s, style, name in [(25/41, "--", "$T_1$"), (2/3, "-", "$T_2$")]:
        selectivity.plot(pressure, 100*np.full_like(pressure, s), style, color=INK, lw=1.7, label=name)
    selectivity.scatter([100], [200/3], c=INK, s=22, zorder=4)
    selectivity.annotate("$S=2/3$", (100, 200/3), xytext=(11, 6), textcoords="offset points")
    selectivity.set(xlabel="总压 / kPa", ylabel="乙醛选择性 / %", xticks=[50, 100, 200, 300, 400],
                    yticks=[58, 61, 64, 67, 70], ylim=(57.5, 71))
    selectivity.legend(loc="lower right")
    selectivity.grid(alpha=.25)
    save(fig, out, "chemistry-17")

    # A para-disubstituted benzene with three alternating double bonds.
    def aromatic(ax, x, y, left, right):
        theta = np.arange(7) * np.pi/3
        coords = np.column_stack([x+.48*np.cos(theta), y+.48*np.sin(theta)])
        ax.plot(coords[:, 0], coords[:, 1], color=INK, lw=1.45)
        for i in (0, 2, 4):
            a, b = coords[i:i+2]
            a, b = .79*a+.21*np.array([x, y]), .79*b+.21*np.array([x, y])
            line(ax, a[0], a[1], b[0], b[1], lw=1)
        line(ax, x-.75, y, x-.48, y)
        line(ax, x+.48, y, x+.75, y)
        label(ax, x-.80, y, left, 12, ha="right")
        label(ax, x+.80, y, right, 12, ha="left")

    fig, ax = plt.subplots(figsize=(11.2, 3.85))
    fig.subplots_adjust(left=.012, right=.988, top=.97, bottom=.035)
    diagram(ax, 13.5, 4.6)
    aromatic(ax, 1.68, 3.18, "HO", "CHO")
    label(ax, 1.68, 2.48, "A")
    arrow(ax, 3.23, 3.18, 5.10, 3.18)
    label(ax, 4.18, 3.63, "乙二醇、酸催化", 11)
    aromatic(ax, 6.40, 3.18, "HO", "R")
    label(ax, 6.40, 2.48, "B")
    arrow(ax, 7.55, 3.18, 11.79, 3.18)
    label(ax, 9.68, 3.65, r"成酚盐，再加 $\mathrm{BrCH_2COOC_2H_5}$", 11)
    label(ax, 12.15, 3.18, "C", 15)
    arrow(ax, 12.15, 2.84, 12.15, 1.34)
    label(ax, 11.95, 2.02, "NaOH 水溶液，加热", 10.5, ha="right")
    label(ax, 12.15, 1.02, "D", 15)
    arrow(ax, 11.67, 1.02, 8.54, 1.02)
    label(ax, 10.07, 1.48, "酸化、缩醛水解", 10.5)
    aromatic(ax, 6.52, 1.02, r"$\mathrm{HOOCCH_2O}$", "CHO")
    label(ax, 6.52, .33, "E")
    label(ax, .25, 1.60, "R 为环缩醛基：", 10.5, ha="left")
    # The left-hand bond is the connection to the benzene ring.
    line(ax, .54, .85, 1.02, .85)
    label(ax, 1.22, .85, "CH", 11)
    for y in (.48, 1.22):
        line(ax, 1.44, .85, 1.73, y)
        label(ax, 1.86, y, "O", 11)
        line(ax, 2.00, y, 2.27, y)
        label(ax, 2.54, y, r"$\mathrm{CH_2}$", 11)
    line(ax, 2.54, .63, 2.54, 1.07)
    save(fig, out, "chemistry-18")


def biology(out):
    fig, ax = plt.subplots(figsize=(9.8, 3.72))
    fig.subplots_adjust(left=.18, right=.97, top=.92, bottom=.20)
    light = [0, 50, 100, 200, 400]
    ax.plot(light, [-3, -1, 0, 5, 8], "o-", color=INK, lw=1.65, label="甲")
    ax.plot(light, [-2, 0, 3, 5, 5], "s--", color=MUTED, lw=1.7, mfc="white", label="乙")
    ax.axhline(0, color=INK, linewidth=.8)
    ax.set(xlabel="光强（μmol 光子·m⁻²·s⁻¹）", ylabel="净 CO₂ 吸收速率\n（μmol CO₂·m⁻²·s⁻¹）",
           xticks=light, yticks=[-3, -2, -1, 0, 3, 5, 8], xlim=(-12, 421), ylim=(-3.65, 9.35))
    ax.legend(loc="lower right")
    ax.grid(alpha=.22)
    save(fig, out, "biology-17")

    fig, ax = plt.subplots(figsize=(10, 3.45))
    fig.subplots_adjust(left=.14, right=.97, top=.92, bottom=.23)
    bars = ax.bar([0, 1, 2, 3], [100, 58, 98, 96], .46, edgecolor=INK, facecolor=LIGHT)
    ax.bar_label(bars, padding=4)
    ax.set(ylabel="M 分泌相对量", ylim=(0, 119), yticks=[0, 25, 50, 75, 100],
           xticks=[0, 1, 2, 3], xticklabels=["甲：溶剂", "乙：激素 C", "丙：阻断剂 I", "丁：C 和 I"])
    ax.set_axisbelow(True)
    ax.grid(axis="y", alpha=.22)
    save(fig, out, "biology-18")

    fig, (ax, data) = plt.subplots(1, 2, figsize=(10.7, 3.25), gridspec_kw={"width_ratios": [1, 1.16]})
    fig.subplots_adjust(left=.035, right=.98, wspace=.10)
    diagram(ax, 10, 4.1)
    for x, width, name, color in [(2, 2.10, "岸边带", "#d2e3eb"), (4.1, 4.9, "内侧带", "#f2f6f8")]:
        ax.add_patch(Rectangle((x, 1.19), width, 1.96, ec=MUTED, fc=color))
        label(ax, x+width/2, 2.17, name, 11)
    label(ax, 1.0, 2.17, "水面", 12)
    table(data, [["样带", "面积占比", "平均密度 /（株·m⁻²）"],
                 ["岸边带", "30%", "12"], ["内侧带", "70%", "4"]], [.23, .27, .50])
    save(fig, out, "biology-19")

    fig, ax = plt.subplots(figsize=(9.6, 3.15))
    fig.subplots_adjust(left=.14, right=.97, top=.90, bottom=.20)
    bars = ax.bar([0, 1, 2, 3], [9, 3, 3, 1], .46, edgecolor=INK, facecolor=LIGHT)
    bars[3].set_hatch("//")
    ax.bar_label(bars, padding=4)
    ax.set(ylabel="比例份数", ylim=(0, 10.5), yticks=[0, 3, 6, 9], xticks=[0, 1, 2, 3],
           xticklabels=["紫色", "黄色", "白色", "败育"])
    ax.set_axisbelow(True)
    ax.grid(axis="y", alpha=.22)
    save(fig, out, "biology-20")

    fig, (ax, data) = plt.subplots(1, 2, figsize=(10.9, 3.50), gridspec_kw={"width_ratios": [1, 1.38]})
    fig.subplots_adjust(left=.027, right=.98, top=.94, bottom=.09, wspace=.10)
    diagram(ax, 9, 5)
    ax.add_patch(Rectangle((.65, 1.3), 3.47, 1.31, fc=LIGHT, ec="none"))
    ax.plot([.65, .65, 4.12, 4.12], [3.85, 1.3, 1.3, 3.85], color=INK, lw=1.6)
    for x, y in [(1.15, 1.63), (1.68, 2.07), (2.22, 1.64), (2.85, 2.18), (3.58, 1.69)]:
        ax.add_patch(Circle((x, y), .15, ec=INK, fc="white", lw=1.2))
    label(ax, 2.38, 3.20, "底物与颗粒")
    arrow(ax, 4.42, 2.35, 5.73, 2.35)
    ax.plot([5.86, 6.22, 7.60, 7.96], [2.75, 1.93, 1.93, 2.75], color=INK, lw=1.55)
    ax.scatter([6.54, 6.75, 6.96, 7.17, 7.38], [2.02]*5, color=MUTED, s=12)
    label(ax, 6.92, 3.12, "筛网")
    label(ax, 6.93, 1.36, "回收颗粒 / 留取滤液", 10)
    table(data, [["组别", "第 1 轮 / mmol", "第 3 轮 / mmol"],
                 ["游离酶", "8.4", "—"],
                 ["小颗粒", "8.0", "7.6"], ["大颗粒", "5.0", "4.9"]], [.27, .365, .365])
    data.text(.5, .06, "每轮液体中葡萄糖增加量（— 表示未测）", ha="center", transform=data.transAxes, color=INK)
    save(fig, out, "biology-21")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    workspace = parser.parse_args().workspace
    for draw in (physics, chemistry, biology):
        destination = workspace / draw.__name__ / "figures"
        destination.mkdir(parents=True, exist_ok=True)
        draw(destination)
