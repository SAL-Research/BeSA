#!/usr/bin/env python3
"""
plot_simpoints.py -- muted, publication-oriented restyle.

Figures: cluster_weights_bar, cluster_pareto, simpoint_timeline
(PNG @300dpi + vector PDF).
"""

import argparse, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

# --- project palette (validated pair: ΔE 20.6/14.0 deutan/tritan) -------------
BASE   = "#54A767"   # regular bars
ACCENT = "#7A63B8"   # dominant cluster (nudged from requested #8071B2, which reads
                      # near-gray at OKLCH chroma 0.099 -- below the 0.10 identity floor)
INK    = "#2C3E50"   # axes, text, cumulative line
GRID   = "#E7E6E1"   # soft warm gray gridlines

plt.rcParams.update({
    "font.family": "serif",              # blends into a LaTeX document
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "xtick.labelsize": 8,
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

COLW = 3.4


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


def _colors(d):
    return [ACCENT if i == 0 else BASE for i in range(len(d["cluster"]))]


def _save(fig, outdir, name):
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(outdir, f"{name}.{ext}"), dpi=300)
    plt.close(fig)


def fig_bar(d, outdir):
    fig, ax = plt.subplots(figsize=(COLW, 2.5))
    x = np.arange(len(d["cluster"])); pct = 100 * d["weight"]
    ax.bar(x, pct, color=_colors(d), edgecolor="none")
    ax.set_xticks(x); ax.set_xticklabels([str(int(c)) for c in d["cluster"]])
    ax.set_xlabel("SimPoint cluster (sorted by weight)")
    ax.set_ylabel("Share of execution (%)")
    ax.set_ylim(0, max(pct) * 1.18)
    ax.yaxis.grid(True, linewidth=0.6, color=GRID); ax.set_axisbelow(True)
    ax.annotate(f"{pct[0]:.1f}%", xy=(0, pct[0]),
                xytext=(0, pct[0] + max(pct) * 0.03),
                ha="center", va="bottom", fontsize=8.5, fontweight="bold")
    _save(fig, outdir, "cluster_weights_bar")


def fig_pareto(d, outdir):
    fig, ax = plt.subplots(figsize=(COLW, 2.6))
    x = np.arange(len(d["cluster"])); pct = 100 * d["weight"]
    cum = 100 * np.cumsum(d["weight"])
    ax.bar(x, pct, color=_colors(d), edgecolor="none", zorder=2)
    ax.set_xticks(x); ax.set_xticklabels([str(int(c)) for c in d["cluster"]])
    ax.set_xlabel("SimPoint cluster (sorted by weight)")
    ax.set_ylabel("Share of execution (%)")
    ax.set_ylim(0, max(pct) * 1.18)
    ax.yaxis.grid(True, linewidth=0.6, color=GRID); ax.set_axisbelow(True)
    ax2 = ax.twinx(); ax2.spines["top"].set_visible(False)
    ax2.plot(x, cum, color=INK, marker="o", markersize=3.3, linewidth=1.2,
             markerfacecolor="white", markeredgecolor=INK, zorder=3)
    ax2.set_ylabel("Cumulative coverage (%)")
    ax2.set_ylim(0, 105)
    ax2.yaxis.set_major_formatter(PercentFormatter(decimals=0))
    k = min(3, len(x) - 1)
    ax2.annotate(f"top {k+1} = {cum[k]:.0f}%", xy=(x[k], cum[k]),
                 xytext=(x[k] + 0.4, cum[k] - 15), fontsize=8,
                 arrowprops=dict(arrowstyle="-", color=INK, linewidth=0.6))
    _save(fig, outdir, "cluster_pareto")


def _scale(v):
    for s, u in [(1e12, "trillions"), (1e9, "billions"),
                 (1e6, "millions"), (1e3, "thousands")]:
        if v >= s:
            return s, u
    return 1.0, "count"


def fig_timeline(d, outdir, interval_size=100_000_000):
    fig, ax = plt.subplots(figsize=(COLW * 1.35, 2.3))
    instr = d["rep_interval"] * interval_size
    scale, unit = _scale(instr.max()); xi = instr / scale
    pct = 100 * d["weight"]; colors = _colors(d)
    ax.vlines(xi, 0, pct, color=colors, linewidth=1.1, alpha=0.8, zorder=1)
    ax.scatter(xi, pct, s=30 + 900 * d["weight"], c=colors,
               edgecolor="white", linewidth=0.5, zorder=2)
    ax.set_xlabel(f"Instructions executed ({unit}, execution order)")
    ax.set_ylabel("Cluster weight (%)")
    ax.set_ylim(0, max(pct) * 1.18); ax.set_xlim(0, xi.max() * 1.05)
    ax.yaxis.grid(True, linewidth=0.6, color=GRID); ax.set_axisbelow(True)
    ax.annotate(f"cluster {int(d['cluster'][0])}\n{pct[0]:.1f}%",
                xy=(xi[0], pct[0]),
                xytext=(xi[0], pct[0] - max(pct) * 0.28),
                ha="center", fontsize=8, fontweight="bold")
    _save(fig, outdir, "simpoint_timeline")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", default="simpoints_weights.txt")
    ap.add_argument("--simpoints", default="simpoints.out")
    ap.add_argument("--outdir", default="figures")
    ap.add_argument("--interval-size", type=int, default=100_000_000)
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    d = load_data(a.weights, a.simpoints)
    fig_bar(d, a.outdir); fig_pareto(d, a.outdir)
    fig_timeline(d, a.outdir, a.interval_size)
    print("done")


if __name__ == "__main__":
    main()
