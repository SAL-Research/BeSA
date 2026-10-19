"""
Aggregate weighted metrics from SimPoint detailed simulation runs.

Computes metrics for:
  - Roofline analysis (Arithmetic Intensity vs Performance)
  - DAMOV-methodology characterization (LFMR, LLC MPKI, AI)

Auto-discovers SimPoints from detail_sp* directories, or reads from
$WORK_DIR/sampling/simpoints/ files.

Usage:
    python3 analysis/aggregate_metrics.py [m5out_dir]
    python3 analysis/aggregate_metrics.py [m5out_dir] --discover
    python3 analysis/aggregate_metrics.py [m5out_dir] --csv
"""
import glob
import json
import os
import re
import sys

CACHE_LINE_BYTES = 64
CLOCK_FREQ_GHZ = float(os.environ.get("GEM5_CLK_FREQ_GHZ", "3.0"))

STAT_PATTERNS = {
    "numCycles": r"board\.processor\.cores0\.core\.numCycles\s+(\d+)",
    "simInsts": r"simInsts\s+(\d+)",
    "simOps": r"simOps\s+(\d+)",
    "cpi": r"board\.processor\.cores0\.core\.cpi\s+([\d.]+)",
    "ipc": r"board\.processor\.cores0\.core\.ipc\s+([\d.]+)",
    "l1d_hits": r"board\.cache_hierarchy\.l1dcaches0\.overallHits::total\s+(\d+)",
    "l1d_misses": r"board\.cache_hierarchy\.l1dcaches0\.overallMisses::total\s+(\d+)",
    "l1d_accesses": r"board\.cache_hierarchy\.l1dcaches0\.overallAccesses::total\s+(\d+)",
    "l1i_hits": r"board\.cache_hierarchy\.l1icaches0\.overallHits::total\s+(\d+)",
    "l1i_misses": r"board\.cache_hierarchy\.l1icaches0\.overallMisses::total\s+(\d+)",
    "l1i_accesses": r"board\.cache_hierarchy\.l1icaches0\.overallAccesses::total\s+(\d+)",
    "l2_hits": r"board\.cache_hierarchy\.l2caches0\.overallHits::total\s+(\d+)",
    "l2_misses": r"board\.cache_hierarchy\.l2caches0\.overallMisses::total\s+(\d+)",
    "l2_accesses": r"board\.cache_hierarchy\.l2caches0\.overallAccesses::total\s+(\d+)",
    "dram_bytes_read": r"board\.memory\.mem_ctrl\.dram\.bytesRead::total\s+(\d+)",
    "dram_bytes_written": r"board\.memory\.mem_ctrl\.dram\.bytesWritten::total\s+(\d+)",
    "dram_read_reqs": r"board\.memory\.mem_ctrl\.dram\.readReqs\s+(\d+)",
    "dram_write_reqs": r"board\.memory\.mem_ctrl\.dram\.writeReqs\s+(\d+)",
    "dram_read_bursts": r"board\.memory\.mem_ctrl\.dram\.readBursts\s+(\d+)",
    "dram_write_bursts": r"board\.memory\.mem_ctrl\.dram\.writeBursts\s+(\d+)",
}

OP_TYPES = [
    "IntAlu", "IntMult", "IntDiv",
    "FloatAdd", "FloatCmp", "FloatCvt", "FloatMult", "FloatMultAcc",
    "FloatDiv", "FloatMisc", "FloatSqrt",
    "SimdAdd", "SimdAddAcc", "SimdAlu", "SimdCmp", "SimdCvt", "SimdMisc",
    "SimdMult", "SimdMultAcc", "SimdShift", "SimdShiftAcc",
    "SimdFloatAdd", "SimdFloatAlu", "SimdFloatCmp", "SimdFloatCvt",
    "SimdFloatDiv", "SimdFloatMisc", "SimdFloatMult", "SimdFloatMultAcc",
    "SimdFloatSqrt",
    "MemRead", "MemWrite", "FloatMemRead", "FloatMemWrite",
    "IprAccess", "InstPrefetch",
]
for op in OP_TYPES:
    STAT_PATTERNS[f"op_{op}"] = (
        r"board\.processor\.cores0\.core\.commit\.committedInstType_0::"
        + re.escape(op) + r"\s+(\d+)"
    )

