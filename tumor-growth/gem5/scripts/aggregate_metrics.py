"""
Aggregate weighted metrics from SimPoint detailed simulation runs.

Computes metrics for:
  - Roofline analysis (Arithmetic Intensity vs Performance)
  - DAMOV-methodology characterization (LFMR, LLC MPKI, AI)

Reads stats.txt from each detail_spNN_idxXXX output directory, extracts
per-core and cache/memory metrics, and computes weighted averages.

Usage:
    cd ~/tumor_gem5
    python3 scripts/aggregate_metrics.py [m5out]
    python3 scripts/aggregate_metrics.py [m5out] --discover   # dump matching stat names
    python3 scripts/aggregate_metrics.py [m5out] --csv        # CSV output
"""
import os
import re
import sys
import json

SIMPOINTS = [
    (0,  196,   0.00241799),
    (1,  250,   0.00237769),
    (2,  457,   0.01418550),
    (3,  479,   0.00656887),
    (4,  1393,  0.06717980),
    (5,  2588,  0.00342549),
    (6,  5275,  0.21890900),
    (7,  11764, 0.00205529),
    (8,  12158, 0.42528400),
    (9,  22871, 0.25759700),
]

CACHE_LINE_BYTES = 64
CLOCK_FREQ_GHZ = 3.0

STAT_PATTERNS = {
    "numCycles": r"board\.processor\.cores0\.core\.numCycles\s+(\d+)",
    "simInsts": r"simInsts\s+(\d+)",
    "simOps": r"simOps\s+(\d+)",
    "cpi": r"board\.processor\.cores0\.core\.cpi\s+([\d.]+)",
    "ipc": r"board\.processor\.cores0\.core\.ipc\s+([\d.]+)",

    # L1D cache
    "l1d_hits": r"board\.cache_hierarchy\.l1dcaches0\.overallHits::total\s+(\d+)",
    "l1d_misses": r"board\.cache_hierarchy\.l1dcaches0\.overallMisses::total\s+(\d+)",
    "l1d_accesses": r"board\.cache_hierarchy\.l1dcaches0\.overallAccesses::total\s+(\d+)",

    # L1I cache
    "l1i_hits": r"board\.cache_hierarchy\.l1icaches0\.overallHits::total\s+(\d+)",
    "l1i_misses": r"board\.cache_hierarchy\.l1icaches0\.overallMisses::total\s+(\d+)",
    "l1i_accesses": r"board\.cache_hierarchy\.l1icaches0\.overallAccesses::total\s+(\d+)",

    # L2 cache (our LLC since no L3)
    "l2_hits": r"board\.cache_hierarchy\.l2caches0\.overallHits::total\s+(\d+)",
    "l2_misses": r"board\.cache_hierarchy\.l2caches0\.overallMisses::total\s+(\d+)",
    "l2_accesses": r"board\.cache_hierarchy\.l2caches0\.overallAccesses::total\s+(\d+)",

    # DRAM (multiple possible stat paths)
    "dram_bytes_read": r"board\.memory\.mem_ctrl\.dram\.bytesRead::total\s+(\d+)",
    "dram_bytes_written": r"board\.memory\.mem_ctrl\.dram\.bytesWritten::total\s+(\d+)",
    "dram_read_reqs": r"board\.memory\.mem_ctrl\.dram\.readReqs\s+(\d+)",
    "dram_write_reqs": r"board\.memory\.mem_ctrl\.dram\.writeReqs\s+(\d+)",
    "dram_read_bursts": r"board\.memory\.mem_ctrl\.dram\.readBursts\s+(\d+)",
    "dram_write_bursts": r"board\.memory\.mem_ctrl\.dram\.writeBursts\s+(\d+)",

    # Committed instruction type breakdown (O3CPU)
    "op_IntAlu": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::IntAlu\s+(\d+)",
    "op_IntMult": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::IntMult\s+(\d+)",
    "op_IntDiv": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::IntDiv\s+(\d+)",
    "op_FloatAdd": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::FloatAdd\s+(\d+)",
    "op_FloatCmp": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::FloatCmp\s+(\d+)",
    "op_FloatCvt": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::FloatCvt\s+(\d+)",
    "op_FloatMult": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::FloatMult\s+(\d+)",
    "op_FloatMultAcc": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::FloatMultAcc\s+(\d+)",
    "op_FloatDiv": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::FloatDiv\s+(\d+)",
    "op_FloatMisc": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::FloatMisc\s+(\d+)",
    "op_FloatSqrt": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::FloatSqrt\s+(\d+)",
    "op_SimdAdd": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::SimdAdd\s+(\d+)",
    "op_SimdAddAcc": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::SimdAddAcc\s+(\d+)",
    "op_SimdAlu": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::SimdAlu\s+(\d+)",
    "op_SimdCmp": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::SimdCmp\s+(\d+)",
    "op_SimdCvt": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::SimdCvt\s+(\d+)",
    "op_SimdMisc": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::SimdMisc\s+(\d+)",
    "op_SimdMult": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::SimdMult\s+(\d+)",
    "op_SimdMultAcc": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::SimdMultAcc\s+(\d+)",
    "op_SimdShift": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::SimdShift\s+(\d+)",
    "op_SimdShiftAcc": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::SimdShiftAcc\s+(\d+)",
    "op_SimdFloatAdd": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::SimdFloatAdd\s+(\d+)",
    "op_SimdFloatAlu": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::SimdFloatAlu\s+(\d+)",
    "op_SimdFloatCmp": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::SimdFloatCmp\s+(\d+)",
    "op_SimdFloatCvt": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::SimdFloatCvt\s+(\d+)",
    "op_SimdFloatDiv": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::SimdFloatDiv\s+(\d+)",
    "op_SimdFloatMisc": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::SimdFloatMisc\s+(\d+)",
    "op_SimdFloatMult": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::SimdFloatMult\s+(\d+)",
    "op_SimdFloatMultAcc": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::SimdFloatMultAcc\s+(\d+)",
    "op_SimdFloatSqrt": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::SimdFloatSqrt\s+(\d+)",
    "op_MemRead": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::MemRead\s+(\d+)",
    "op_MemWrite": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::MemWrite\s+(\d+)",
    "op_FloatMemRead": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::FloatMemRead\s+(\d+)",
    "op_FloatMemWrite": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::FloatMemWrite\s+(\d+)",
    "op_IprAccess": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::IprAccess\s+(\d+)",
    "op_InstPrefetch": r"board\.processor\.cores0\.core\.commit\.committedInstType_0::InstPrefetch\s+(\d+)",
}

