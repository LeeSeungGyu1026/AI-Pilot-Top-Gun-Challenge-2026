"""Extract training curves, the eval 'journey', and engagement-replay trajectories
into artifacts/presentation/data.json for the HTML progress presentation.

Light/read-only (no training). Re-runnable: add new demo episodes / stages and re-run
to refresh the JSON (e.g. after the BT run finishes).

    python scripts/build_presentation_data.py
"""
from __future__ import annotations
import csv, glob, json, math, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "artifacts" / "logs" / "team01"
EVAL = ROOT / "artifacts" / "eval"
OUT = ROOT / "artifacts" / "presentation"
OUT.mkdir(parents=True, exist_ok=True)


def _f(x):
    try:
        return float(x)
    except Exception:
        return float("nan")


def learning_curve(tag, keys=("win_rate", "loss_rate", "timeout_rate", "crash_rate",
                              "final_ata_deg", "ep_reward_damage")):
    p = LOGS / tag / "training_log.csv"
    if not p.exists():
        return None
    rows = list(csv.DictReader(open(p)))
    out = {"iter": [int(_f(r["iter"])) for r in rows]}
    for k in keys:
        out[k] = [round(_f(r.get(k, "")), 4) for r in rows]
    return out


def eval_summary(name):
    p = EVAL / name / "summary.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())


def _latlon_to_ne(lat, lon, lat0, lon0):
    mlat = 111320.0
    mlon = 111320.0 * math.cos(math.radians(lat0))
    return (lat - lat0) * mlat, (lon - lon0) * mlon


def demo_trajectory(tag, iteration, max_frames=160):
    base = LOGS / tag / "engagement_replays" / ("iter_%06d" % iteration) / "episode_00"
    o = glob.glob(str(base / "*ownship*.csv"))
    t = glob.glob(str(base / "*target*.csv"))
    if not o or not t:
        return None
    O = list(csv.DictReader(open(o[0])))
    T = list(csv.DictReader(open(t[0])))
    n = min(len(O), len(T))
    if n < 2:
        return None
    lat0 = _f(O[0]["Latitude"]); lon0 = _f(O[0]["Longitude"])
    step = max(1, n // max_frames)
    own, tgt, rng, ata = [], [], [], []
    for i in range(0, n, step):
        oi, ti = O[i], T[i]
        on, oe = _latlon_to_ne(_f(oi["Latitude"]), _f(oi["Longitude"]), lat0, lon0)
        tn, te = _latlon_to_ne(_f(ti["Latitude"]), _f(ti["Longitude"]), lat0, lon0)
        oalt = _f(oi["Altitude"]); talt = _f(ti["Altitude"])
        de, dn, dz = te - oe, tn - on, talt - oalt
        r = math.sqrt(de * de + dn * dn + dz * dz)
        brg = math.degrees(math.atan2(de, dn)) % 360.0
        hdg = _f(oi["Yaw (deg)"]) % 360.0
        a = (brg - hdg + 180.0) % 360.0 - 180.0
        own.append([round(on, 1), round(oe, 1), round(oalt, 1), round(hdg, 1), round(_f(oi["Health"]), 3)])
        tgt.append([round(tn, 1), round(te, 1), round(talt, 1), round(_f(ti["Yaw (deg)"]) % 360.0, 1), round(_f(ti["Health"]), 3)])
        rng.append(round(r, 1))
        ata.append(round(a, 1))
    return {"own": own, "tgt": tgt, "range": rng, "ata": ata, "frames": len(own)}


# --- demos: (key, tag, iteration, caption) ---
DEMO_SPECS = [
    ("before_wall", "ic_s2_level_v6", 20,
     "BEFORE the fix: the agent tracks the target for the full 90 s but never converts a kill (10% win). It is glued to the tail yet cannot finish."),
    ("after_fix", "ic_s2_rangedisc_v2", 50,
     "AFTER the range-discipline fix: a clean, decisive kill. The credit-assignment fix taught it to commit to the gun solution."),
    ("competition_range", "ic_s2_sep1450_v1", 50,
     "At the 1400 m competition spawn vs a maneuvering (weaving) target: closes from long range and scores the kill."),
    ("vs_bt", "ic_s3_bt_v1", 90,
     "A kill against the training behavior-tree opponent (the variant the agent mastered, 100%). It closes on the maneuvering BT and finishes cleanly — without chasing it into the ground."),
]


def main():
    data = {"demos": {}, "curves": {}, "journey": [], "evals": {}}

    for key, tag, it, cap in DEMO_SPECS:
        traj = demo_trajectory(tag, it)
        if traj:
            traj["caption"] = cap
            traj["tag"] = tag
            traj["iter"] = it
            data["demos"][key] = traj
            print(f"[demo] {key}: {tag} it{it} -> {traj['frames']} frames")
        else:
            print(f"[demo] {key}: {tag} it{it} -> NOT FOUND (skipped)")

    curve_tags = ["ic_s2_level_v6", "ic_s2_rangedisc_v1", "ic_s2_rangedisc_v2",
                  "ic_s2_weave_v1", "ic_s2_weave_v2", "ic_s2_sep950_v1", "ic_s2_sep1250_v1",
                  "ic_s2_sep1450_v1", "ic_s3_bt_v1"]
    for tag in curve_tags:
        c = learning_curve(tag)
        if c:
            data["curves"][tag] = c
            print(f"[curve] {tag}: {len(c['iter'])} iters")

    for name in ["v6_truecheck", "rangedisc_v2_check", "weave_v2_check",
                 "sep1250_weavecheck", "sep1450_milestone", "sep1450_vs_BT", "bt_v1_check"]:
        s = eval_summary(name)
        if s:
            data["evals"][name] = {k: s[k] for k in ("win_rate", "loss_rate", "draw_rate",
                                                      "episodes", "end_conditions") if k in s}

    blob = json.dumps(data)
    (OUT / "data.json").write_text(blob)
    # data.js wrapper so index.html can load it over file:// without a server (no CORS).
    (OUT / "data.js").write_text("window.PRESENTATION_DATA = " + blob + ";\n", encoding="utf-8")
    print(f"\nwrote {OUT / 'data.json'} and data.js ({len(blob)} bytes)")


if __name__ == "__main__":
    main()