COMPILED = {name: re.compile(pat) for name, pat in STAT_PATTERNS.items()}


def parse_stats(path):
    m = {}
    with open(path) as f:
        for line in f:
            for name, pat in COMPILED.items():
                hit = pat.search(line)
                if hit:
                    v = hit.group(1)
                    m[name] = float(v) if "." in v else int(v)
    return m


def discover_stats(path):
    kw = ["dram", "bytes", "mem_ctrl", "committedinsttype", "overall",
          "miss", "hit", "access", "l1d", "l1i", "l2"]
    out = []
    with open(path) as f:
        for line in f:
            if any(k in line.lower() for k in kw):
                out.append(line.rstrip())
    return out


def discover_simpoints(base_dir):
    """Auto-discover SimPoints from detail_sp* directory names + weights file."""
    work_dir = os.environ.get("WORK_DIR", os.path.dirname(base_dir))
    bench = os.environ.get("BENCHMARK_NAME", "")

    weights = {}
    weights_file = os.path.join(work_dir, "sampling", "simpoints",
                                f"{bench}.weights" if bench else "*.weights")
    for wf in glob.glob(weights_file) or glob.glob(
            os.path.join(work_dir, "sampling", "simpoints", "*.weights")):
        with open(wf) as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    weights[int(parts[1])] = float(parts[0])
        break

    orig_indices = {}
    orig_file = os.path.join(work_dir, "sampling", "simpoints",
                             f"{bench}_original.simpts" if bench else "*_original.simpts")
    for of in glob.glob(orig_file) or glob.glob(
            os.path.join(work_dir, "sampling", "simpoints", "*_original.simpts")):
        with open(of) as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    orig_indices[int(parts[1])] = int(parts[0])
        break

    # If files found, build from them
    if orig_indices and weights:
        sps = []
        for i, cluster in enumerate(sorted(orig_indices.keys())):
            sps.append((i, orig_indices[cluster], weights.get(cluster, 0.0)))
        return sorted(sps, key=lambda x: x[0])

    # Fallback: discover from directory names
    pattern = os.path.join(base_dir, "detail_sp*_idx*")
    dirs = sorted(glob.glob(pattern))
    sps = []
    for d in dirs:
        m = re.search(r'detail_sp(\d+)_idx(\d+)', os.path.basename(d))
        if m:
            sp_num, sp_idx = int(m.group(1)), int(m.group(2))
            w = weights.get(sp_num, 1.0 / max(len(dirs), 1))
            sps.append((sp_num, sp_idx, w))
    return sps