COMPILED_PATTERNS = {name: re.compile(pat) for name, pat in STAT_PATTERNS.items()}


def parse_stats(stats_path):
    metrics = {}
    with open(stats_path) as f:
        for line in f:
            for name, pat in COMPILED_PATTERNS.items():
                m = pat.search(line)
                if m:
                    val = m.group(1)
                    metrics[name] = float(val) if "." in val else int(val)
    return metrics


def discover_stats(stats_path, keywords=None):
    if keywords is None:
        keywords = ["dram", "bytes", "mem_ctrl", "bandwidth", "bw",
                     "committedinsttype", "issuedinsttype", "overall",
                     "miss", "hit", "access", "l1d", "l1i", "l2"]
    found = []
    with open(stats_path) as f:
        for line in f:
            line_lower = line.lower()
            if any(kw in line_lower for kw in keywords):
                found.append(line.rstrip())
    return found


def compute_derived(m):
    d = {}
    insts = m.get("simInsts", 0)
    ops = m.get("simOps", 0)
    cycles = m.get("numCycles", 0)
    insts_k = insts / 1000.0 if insts > 0 else 1.0

    d["cpi"] = m.get("cpi", cycles / insts if insts > 0 else 0.0)
    d["ipc"] = m.get("ipc", insts / cycles if cycles > 0 else 0.0)

    # Per-kilo-instruction miss rates
    d["l1d_mpki"] = m.get("l1d_misses", 0) / insts_k
    d["l1i_mpki"] = m.get("l1i_misses", 0) / insts_k
    d["l2_mpki"] = m.get("l2_misses", 0) / insts_k  # LLC MPKI

    # Hit rates
    l1d_acc = m.get("l1d_accesses", 0)
    l1i_acc = m.get("l1i_accesses", 0)
    l2_acc = m.get("l2_accesses", 0)
    d["l1d_hit_rate"] = m.get("l1d_hits", 0) / l1d_acc if l1d_acc > 0 else 0.0
    d["l1i_hit_rate"] = m.get("l1i_hits", 0) / l1i_acc if l1i_acc > 0 else 0.0
    d["l2_hit_rate"] = m.get("l2_hits", 0) / l2_acc if l2_acc > 0 else 0.0

    # LFMR: Last-to-First Miss Ratio = LLC misses / L1 total misses
    # L2 is our LLC; L1 total = L1D misses + L1I misses
    l1_total_misses = m.get("l1d_misses", 0) + m.get("l1i_misses", 0)
    l2_misses = m.get("l2_misses", 0)
    d["lfmr"] = l2_misses / l1_total_misses if l1_total_misses > 0 else 0.0

    # DAMOV Arithmetic Intensity: ops per L1 data cache line accessed
    # (Section 2.4.1: "arithmetic and logic operations per L1 cache line accessed")
    d["ai_damov"] = ops / l1d_acc if l1d_acc > 0 else 0.0

    # DRAM bytes: prefer explicit bytesRead/Written, fall back to reqs * line size
    dram_bytes = m.get("dram_bytes_read", 0) + m.get("dram_bytes_written", 0)
    if dram_bytes == 0:
        dram_reads = m.get("dram_read_reqs", m.get("dram_read_bursts", 0))
        dram_writes = m.get("dram_write_reqs", m.get("dram_write_bursts", 0))
        dram_bytes = (dram_reads + dram_writes) * CACHE_LINE_BYTES
    d["dram_bytes_total"] = dram_bytes

    # Roofline Arithmetic Intensity: ops per byte from DRAM
    d["ai_roofline"] = ops / dram_bytes if dram_bytes > 0 else float("inf")

    # Performance: GOPS/s = ops / (cycles / freq_GHz) / 1e9
    if cycles > 0:
        seconds = cycles / (CLOCK_FREQ_GHZ * 1e9)
        d["gops"] = ops / 1e9 / seconds if seconds > 0 else 0.0
    else:
        d["gops"] = 0.0

    # DRAM bandwidth (GB/s)
    if cycles > 0 and dram_bytes > 0:
        seconds = cycles / (CLOCK_FREQ_GHZ * 1e9)
        d["dram_bw_gbs"] = dram_bytes / 1e9 / seconds
    else:
        d["dram_bw_gbs"] = 0.0

    # Instruction type breakdown
    float_ops = sum(m.get(k, 0) for k in m if k.startswith("op_Float") and "Mem" not in k)
    simd_ops = sum(m.get(k, 0) for k in m if k.startswith("op_Simd"))
    int_alu_ops = m.get("op_IntAlu", 0)
    int_mult_ops = m.get("op_IntMult", 0)
    int_div_ops = m.get("op_IntDiv", 0)
    mem_read_ops = m.get("op_MemRead", 0) + m.get("op_FloatMemRead", 0)
    mem_write_ops = m.get("op_MemWrite", 0) + m.get("op_FloatMemWrite", 0)

    d["float_ops"] = float_ops
    d["simd_ops"] = simd_ops
    d["int_alu_ops"] = int_alu_ops
    d["int_mult_ops"] = int_mult_ops
    d["int_div_ops"] = int_div_ops
    d["mem_read_ops"] = mem_read_ops
    d["mem_write_ops"] = mem_write_ops
    d["compute_ops"] = int_alu_ops + int_mult_ops + int_div_ops + float_ops + simd_ops

    # Roofline AI using only FP+SIMD ops (traditional FLOP-based roofline)
    d["ai_roofline_fp"] = (float_ops + simd_ops) / dram_bytes if dram_bytes > 0 else float("inf")

    return d


