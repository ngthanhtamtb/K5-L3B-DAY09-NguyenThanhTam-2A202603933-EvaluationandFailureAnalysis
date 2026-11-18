"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item
from lab9.graders import GRADERS


def _is_bad_number(val: object) -> bool:
    if val is None or isinstance(val, bool):
        return False
    if isinstance(val, (int, float)):
        return math.isnan(val) or math.isinf(val)
    return True


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems: list[str] = []

    pr_metrics = pr.get("metrics") or {}
    for k, v in pr_metrics.items():
        if v is None or _is_bad_number(v):
            problems.append(f"metric {k!r} is None/NaN/inf")
    for m in spec.get("metrics") or []:
        mid = m["id"]
        if mid not in pr_metrics or pr_metrics[mid] is None or _is_bad_number(pr_metrics[mid]):
            problems.append(f"spec metric {mid!r} missing or NaN/inf in metrics")

    if pr.get("evaluator_failures"):
        problems.append(f"evaluator_failures non-empty ({len(pr['evaluator_failures'])})")

    pr_manifest = pr.get("manifest") or {}
    base_manifest = base.get("manifest") or {}
    pr_items = pr_manifest.get("items")
    pr_seeds = pr_manifest.get("seeds")
    base_items = base_manifest.get("items")
    base_seeds = base_manifest.get("seeds")

    pr_rows = pr.get("rows") or []
    base_rows = base.get("rows") or []

    if not isinstance(pr_items, int) or not isinstance(pr_seeds, list):
        problems.append("invalid manifest items or seeds")
    else:
        if len(pr_rows) != pr_items * len(pr_seeds):
            problems.append(f"len(rows)={len(pr_rows)} != manifest items ({pr_items}) x seeds ({len(pr_seeds)})")
        if len( pr_seeds ) != len(set(pr_seeds)):
            problems.append("duplicate seeds in manifest")

    if pr_items != base_items or list(pr_seeds or []) != list(base_seeds or []):
        problems.append("manifest items or seeds differ from baseline")

    if len(pr_rows) != len(base_rows):
        problems.append(f"row count {len(pr_rows)} != baseline row count {len(base_rows)}")

    pr_pairs = [(r.get("item_id"), r.get("seed")) for r in pr_rows]
    base_pairs = [(r.get("item_id"), r.get("seed")) for r in base_rows]
    if len(set(pr_pairs)) != len(pr_pairs):
        problems.append("duplicate (item_id, seed) rows in PR")
    if set(pr_pairs) != set(base_pairs):
        problems.append("(item_id, seed) set differs from baseline")

    # Determine which spec metrics are row-level graded metrics
    row_keys = {k for r in [*pr_rows, *base_rows] for k in r.keys()} - {"item_id", "seed", "slices", "cost"}
    graded_ids = [
        m["id"]
        for m in (spec.get("metrics") or [])
        if m["id"] in row_keys or (m["id"] in GRADERS and row_keys)
    ]
    for r in pr_rows:
        for mid in graded_ids:
            val = r.get(mid)
            if val is None or _is_bad_number(val):
                problems.append(f"row {r.get('item_id')}@{r.get('seed')} has None/NaN for {mid}")

    # Verify slice tags per (item_id, seed) and per item_id match baseline
    base_slices_by_pair = {(r.get("item_id"), r.get("seed")): sorted(r.get("slices") or []) for r in base_rows}
    base_slices_by_item = {r.get("item_id"): sorted(r.get("slices") or []) for r in base_rows}
    for r in pr_rows:
        pair = (r.get("item_id"), r.get("seed"))
        r_slices = sorted(r.get("slices") or [])
        if pair in base_slices_by_pair and r_slices != base_slices_by_pair[pair]:
            problems.append(f"slice tags modified for {pair[0]}@{pair[1]}")
        elif r.get("item_id") in base_slices_by_item and r_slices != base_slices_by_item[r.get("item_id")]:
            problems.append(f"slice tags modified for item {r.get('item_id')}")

    # Verify row-level aggregates match reported metrics when all row values are valid booleans/numbers
    if pr_rows and not problems:
        for mid in graded_ids:
            vals = [r.get(mid) for r in pr_rows if r.get(mid) is not None and not _is_bad_number(r.get(mid))]
            if len(vals) == len(pr_rows) and mid in pr_metrics and not _is_bad_number(pr_metrics[mid]):
                expected = sum(vals) if mid in ("secret_leak", "approval_bypass") else round(sum(vals) / len(vals), 4)
                if abs(float(pr_metrics[mid]) - float(expected)) > 1e-3:
                    problems.append(f"metric {mid} ({pr_metrics[mid]}) disagrees with row aggregate ({expected})")

    # Ratchet check against base_spec
    if base_spec is not None and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        spec_metrics = {m["id"]: m for m in (spec.get("metrics") or [])}
        for bm in base_spec.get("metrics") or []:
            mid = bm["id"]
            if mid not in spec_metrics:
                problems.append(f"ratchet: metric {mid} removed")
                continue
            sm = spec_metrics[mid]
            if bm.get("blocking") and not sm.get("blocking"):
                problems.append(f"ratchet: metric {mid} became non-blocking")
            bth = bm.get("threshold") or {}
            sth = sm.get("threshold") or {}
            if "min" in bth and ("min" not in sth or sth["min"] < bth["min"]):
                problems.append(f"ratchet: metric {mid} min threshold loosened")
            if "max" in bth and ("max" not in sth or sth["max"] > bth["max"]):
                problems.append(f"ratchet: metric {mid} max threshold loosened")
            if "max_increase" in bth and ("max_increase" not in sth or sth["max_increase"] > bth["max_increase"]):
                problems.append(f"ratchet: metric {mid} max_increase threshold loosened")
            if bth.get("no_significant_drop") and not sth.get("no_significant_drop"):
                problems.append(f"ratchet: metric {mid} dropped no_significant_drop")

        spec_slices = {(s["name"], s["metric"]): s for s in (spec.get("slices") or [])}
        for bs in base_spec.get("slices") or []:
            skey = (bs["name"], bs["metric"])
            if skey not in spec_slices:
                problems.append(f"ratchet: slice {skey[0]}/{skey[1]} removed")
                continue
            ss = spec_slices[skey]
            if bs.get("blocking") and not ss.get("blocking"):
                problems.append(f"ratchet: slice {skey[0]}/{skey[1]} became non-blocking")
            if "min" in bs and ("min" not in ss or ss["min"] < bs["min"]):
                problems.append(f"ratchet: slice {skey[0]}/{skey[1]} min threshold loosened")
            if "max" in bs and ("max" not in ss or ss["max"] > bs["max"]):
                problems.append(f"ratchet: slice {skey[0]}/{skey[1]} max threshold loosened")
            if bs.get("no_significant_drop") and not ss.get("no_significant_drop"):
                problems.append(f"ratchet: slice {skey[0]}/{skey[1]} dropped no_significant_drop")

    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked: list[str] = []
    lines: list[str] = []
    bs = spec.get("bootstrap", {})
    for s in spec.get("slices") or []:
        name, mid = s["name"], s["metric"]
        sid = f"slice:{name}/{mid}"
        a = per_item(pr, mid, slice_name=name)
        b = per_item(base, mid, slice_name=name)
        val = round(sum(a.values()) / len(a), 4) if a else None
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        else:
            if "max" in s and val > s["max"]:
                verdict = "fail"
            if "min" in s and val < s["min"]:
                verdict = "fail"
            if s.get("no_significant_drop"):
                keys = sorted(set(a) & set(b))
                if keys:
                    d, lo, hi = stats.paired_bootstrap(
                        [a[k] for k in keys],
                        [b[k] for k in keys],
                        n_resamples=bs.get("n_resamples", 1000),
                        rng=bs.get("rng", 2027),
                    )
                    note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                    if hi < 0:
                        verdict = "fail"
        if verdict != "ok" and s.get("blocking"):
            blocked.append(sid)
        th = {k: s[k] for k in ("min", "max", "no_significant_drop") if k in s}
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if s.get("blocking") else "warn")
        lines.append(f"  {sid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