def compute_derived(m):
    d = {}
    insts = m.get("simInsts", 0)
    ops = m.get("simOps", 0)
    cycles = m.get("numCycles", 0)
    insts_k = insts / 1000.0 if insts > 0 else 1.0

    d["cpi"] = m.get("cpi", cycles / insts if insts > 0 else 0.0)
    d["ipc"] = m.get("ipc", insts / cycles if cycles > 0 else 0.0)
    d["l1d_mpki"] = m.get("l1d_misses", 0) / insts_k
    d["l1i_mpki"] = m.get("l1i_misses", 0) / insts_k
    d["l2_mpki"] = m.get("l2_misses", 0) / insts_k

    l1d_acc = m.get("l1d_accesses", 0)
    l1i_acc = m.get("l1i_accesses", 0)
    l2_acc = m.get("l2_accesses", 0)
    d["l1d_hit_rate"] = m.get("l1d_hits", 0) / l1d_acc if l1d_acc > 0 else 0.0
    d["l1i_hit_rate"] = m.get("l1i_hits", 0) / l1i_acc if l1i_acc > 0 else 0.0
    d["l2_hit_rate"] = m.get("l2_hits", 0) / l2_acc if l2_acc > 0 else 0.0

    l1_misses = m.get("l1d_misses", 0) + m.get("l1i_misses", 0)
    l2_misses = m.get("l2_misses", 0)
    d["lfmr"] = l2_misses / l1_misses if l1_misses > 0 else 0.0
    d["ai_damov"] = ops / l1d_acc if l1d_acc > 0 else 0.0

    dram_bytes = m.get("dram_bytes_read", 0) + m.get("dram_bytes_written", 0)
    if dram_bytes == 0:
        dr = m.get("dram_read_reqs", m.get("dram_read_bursts", 0))
        dw = m.get("dram_write_reqs", m.get("dram_write_bursts", 0))
        dram_bytes = (dr + dw) * CACHE_LINE_BYTES
    d["dram_bytes_total"] = dram_bytes
    d["ai_roofline"] = ops / dram_bytes if dram_bytes > 0 else float("inf")

    if cycles > 0:
        secs = cycles / (CLOCK_FREQ_GHZ * 1e9)
        d["gops"] = ops / 1e9 / secs
        d["dram_bw_gbs"] = dram_bytes / 1e9 / secs if dram_bytes > 0 else 0.0
    else:
        d["gops"] = 0.0
        d["dram_bw_gbs"] = 0.0

    float_ops = sum(m.get(k, 0) for k in m if k.startswith("op_Float") and "Mem" not in k)
    simd_ops = sum(m.get(k, 0) for k in m if k.startswith("op_Simd"))
    d["float_ops"] = float_ops
    d["simd_ops"] = simd_ops
    d["int_alu_ops"] = m.get("op_IntAlu", 0)
    d["int_mult_ops"] = m.get("op_IntMult", 0)
    d["int_div_ops"] = m.get("op_IntDiv", 0)
    d["mem_read_ops"] = m.get("op_MemRead", 0) + m.get("op_FloatMemRead", 0)
    d["mem_write_ops"] = m.get("op_MemWrite", 0) + m.get("op_FloatMemWrite", 0)
    d["compute_ops"] = d["int_alu_ops"] + d["int_mult_ops"] + d["int_div_ops"] + float_ops + simd_ops
    d["ai_roofline_fp"] = (float_ops + simd_ops) / dram_bytes if dram_bytes > 0 else float("inf")
    return d


def damov_classify(llc_mpki, lfmr, ai):
    if llc_mpki >= 11.0:
        if lfmr >= 0.56:
            return ("1a", "DRAM BW-bound", "High LLC misses from L1 -> BW limited")
        return ("1b", "DRAM latency-bound", "High LLC misses filtered by L1/L2 -> latency limited")
    if lfmr >= 0.56:
        return ("1c", "L1/L2 capacity", "Low LLC MPKI, high LFMR -> L1/L2 pressure")
    if ai <= 8.5:
        return ("2a", "LLC contention", "Low MPKI, low LFMR, low AI -> streaming/contention")
    return ("2c", "Compute-bound", "Low MPKI, low LFMR, high AI -> compute limited")


