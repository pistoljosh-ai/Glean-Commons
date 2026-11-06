#!/usr/bin/env python3
"""Compare per-variant usage events and recommend promote / coexist / keep testing.

Stdlib only. Free and simple.

CSV columns (header required):
  variant,user_id,benefit_hours,depth_runs,still_active_4w

- variant: variant id (e.g. control, treatment)
- user_id: unique human id (creator self-use should already be filtered out)
- benefit_hours: hours saved (primary metric by default)
- depth_runs: optional depth signal
- still_active_4w: 0 or 1, optional durability

Example:
  python3 analyst/compare.py analyst/sample_events.csv --metric benefit_hours
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

MIN_USERS = 30
MIN_SEGMENT = 20
# Two-sided alpha for "clearly better"
ALPHA = 0.05
# Relative lift below this → treat as too close unless preferences diverge
MIN_LIFT = 0.10


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def variance(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)


def welch_t_p(a: list[float], b: list[float]) -> tuple[float, float]:
    """Welch's t-test; returns (t, two-sided p via normal approx of t for df large)."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return float("nan"), 1.0
    ma, mb = mean(a), mean(b)
    va, vb = variance(a), variance(b)
    se = math.sqrt(va / na + vb / nb)
    if se == 0:
        return 0.0, 1.0
    t = (ma - mb) / se
    # Welch–Satterthwaite df
    num = (va / na + vb / nb) ** 2
    den = 0.0
    if na > 1:
        den += (va / na) ** 2 / (na - 1)
    if nb > 1:
        den += (vb / nb) ** 2 / (nb - 1)
    df = num / den if den else 1.0
    # Normal approximation is fine for our sample-size floor; refine with
    # a simple t→p using erf on a z that slightly inflates for low df.
    z = abs(t) * (1.0 - 1.0 / (4.0 * df))
    # two-sided p from normal
    p = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(z / math.sqrt(2.0))))
    return t, max(0.0, min(1.0, p))


def load_events(path: Path, metric: str) -> dict[str, list[float]]:
    by: dict[str, list[float]] = defaultdict(list)
    users: dict[str, set[str]] = defaultdict(set)
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "variant" not in reader.fieldnames:
            raise SystemExit("CSV needs a header with at least: variant,user_id," + metric)
        if metric not in reader.fieldnames:
            raise SystemExit(f"CSV missing metric column '{metric}'")
        for row in reader:
            v = row["variant"].strip()
            uid = row.get("user_id", "").strip()
            if not v or not uid:
                continue
            if uid in users[v]:
                continue  # one row per user per variant
            users[v].add(uid)
            try:
                val = float(row[metric])
            except (TypeError, ValueError):
                continue
            by[v].append(val)
    return dict(by)


def preference_segments(path: Path) -> dict[str, int]:
    """If CSV has preferred_variant column, count users who state a preference."""
    counts: dict[str, int] = defaultdict(int)
    seen: set[str] = set()
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "preferred_variant" not in reader.fieldnames:
            return {}
        for row in reader:
            uid = row.get("user_id", "").strip()
            pref = row.get("preferred_variant", "").strip()
            if not uid or not pref or uid in seen:
                continue
            seen.add(uid)
            counts[pref] += 1
    return dict(counts)


def recommend(
    by: dict[str, list[float]],
    prefs: dict[str, int],
    metric: str,
) -> dict:
    variants = sorted(by.keys())
    if len(variants) < 2:
        return {
            "recommendation": "keep_testing",
            "reason": "Need at least two variants.",
            "variants": variants,
        }

    sizes = {v: len(by[v]) for v in variants}
    means = {v: mean(by[v]) for v in variants}
    best = max(variants, key=lambda v: means[v])
    rest = [v for v in variants if v != best]
    # Compare best vs next-best
    second = max(rest, key=lambda v: means[v])
    t, p = welch_t_p(by[best], by[second])
    lift = (
        (means[best] - means[second]) / abs(means[second])
        if means[second] != 0
        else float("inf")
    )

    underpowered = any(sizes[v] < MIN_USERS for v in variants)

    # Preference coexistence signal
    coexist_ok = (
        prefs
        and all(prefs.get(v, 0) >= MIN_SEGMENT for v in variants)
        and len([v for v in variants if prefs.get(v, 0) >= MIN_SEGMENT]) >= 2
    )

    result = {
        "metric": metric,
        "n": sizes,
        "mean": {v: round(means[v], 4) for v in variants},
        "best": best,
        "second": second,
        "lift_vs_second": None if math.isinf(lift) else round(lift, 4),
        "welch_t": None if math.isnan(t) else round(t, 4),
        "p_approx": round(p, 4),
        "prefs": prefs,
        "min_users": MIN_USERS,
        "alpha": ALPHA,
        "min_lift": MIN_LIFT,
    }

    if underpowered:
        result["recommendation"] = "keep_testing"
        result["reason"] = (
            f"At least one variant has n < {MIN_USERS}. "
            "Do not promote yet."
        )
        return result

    if coexist_ok and p > ALPHA:
        result["recommendation"] = "coexist"
        result["reason"] = (
            "No clear overall winner, but each variant has a solid "
            f"preference segment (≥ {MIN_SEGMENT}). Route by preference."
        )
        return result

    if p <= ALPHA and lift >= MIN_LIFT:
        result["recommendation"] = "promote"
        result["reason"] = (
            f"'{best}' is clearly ahead on {metric} "
            f"(p≈{p:.4f}, lift≥{MIN_LIFT:.0%}). Human must still approve."
        )
        return result

    if coexist_ok:
        result["recommendation"] = "coexist"
        result["reason"] = (
            "Overall difference is weak, but preferences split. "
            "Keep both and route by preference."
        )
        return result

    result["recommendation"] = "keep_testing"
    result["reason"] = (
        "Too close to call, or lift below the minimum bar. "
        "Gather more honest use."
    )
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="Compare variant event CSVs")
    ap.add_argument("csv_path", type=Path)
    ap.add_argument("--metric", default="benefit_hours")
    args = ap.parse_args()
    if not args.csv_path.exists():
        print(f"FAIL: {args.csv_path} not found", file=sys.stderr)
        return 1

    by = load_events(args.csv_path, args.metric)
    prefs = preference_segments(args.csv_path)
    out = recommend(by, prefs, args.metric)

    print("Commons Analyst — compare.py")
    print(f"file: {args.csv_path}")
    print(f"metric: {out.get('metric')}")
    print(f"n: {out.get('n')}")
    print(f"mean: {out.get('mean')}")
    if out.get("prefs"):
        print(f"prefs: {out['prefs']}")
    print(f"best: {out.get('best')}  second: {out.get('second')}")
    print(f"lift_vs_second: {out.get('lift_vs_second')}  p_approx: {out.get('p_approx')}")
    print(f"recommendation: {out['recommendation']}")
    print(f"reason: {out['reason']}")
    print("Note: humans approve every promotion. See ANALYST.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
