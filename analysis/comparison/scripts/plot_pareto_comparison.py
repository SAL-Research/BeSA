#!/usr/bin/env python3
"""
plot_pareto_comparison.py -- two-panel SimPoint Pareto comparison across workloads.

"""

import argparse, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

BASE   = "#54A767"   # regular bars 
ACCENT = "#7A63B8"   # dominant cluster 
INK    = "#2C3E50"   # axes, text, cumulative line
GRID   = "#E7E6E1"   # soft warm gray gridlines

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 9,
    "axes.titlesize": 9.5,
    "axes.labelsize": 9,
    "xtick.labelsize": 7.5,
    "ytick.labelsize": 8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": INK,
    "axes.linewidth": 0.7,
    "xtick.color": INK, "ytick.color": INK,
    "text.color": INK, "axes.labelcolor": INK,
    "figure.dpi": 120,
    "savefig.bbox": "tight",
})


def load_data(weights_path, simpoints_path):
    w, rep = {}, {}
    for line in open(weights_path):
        if line.strip():
            val, cid = line.split(); w[int(cid)] = float(val)
    for line in open(simpoints_path):
        if line.strip():
            interval, cid = line.split(); rep[int(cid)] = int(interval)
    clusters = sorted(w)
    weights = np.array([w[c] for c in clusters], float)
    weights = weights / weights.sum()
    reps = np.array([rep.get(c, -1) for c in clusters], float)
    order = np.argsort(weights)[::-1]
    return {"cluster": np.array(clusters)[order],
            "weight": weights[order],
            "rep_interval": reps[order]}


def _panel(ax, ax2, d, title, ymax):
    x = np.arange(len(d["cluster"])); pct = 100 * d["weight"]
    cum = 100 * np.cumsum(d["weight"])
    colors = [ACCENT if i == 0 else BASE for i in range(len(x))]
    ax.bar(x, pct, color=colors, edgecolor="none", zorder=2)
    ax.set_xticks(x); ax.set_xticklabels([str(i + 1) for i in x])
    ax.set_xlabel("Cluster rank (sorted by weight)")
    ax.set_ylim(0, ymax)
    ax.yaxis.grid(True, linewidth=0.6, color=GRID); ax.set_axisbelow(True)
    ax.set_title(title, fontweight="bold")

    ax2.plot(x, cum, color=INK, marker="o", markersize=3.3, linewidth=1.2,
              markerfacecolor="white", markeredgecolor=INK, zorder=3)
    ax2.set_ylim(0, 105)
    ax2.spines["top"].set_visible(False)
    ax2.yaxis.set_major_formatter(PercentFormatter(decimals=0))

    k3 = min(2, len(x) - 1)
    ax.annotate(f"{pct[0]:.1f}%", xy=(0, pct[0]),
                xytext=(0, pct[0] + ymax * 0.03),
                ha="center", va="bottom", fontsize=8, fontweight="bold")
    ax2.annotate(f"top {k3 + 1} = {cum[k3]:.0f}%", xy=(x[k3], cum[k3]),
                 xytext=(x[k3] + 0.5, cum[k3] - 18), fontsize=7.5,
                 arrowprops=dict(arrowstyle="-", color=INK, linewidth=0.6))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epi-weights", required=True)
    ap.add_argument("--epi-simpoints", required=True)
    ap.add_argument("--epi-label", default="Epidemiology (200M agents, k=12)")
    ap.add_argument("--tumor-weights", required=True)
    ap.add_argument("--tumor-simpoints", required=True)
    ap.add_argument("--tumor-label", default="Tumor growth (800 iter, k=10)")
    ap.add_argument("--outdir", default="figures")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    d_epi = load_data(a.epi_weights, a.epi_simpoints)
    d_tum = load_data(a.tumor_weights, a.tumor_simpoints)
    ymax = 100 * max(d_epi["weight"].max(), d_tum["weight"].max()) * 1.2

    fig, axes = plt.subplots(1, 2, figsize=(6.8, 2.7), sharey=True)
    ax2_left = axes[0].twinx()
    ax2_right = axes[1].twinx()
    ax2_left.set_yticklabels([])

    _panel(axes[0], ax2_left, d_epi, a.epi_label, ymax)
    _panel(axes[1], ax2_right, d_tum, a.tumor_label, ymax)

    axes[0].set_ylabel("Share of execution (%)")
    ax2_right.set_ylabel("Cumulative coverage (%)")

    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(a.outdir, f"pareto_comparison.{ext}"), dpi=300)
    plt.close(fig)
    print("done")


if __name__ == "__main__":
    main()