def main():
    args_list = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = set(a for a in sys.argv[1:] if a.startswith("--"))
    base_dir = args_list[0] if args_list else "m5out"

    SIMPOINTS = discover_simpoints(base_dir)
    if not SIMPOINTS:
        print("ERROR: No SimPoints found. Check WORK_DIR and sampling/simpoints/.", file=sys.stderr)
        sys.exit(1)

    if "--discover" in flags:
        for sp_num, sp_idx, _ in SIMPOINTS:
            stats_path = os.path.join(base_dir, f"detail_sp{sp_num:02d}_idx{sp_idx}", "stats.txt")
            if os.path.exists(stats_path):
                print(f"\n=== SP{sp_num:02d} idx{sp_idx} ===")
                for line in discover_stats(stats_path):
                    print(f"  {line}")
                print("\n(showing first available SimPoint only)")
                break
        return

    results, total_weight = [], 0.0
    hdr = (f"{'SP':>3} {'Index':>6} {'Weight':>8} {'CPI':>8} {'IPC':>8} "
           f"{'L1D MPKI':>10} {'L1I MPKI':>10} {'LLC MPKI':>10} "
           f"{'LFMR':>8} {'AI(DAMOV)':>10} {'AI(Roof)':>10} "
           f"{'GOPS/s':>8} {'Insts':>14}")

    do_csv = "--csv" in flags
    if not do_csv:
        print(hdr)
        print("-" * len(hdr))

    for sp_num, sp_idx, weight in SIMPOINTS:
        stats_path = os.path.join(base_dir, f"detail_sp{sp_num:02d}_idx{sp_idx}", "stats.txt")
        if not os.path.exists(stats_path):
            if not do_csv:
                print(f"{sp_num:>3} {sp_idx:>6} {weight:>8.5f}  ** MISSING **")
            continue

        m = parse_stats(stats_path)
        d = compute_derived(m)
        insts = m.get("simInsts", 0)

        if not do_csv:
            air = f"{d['ai_roofline']:.4f}" if d["ai_roofline"] != float("inf") else "inf"
            print(f"{sp_num:>3} {sp_idx:>6} {weight:>8.5f} {d['cpi']:>8.4f} "
                  f"{d['ipc']:>8.4f} {d['l1d_mpki']:>10.4f} {d['l1i_mpki']:>10.4f} "
                  f"{d['l2_mpki']:>10.4f} {d['lfmr']:>8.4f} {d['ai_damov']:>10.4f} "
                  f"{air:>10} {d['gops']:>8.3f} {insts:>14,}")

        results.append({"sp_num": sp_num, "sp_idx": sp_idx, "weight": weight,
                        "insts": insts, **d, **m})
        total_weight += weight

    if not results:
        print("\nNo results found.")
        return

    if not do_csv:
        print("-" * len(hdr))

    avg_keys = ["cpi", "ipc", "l1d_mpki", "l1i_mpki", "l2_mpki",
                "lfmr", "ai_damov", "ai_roofline", "gops",
                "l1d_hit_rate", "l1i_hit_rate", "l2_hit_rate", "dram_bw_gbs"]
    weighted = {}
    for k in avg_keys:
        vs = [(r["weight"], r.get(k, 0)) for r in results if r.get(k, 0) != float("inf")]
        ws = sum(w for w, _ in vs)
        weighted[k] = sum(w * v for w, v in vs) / ws if ws > 0 else 0.0

    sum_keys = ["float_ops", "simd_ops", "int_alu_ops", "int_mult_ops",
                "int_div_ops", "mem_read_ops", "mem_write_ops", "compute_ops",
                "dram_bytes_total"]
    w_sums = {k: sum(r["weight"] * r.get(k, 0) for r in results) / total_weight for k in sum_keys}

    cls_id, cls_name, cls_desc = damov_classify(weighted["l2_mpki"], weighted["lfmr"], weighted["ai_damov"])

    if do_csv:
        fields = ["sp_num", "sp_idx", "weight", "insts", "cpi", "ipc",
                  "l1d_mpki", "l1i_mpki", "l2_mpki", "lfmr", "ai_damov",
                  "ai_roofline", "gops", "l1d_hit_rate", "l1i_hit_rate",
                  "l2_hit_rate", "dram_bw_gbs", "dram_bytes_total",
                  "float_ops", "simd_ops", "compute_ops", "mem_read_ops", "mem_write_ops"]
        print(",".join(fields))
        for r in results:
            row = []
            for f in fields:
                v = r.get(f, 0)
                row.append("inf" if isinstance(v, float) and v == float("inf")
                           else f"{v:.6f}" if isinstance(v, float) else str(v))
            print(",".join(row))
        return

    print(f"\n{'='*60}")
    print(f"  WEIGHTED AVERAGES (total weight = {total_weight:.6f})")
    print(f"{'='*60}")
    print(f"\n  --- Core Performance ---")
    print(f"  CPI:                {weighted['cpi']:.4f}")
    print(f"  IPC:                {weighted['ipc']:.4f}")
    print(f"  Throughput:         {weighted['gops']:.3f} GOPS/s")
    print(f"\n  --- Cache Miss Rates (MPKI) ---")
    print(f"  L1D MPKI:           {weighted['l1d_mpki']:.4f}")
    print(f"  L1I MPKI:           {weighted['l1i_mpki']:.4f}")
    print(f"  LLC MPKI (L2):      {weighted['l2_mpki']:.4f}")
    print(f"\n  --- Cache Hit Rates ---")
    print(f"  L1D hit rate:       {weighted['l1d_hit_rate']*100:.2f}%")
    print(f"  L1I hit rate:       {weighted['l1i_hit_rate']*100:.2f}%")
    print(f"  L2  hit rate:       {weighted['l2_hit_rate']*100:.2f}%")
    print(f"\n  --- DAMOV Metrics ---")
    print(f"  LFMR (LLC/L1):      {weighted['lfmr']:.4f}  (threshold: 0.56)")
    print(f"  AI (ops/L1 line):   {weighted['ai_damov']:.4f}  (threshold: 8.5)")
    print(f"  LLC MPKI:           {weighted['l2_mpki']:.4f}  (threshold: 11.0)")
    print(f"\n  --- DAMOV Classification ---")
    print(f"  Class:              {cls_id} - {cls_name}")
    print(f"  Description:        {cls_desc}")
    ai_r = weighted["ai_roofline"]
    print(f"\n  --- Roofline Analysis ---")
    print(f"  AI (ops/byte DRAM): {ai_r:.4f}" if ai_r != float("inf") else
          f"  AI (ops/byte DRAM): inf (no DRAM traffic)")
    print(f"  DRAM BW:            {weighted['dram_bw_gbs']:.3f} GB/s")
    print(f"\n  --- Instruction Mix (weighted per interval) ---")
    for label, key in [("Int ALU", "int_alu_ops"), ("Int Mult", "int_mult_ops"),
                       ("Int Div", "int_div_ops"), ("Float", "float_ops"),
                       ("SIMD", "simd_ops"), ("Mem Read", "mem_read_ops"),
                       ("Mem Write", "mem_write_ops"), ("Compute", "compute_ops")]:
        print(f"  {label + ':':20}{w_sums[key]:>14,.0f}")

    print(f"\n{'='*60}")
    print(f"  PER-SIMPOINT DAMOV CLASSIFICATION")
    print(f"{'='*60}")
    print(f"  {'SP':>3} {'Index':>6} {'Weight':>8} {'Class':>6} {'Name':<20} "
          f"{'LLC MPKI':>10} {'LFMR':>8} {'AI':>8}")
    print(f"  {'-'*80}")
    for r in results:
        cid, cname, _ = damov_classify(r["l2_mpki"], r["lfmr"], r["ai_damov"])
        print(f"  {r['sp_num']:>3} {r['sp_idx']:>6} {r['weight']:>8.5f} "
              f"{cid:>6} {cname:<20} {r['l2_mpki']:>10.4f} "
              f"{r['lfmr']:>8.4f} {r['ai_damov']:>8.4f}")

    json_path = os.path.join(base_dir, "simpoint_metrics.json")
    json_data = {
        "config": {"cache_line_bytes": CACHE_LINE_BYTES,
                    "clock_freq_ghz": CLOCK_FREQ_GHZ, "llc_level": "L2"},
        "weighted_averages": weighted, "weighted_sums": w_sums,
        "damov_classification": {"class_id": cls_id, "class_name": cls_name,
                                  "description": cls_desc,
                                  "thresholds": {"mpki": 11.0, "lfmr": 0.56, "ai": 8.5}},
        "per_simpoint": [{
            "sp_num": r["sp_num"], "sp_idx": r["sp_idx"], "weight": r["weight"],
            "insts": r["insts"], "cpi": r["cpi"], "ipc": r["ipc"],
            "l1d_mpki": r["l1d_mpki"], "l2_mpki": r["l2_mpki"], "lfmr": r["lfmr"],
            "ai_damov": r["ai_damov"], "gops": r["gops"],
            "ai_roofline": r["ai_roofline"] if r["ai_roofline"] != float("inf") else None,
            "damov_class": damov_classify(r["l2_mpki"], r["lfmr"], r["ai_damov"])[0],
            "float_ops": r["float_ops"], "simd_ops": r["simd_ops"],
            "compute_ops": r["compute_ops"],
        } for r in results],
    }
    with open(json_path, "w") as f:
        json.dump(json_data, f, indent=2)
    print(f"\nFull metrics written to {json_path}")


if __name__ == "__main__":
    main()