def damov_classify(llc_mpki, lfmr, ai):
    """
    DAMOV bottleneck classification (architecture-dependent, Table 1).
    L2 is our LLC since no L3.
    """
    MPKI_THRESH = 11.0
    LFMR_THRESH = 0.56
    AI_THRESH = 8.5

    if llc_mpki >= MPKI_THRESH:
        if lfmr >= LFMR_THRESH:
            return ("1a", "DRAM BW-bound",
                    "High LLC misses that originate from L1 -> memory-bandwidth limited")
        else:
            return ("1b", "DRAM latency-bound",
                    "High LLC misses but filtered by L1/L2 -> memory-latency limited")
    else:
        if lfmr >= LFMR_THRESH:
            return ("1c", "L1/L2 capacity",
                    "Low LLC MPKI but high LFMR -> working set fits in LLC, L1/L2 pressure")
        else:
            if ai <= AI_THRESH:
                return ("2a", "LLC contention",
                        "Low MPKI, low LFMR, low AI -> LLC contention or streaming")
            else:
                return ("2c", "Compute-bound",
                        "Low MPKI, low LFMR, high AI -> compute limited")


def main():
    args_list = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    base_dir = args_list[0] if args_list else "m5out"
    do_discover = "--discover" in flags
    do_csv = "--csv" in flags

    if do_discover:
        for sp_num, sp_idx, weight in SIMPOINTS:
            detail_dir = os.path.join(base_dir, f"detail_sp{sp_num:02d}_idx{sp_idx}")
            stats_path = os.path.join(detail_dir, "stats.txt")
            if os.path.exists(stats_path):
                print(f"\n=== SP{sp_num:02d} idx{sp_idx} ===")
                for line in discover_stats(stats_path):
                    print(f"  {line}")
                print(f"\n(showing first available SimPoint only)")
                break
        return

    results = []
    total_weight = 0.0

    hdr = (f"{'SP':>3} {'Index':>6} {'Weight':>8} {'CPI':>8} {'IPC':>8} "
           f"{'L1D MPKI':>10} {'L1I MPKI':>10} {'LLC MPKI':>10} "
           f"{'LFMR':>8} {'AI(DAMOV)':>10} {'AI(Roof)':>10} "
           f"{'GOPS/s':>8} {'Insts':>14}")

    if not do_csv:
        print(hdr)
        print("-" * len(hdr))

    for sp_num, sp_idx, weight in SIMPOINTS:
        detail_dir = os.path.join(base_dir, f"detail_sp{sp_num:02d}_idx{sp_idx}")
        stats_path = os.path.join(detail_dir, "stats.txt")

        if not os.path.exists(stats_path):
            if not do_csv:
                print(f"{sp_num:>3} {sp_idx:>6} {weight:>8.5f}  ** MISSING **")
            continue

        m = parse_stats(stats_path)
        d = compute_derived(m)
        insts = m.get("simInsts", 0)

        if not do_csv:
            ai_roof_str = f"{d['ai_roofline']:.4f}" if d["ai_roofline"] != float("inf") else "inf"
            print(f"{sp_num:>3} {sp_idx:>6} {weight:>8.5f} {d['cpi']:>8.4f} "
                  f"{d['ipc']:>8.4f} {d['l1d_mpki']:>10.4f} {d['l1i_mpki']:>10.4f} "
                  f"{d['l2_mpki']:>10.4f} {d['lfmr']:>8.4f} {d['ai_damov']:>10.4f} "
                  f"{ai_roof_str:>10} {d['gops']:>8.3f} {insts:>14,}")

        record = {
            "sp_num": sp_num, "sp_idx": sp_idx, "weight": weight,
            "insts": insts, **d, **{k: v for k, v in m.items()},
        }
        results.append(record)
        total_weight += weight

    if not results:
        print("\nNo results found.")
        return

    if not do_csv:
        print("-" * len(hdr))

    # Weighted averages for scalar metrics
    avg_keys = [
        "cpi", "ipc", "l1d_mpki", "l1i_mpki", "l2_mpki",
        "lfmr", "ai_damov", "ai_roofline", "gops",
        "l1d_hit_rate", "l1i_hit_rate", "l2_hit_rate", "dram_bw_gbs",
    ]
    weighted = {}
    for key in avg_keys:
        vals = [r["weight"] * r.get(key, 0) for r in results
                if r.get(key, 0) != float("inf")]
        w_sum = sum(r["weight"] for r in results
                    if r.get(key, 0) != float("inf"))
        weighted[key] = sum(vals) / w_sum if w_sum > 0 else 0.0

    # Weighted sums for count metrics (per 100M interval)
    sum_keys = ["float_ops", "simd_ops", "int_alu_ops", "int_mult_ops",
                "int_div_ops", "mem_read_ops", "mem_write_ops", "compute_ops",
                "dram_bytes_total"]
    w_sums = {}
    for key in sum_keys:
        w_sums[key] = sum(r["weight"] * r.get(key, 0) for r in results) / total_weight

    # DAMOV classification on weighted averages
    cls_id, cls_name, cls_desc = damov_classify(
        weighted["l2_mpki"], weighted["lfmr"], weighted["ai_damov"]
    )

    if do_csv:
        csv_fields = ["sp_num", "sp_idx", "weight", "insts",
                      "cpi", "ipc", "l1d_mpki", "l1i_mpki", "l2_mpki",
                      "lfmr", "ai_damov", "ai_roofline", "gops",
                      "l1d_hit_rate", "l1i_hit_rate", "l2_hit_rate",
                      "dram_bw_gbs", "dram_bytes_total",
                      "float_ops", "simd_ops", "compute_ops",
                      "mem_read_ops", "mem_write_ops"]
        print(",".join(csv_fields))
        for r in results:
            vals = []
            for f in csv_fields:
                v = r.get(f, 0)
                if isinstance(v, float) and v == float("inf"):
                    vals.append("inf")
                elif isinstance(v, float):
                    vals.append(f"{v:.6f}")
                else:
                    vals.append(str(v))
            print(",".join(vals))
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
    print(f"  L1D hit rate:       {weighted['l1d_hit_rate']:.4f} ({weighted['l1d_hit_rate']*100:.2f}%)")
    print(f"  L1I hit rate:       {weighted['l1i_hit_rate']:.4f} ({weighted['l1i_hit_rate']*100:.2f}%)")
    print(f"  L2  hit rate:       {weighted['l2_hit_rate']:.4f} ({weighted['l2_hit_rate']*100:.2f}%)")

    print(f"\n  --- DAMOV Metrics ---")
    print(f"  LFMR (LLC/L1):      {weighted['lfmr']:.4f}  (threshold: 0.56)")
    print(f"  AI (ops/L1 line):   {weighted['ai_damov']:.4f}  (threshold: 8.5)")
    print(f"  LLC MPKI:           {weighted['l2_mpki']:.4f}  (threshold: 11.0)")

    print(f"\n  --- DAMOV Classification ---")
    print(f"  Class:              {cls_id} - {cls_name}")
    print(f"  Description:        {cls_desc}")

    print(f"\n  --- Roofline Analysis ---")
    ai_r = weighted["ai_roofline"]
    print(f"  AI (ops/byte DRAM): {ai_r:.4f}" if ai_r != float("inf") else
          f"  AI (ops/byte DRAM): inf (no DRAM traffic observed)")
    print(f"  DRAM BW:            {weighted['dram_bw_gbs']:.3f} GB/s")
    print(f"  DRAM bytes (wtd):   {w_sums['dram_bytes_total']:,.0f}")

    print(f"\n  --- Instruction Mix (weighted counts per 100M interval) ---")
    print(f"  Int ALU:            {w_sums['int_alu_ops']:>14,.0f}")
    print(f"  Int Mult:           {w_sums['int_mult_ops']:>14,.0f}")
    print(f"  Int Div:            {w_sums['int_div_ops']:>14,.0f}")
    print(f"  Float (scalar):     {w_sums['float_ops']:>14,.0f}")
    print(f"  SIMD:               {w_sums['simd_ops']:>14,.0f}")
    print(f"  Mem Read:           {w_sums['mem_read_ops']:>14,.0f}")
    print(f"  Mem Write:          {w_sums['mem_write_ops']:>14,.0f}")
    print(f"  Compute total:      {w_sums['compute_ops']:>14,.0f}")

    # Per-SimPoint DAMOV classification
    print(f"\n{'='*60}")
    print(f"  PER-SIMPOINT DAMOV CLASSIFICATION")
    print(f"{'='*60}")
    print(f"  {'SP':>3} {'Index':>6} {'Weight':>8} {'Class':>6} {'Name':<20} "
          f"{'LLC MPKI':>10} {'LFMR':>8} {'AI':>8}")
    print(f"  {'-'*80}")
    for r in results:
        c_id, c_name, _ = damov_classify(r["l2_mpki"], r["lfmr"], r["ai_damov"])
        print(f"  {r['sp_num']:>3} {r['sp_idx']:>6} {r['weight']:>8.5f} "
              f"{c_id:>6} {c_name:<20} {r['l2_mpki']:>10.4f} "
              f"{r['lfmr']:>8.4f} {r['ai_damov']:>8.4f}")

    # JSON dump for downstream analysis / plotting
    json_path = os.path.join(base_dir, "simpoint_metrics.json")
    json_data = {
        "config": {
            "cache_line_bytes": CACHE_LINE_BYTES,
            "clock_freq_ghz": CLOCK_FREQ_GHZ,
            "llc_level": "L2",
            "note": "No L3 in gem5 config; L2 serves as LLC",
        },
        "weighted_averages": weighted,
        "weighted_sums": w_sums,
        "damov_classification": {
            "class_id": cls_id,
            "class_name": cls_name,
            "description": cls_desc,
            "thresholds": {"mpki": 11.0, "lfmr": 0.56, "ai": 8.5},
        },
        "per_simpoint": [
            {
                "sp_num": r["sp_num"], "sp_idx": r["sp_idx"],
                "weight": r["weight"], "insts": r["insts"],
                "cpi": r["cpi"], "ipc": r["ipc"],
                "l1d_mpki": r["l1d_mpki"], "l1i_mpki": r["l1i_mpki"],
                "l2_mpki": r["l2_mpki"],
                "l1d_hit_rate": r["l1d_hit_rate"],
                "l1i_hit_rate": r["l1i_hit_rate"],
                "l2_hit_rate": r["l2_hit_rate"],
                "lfmr": r["lfmr"],
                "ai_damov": r["ai_damov"],
                "ai_roofline": r["ai_roofline"] if r["ai_roofline"] != float("inf") else None,
                "ai_roofline_fp": r.get("ai_roofline_fp", None) if r.get("ai_roofline_fp", float("inf")) != float("inf") else None,
                "gops": r["gops"],
                "dram_bw_gbs": r["dram_bw_gbs"],
                "dram_bytes_total": r["dram_bytes_total"],
                "float_ops": r["float_ops"],
                "simd_ops": r["simd_ops"],
                "compute_ops": r["compute_ops"],
                "mem_read_ops": r["mem_read_ops"],
                "mem_write_ops": r["mem_write_ops"],
                "damov_class": damov_classify(r["l2_mpki"], r["lfmr"], r["ai_damov"])[0],
            }
            for r in results
        ],
    }
    with open(json_path, "w") as f:
        json.dump(json_data, f, indent=2)
    print(f"\nFull metrics written to {json_path}")


if __name__ == "__main__":
    main()
