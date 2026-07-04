from __future__ import annotations

import csv
import json
import math
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
ENV_ROOT = ROOT / "AIP_LIB" / "DogFightEnv" / "Release_260529"
LOG_ROOT = ENV_ROOT / "artifacts" / "logs" / "team01"
OUT_HTML = ROOT / "reports" / "training_progress_report.html"
VIDEO_PATH = ROOT / "1일차 강의 자료" / "경진대회에서 사용할 교전환경.mp4"


METRIC_LABELS = {
    "reward_mean": "Mean reward",
    "win_rate": "Win rate",
    "loss_rate": "Loss rate",
    "timeout_rate": "Timeout rate",
    "crash_rate": "Crash rate",
    "ep_wez_steps": "WEZ steps",
    "ep_min_distance": "Min distance",
    "ep_mean_distance": "Mean distance",
    "ep_len_mean": "Episode length",
}


def as_float(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"n/a", "nan", "none"}:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def mean(values: list[float | None]) -> float | None:
    numbers = [value for value in values if value is not None]
    if not numbers:
        return None
    return sum(numbers) / len(numbers)


def row_metrics(rows: list[dict[str, str]], tail: int = 10) -> dict[str, float | None]:
    selected = rows[-tail:] if rows else []
    return {
        key: mean([as_float(row.get(key)) for row in selected])
        for key in METRIC_LABELS
    }


def summarize_run(run_dir: Path) -> dict[str, object] | None:
    rows = read_csv(run_dir / "training_log.csv")
    if not rows:
        return None
    last = rows[-1]
    tail = row_metrics(rows)
    final = {key: as_float(last.get(key)) for key in METRIC_LABELS}
    return {
        "name": run_dir.name,
        "modified": run_dir.stat().st_mtime,
        "modified_iso": datetime.fromtimestamp(run_dir.stat().st_mtime).isoformat(timespec="seconds"),
        "rows": len(rows),
        "last_iter": as_float(last.get("iter")),
        "last_steps": as_float(last.get("sampled_steps")),
        "final": final,
        "tail10": tail,
    }


def list_run_summaries() -> list[dict[str, object]]:
    summaries: list[dict[str, object]] = []
    if not LOG_ROOT.exists():
        return summaries
    for run_dir in LOG_ROOT.iterdir():
        if not run_dir.is_dir():
            continue
        summary = summarize_run(run_dir)
        if summary:
            summaries.append(summary)
    summaries.sort(key=lambda item: item["modified"])
    return summaries


def read_series(run_name: str, fields: list[str]) -> list[dict[str, float | None]]:
    rows = read_csv(LOG_ROOT / run_name / "training_log.csv")
    series: list[dict[str, float | None]] = []
    for row in rows:
        item = {"iter": as_float(row.get("iter"))}
        for field in fields:
            item[field] = as_float(row.get(field))
        series.append(item)
    return series


def choose_latest_by_prefix(summaries: list[dict[str, object]], prefix: str) -> dict[str, object] | None:
    candidates = [item for item in summaries if str(item["name"]).startswith(prefix)]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item["modified"])


def build_key_runs(summaries: list[dict[str, object]]) -> list[dict[str, object]]:
    names = [
        "ppo_tgc26_pbrs_v1",
        "ppo_tgc26_close_v2",
        "saddle_test_v1",
        "saddle_level_v6",
        "ic_s2_level_v7",
        "ic_s2_cone5_v1",
        "ic_s2_finish_v1",
        "ic_s2_rangedisc_v2",
        "ic_s2_weave_v3",
        "ic_s2_sep950_v1",
        "ic_s2_sep1150_v2",
        "ic_s2_sep1250_v1",
        "ic_s2_sep1350_v1",
        "ic_s2_sep1450_v1",
        "ic_s3_bt_v1",
    ]
    by_name = {str(item["name"]): item for item in summaries}
    runs = [by_name[name] for name in names if name in by_name]
    seen = {str(item["name"]) for item in runs}
    latest = choose_latest_by_prefix(summaries, "ic_s3_")
    if latest and str(latest["name"]) not in seen:
        runs.append(latest)
    return runs


def build_separation_runs(summaries: list[dict[str, object]]) -> list[dict[str, object]]:
    latest_by_distance: dict[int, dict[str, object]] = {}
    for item in summaries:
        match = re.match(r"ic_s2_sep(\d+)_v\d+", str(item["name"]))
        if not match:
            continue
        distance = int(match.group(1))
        item = dict(item)
        item["separation_m"] = distance
        current = latest_by_distance.get(distance)
        if current is None or item["modified"] > current["modified"]:
            latest_by_distance[distance] = item
    return [latest_by_distance[key] for key in sorted(latest_by_distance)]


def normalize_replay_path(raw: str) -> Path:
    path = Path(raw)
    if path.exists():
        return path
    rel = str(raw).replace(str(ROOT), "").lstrip("\\/")
    return ROOT / rel


def load_replay(run_name: str) -> dict[str, object]:
    index_rows = read_csv(LOG_ROOT / run_name / "engagement_replays" / "replay_index.csv")
    if not index_rows:
        return {"points": [], "summary": {}}
    wins = [row for row in index_rows if row.get("outcome") == "win"]
    selected = max(wins or index_rows, key=lambda row: as_float(row.get("iteration")) or -1)
    own_rows = read_csv(normalize_replay_path(selected.get("ownship_log", "")))
    tgt_rows = read_csv(normalize_replay_path(selected.get("target_log", "")))
    count = min(len(own_rows), len(tgt_rows))
    if count == 0:
        return {"points": [], "summary": selected}

    step = max(1, count // 240)
    lat0 = mean([
        as_float(own_rows[0].get("Latitude")),
        as_float(tgt_rows[0].get("Latitude")),
    ]) or 0.0
    lon0 = mean([
        as_float(own_rows[0].get("Longitude")),
        as_float(tgt_rows[0].get("Longitude")),
    ]) or 0.0
    cos_lat = math.cos(math.radians(lat0))

    def project(row: dict[str, str]) -> tuple[float, float, float]:
        lat = as_float(row.get("Latitude")) or lat0
        lon = as_float(row.get("Longitude")) or lon0
        alt = as_float(row.get("Altitude")) or 0.0
        x = (lon - lon0) * 111_320.0 * cos_lat
        y = (lat - lat0) * 110_540.0
        return x, y, alt

    points: list[dict[str, float | None]] = []
    for idx in range(0, count, step):
        own = own_rows[idx]
        tgt = tgt_rows[idx]
        ox, oy, oa = project(own)
        tx, ty, ta = project(tgt)
        points.append({
            "t": as_float(own.get("Time")),
            "ox": round(ox, 2),
            "oy": round(oy, 2),
            "oa": round(oa, 2),
            "tx": round(tx, 2),
            "ty": round(ty, 2),
            "ta": round(ta, 2),
            "oh": as_float(own.get("Health")),
            "th": as_float(tgt.get("Health")),
            "d": round(math.hypot(ox - tx, oy - ty), 2),
        })

    return {
        "points": points,
        "summary": {
            "run": run_name,
            "iteration": as_float(selected.get("iteration")),
            "outcome": selected.get("outcome"),
            "end_condition": selected.get("end_condition"),
            "steps": as_float(selected.get("steps")),
            "total_reward": as_float(selected.get("total_reward")),
            "ep_min_distance": as_float(selected.get("ep_min_distance")),
            "ownship_health": as_float(selected.get("ownship_health")),
            "target_health": as_float(selected.get("target_health")),
        },
    }


def fmt_number(value: float | None, suffix: str = "", digits: int = 1) -> str:
    if value is None:
        return "-"
    if abs(value) >= 1000:
        text = f"{value:,.0f}"
    else:
        text = f"{value:.{digits}f}"
    return f"{text}{suffix}"


def pct(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value * 100:.0f}%"


def html_escape(text: object) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_html(data: dict[str, object]) -> str:
    json_blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    current = data["current"]
    current_tail = current["tail10"]
    key_rows = []
    for run in data["key_runs"]:
        tail = run["tail10"]
        key_rows.append(
            "<tr>"
            f"<td>{html_escape(run['name'])}</td>"
            f"<td>{fmt_number(run['last_iter'], digits=0)}</td>"
            f"<td>{pct(tail.get('win_rate'))}</td>"
            f"<td>{pct(tail.get('crash_rate'))}</td>"
            f"<td>{fmt_number(tail.get('ep_wez_steps'), digits=1)}</td>"
            f"<td>{fmt_number(tail.get('ep_min_distance'), ' m', 0)}</td>"
            f"<td>{fmt_number(tail.get('reward_mean'), digits=1)}</td>"
            "</tr>"
        )
    sep_rows = []
    for run in data["separation_runs"]:
        tail = run["tail10"]
        sep_rows.append(
            "<tr>"
            f"<td>{run['separation_m']} m</td>"
            f"<td>{html_escape(run['name'])}</td>"
            f"<td>{pct(tail.get('win_rate'))}</td>"
            f"<td>{fmt_number(tail.get('ep_min_distance'), ' m', 0)}</td>"
            f"<td>{fmt_number(tail.get('ep_wez_steps'), digits=1)}</td>"
            "</tr>"
        )

    video_src = quote(str(Path("..") / VIDEO_PATH.relative_to(ROOT)).replace("\\", "/"), safe="/")
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Pilot Top Gun Training Progress</title>
  <style>
    :root {{
      --bg: #f6f7f2;
      --ink: #1f2a2e;
      --muted: #68747a;
      --line: #d9dfd8;
      --panel: #ffffff;
      --blue: #2f6f9f;
      --green: #2e7d55;
      --red: #bd4b4b;
      --amber: #b8791f;
      --teal: #2a7f79;
      --shadow: 0 12px 28px rgba(25, 36, 38, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background: var(--bg);
      font-family: Arial, "Malgun Gothic", sans-serif;
      letter-spacing: 0;
    }}
    main {{ width: min(1240px, calc(100% - 32px)); margin: 0 auto; padding: 28px 0 42px; }}
    header {{
      display: grid;
      grid-template-columns: minmax(0, 1.5fr) minmax(280px, 0.8fr);
      gap: 20px;
      align-items: end;
      padding: 20px 0 18px;
      border-bottom: 1px solid var(--line);
    }}
    h1 {{ margin: 0; font-size: clamp(28px, 4vw, 48px); line-height: 1.05; }}
    h2 {{ margin: 0 0 14px; font-size: 22px; }}
    h3 {{ margin: 0 0 8px; font-size: 17px; }}
    p {{ margin: 0; color: var(--muted); line-height: 1.55; }}
    .stamp {{ text-align: right; color: var(--muted); font-size: 14px; line-height: 1.6; }}
    .grid {{ display: grid; gap: 18px; }}
    .cards {{ grid-template-columns: repeat(4, minmax(0, 1fr)); margin: 20px 0; }}
    .card, .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }}
    .card {{ padding: 16px; min-height: 112px; }}
    .label {{ color: var(--muted); font-size: 13px; }}
    .value {{ margin-top: 8px; font-size: 30px; font-weight: 700; line-height: 1.05; }}
    .sub {{ margin-top: 8px; color: var(--muted); font-size: 13px; line-height: 1.45; }}
    .panel {{ padding: 18px; }}
    .two {{ grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }}
    .wide {{ grid-column: 1 / -1; }}
    canvas.chart {{ width: 100%; height: 280px; display: block; }}
    .timeline {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 10px;
      margin-top: 14px;
    }}
    .stage {{
      border-left: 4px solid var(--blue);
      background: #f9faf7;
      padding: 12px;
      min-height: 132px;
      border-radius: 6px;
    }}
    .stage:nth-child(2) {{ border-color: var(--red); }}
    .stage:nth-child(3) {{ border-color: var(--green); }}
    .stage:nth-child(4) {{ border-color: var(--amber); }}
    .stage:nth-child(5) {{ border-color: var(--teal); }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 10px 8px; border-bottom: 1px solid var(--line); text-align: right; }}
    th:first-child, td:first-child, th:nth-child(2), td:nth-child(2) {{ text-align: left; }}
    th {{ color: var(--muted); font-weight: 600; }}
    .media-grid {{ grid-template-columns: minmax(0, 1.1fr) minmax(0, 0.9fr); align-items: start; }}
    video {{
      width: 100%;
      display: block;
      border-radius: 8px;
      background: #111;
      border: 1px solid var(--line);
    }}
    .replay-wrap {{
      position: relative;
      min-height: 360px;
      background: #101820;
      border: 1px solid #20313a;
      border-radius: 8px;
      overflow: hidden;
    }}
    #replayCanvas {{ width: 100%; height: 360px; display: block; }}
    .replay-readout {{
      position: absolute;
      left: 12px;
      bottom: 12px;
      right: 12px;
      display: flex;
      justify-content: space-between;
      gap: 10px;
      color: #eaf2ef;
      font-size: 13px;
      background: rgba(16, 24, 32, 0.72);
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 6px;
      padding: 8px 10px;
    }}
    .legend {{ display: flex; gap: 14px; flex-wrap: wrap; margin-top: 10px; color: var(--muted); font-size: 13px; }}
    .swatch {{ width: 12px; height: 12px; border-radius: 50%; display: inline-block; margin-right: 6px; vertical-align: -1px; }}
    .note {{ margin-top: 10px; font-size: 13px; color: var(--muted); }}
    @media (max-width: 900px) {{
      header, .two, .media-grid {{ grid-template-columns: 1fr; }}
      .stamp {{ text-align: left; }}
      .cards {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .timeline {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 560px) {{
      main {{ width: min(100% - 20px, 1240px); padding-top: 18px; }}
      .cards {{ grid-template-columns: 1fr; }}
      table {{ font-size: 12px; }}
      th, td {{ padding: 8px 5px; }}
      .value {{ font-size: 26px; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>AI Pilot Top Gun 훈련 진행 리포트</h1>
        <p>JSBSim 기반 F-16 1v1 gun-only dogfight에서 PPO 정책을 학습한 현재까지의 맥락, 주요 실험, 결과 지표를 한 화면에 정리했습니다.</p>
      </div>
      <div class="stamp">
        생성 시각: {generated_at}<br>
        데이터: AIP_LIB/DogFightEnv/Release_260529/artifacts/logs/team01
      </div>
    </header>

    <section class="grid cards">
      <div class="card">
        <div class="label">현재 대표 실험</div>
        <div class="value">{html_escape(current['name'])}</div>
        <div class="sub">최근 BT 재도입 실험</div>
      </div>
      <div class="card">
        <div class="label">최근 10 iter 승률</div>
        <div class="value">{pct(current_tail.get('win_rate'))}</div>
        <div class="sub">마지막 iter 기준 {pct(current['final'].get('win_rate'))}</div>
      </div>
      <div class="card">
        <div class="label">최근 10 iter 추락률</div>
        <div class="value">{pct(current_tail.get('crash_rate'))}</div>
        <div class="sub">action slew limiter 이후 FDM blow-up 억제</div>
      </div>
      <div class="card">
        <div class="label">최근 10 iter WEZ 접촉</div>
        <div class="value">{fmt_number(current_tail.get('ep_wez_steps'), digits=1)}</div>
        <div class="sub">평균 최소거리 {fmt_number(current_tail.get('ep_min_distance'), ' m', 0)}</div>
      </div>
    </section>

    <section class="panel">
      <h2>프로젝트 맥락</h2>
      <p>목표는 F-16을 조종하는 강화학습 정책이 1v1 근접 공중전에서 상대를 gun WEZ 안에 유지해 격추하는 것입니다. 환경은 JSBSim flight dynamics와 RLlib 2.54/PyTorch PPO를 사용하며, 최종 평가지표는 Unreal 서버에서의 승률입니다. 관측은 각도 sin/cos, 거리, closure/LOS rate, 에너지, lead-angle error, WEZ flag를 포함하고, 보상은 pursuit PBRS, dense pursuit, damage, 안전/종료 항목으로 구성됩니다.</p>
      <div class="timeline">
        <div class="stage">
          <h3>1. Flat run</h3>
          <p>비행 안정성은 얻었지만 1.2-1.6 km에서 맴돌며 WEZ 진입과 승리가 거의 없었습니다.</p>
        </div>
        <div class="stage">
          <h3>2. Stage-0 failure</h3>
          <p>생존 전용 stage가 고도 패널티 때문에 빠른 추락을 유리하게 만들어 crash-fast attractor가 발생했습니다.</p>
        </div>
        <div class="stage">
          <h3>3. Reward repair</h3>
          <p>Altitude PBRS, 항상 켜진 pursuit shaping, 첫 WEZ 보너스, draw/loss 패널티, action slew limiter로 안정 비행을 회복했습니다.</p>
        </div>
        <div class="stage">
          <h3>4. Contact bootstrap</h3>
          <p>근접 saddle/offensive start와 cone/level/finish 실험으로 첫 WEZ 접촉과 target destroyed 경험을 만들었습니다.</p>
        </div>
        <div class="stage">
          <h3>5. Generalization</h3>
          <p>950-1450 m 분리거리, range discipline, weave, BT 재도입을 거쳐 현재 BT 상대 승률이 안정화되었습니다.</p>
        </div>
      </div>
    </section>

    <section class="grid two" style="margin-top:18px;">
      <div class="panel">
        <h2>BT 재도입 학습 곡선</h2>
        <canvas id="btChart" class="chart"></canvas>
        <div class="legend">
          <span><i class="swatch" style="background:var(--green)"></i>Win rate</span>
          <span><i class="swatch" style="background:var(--red)"></i>Loss rate</span>
          <span><i class="swatch" style="background:var(--blue)"></i>Crash rate</span>
        </div>
      </div>
      <div class="panel">
        <h2>교전 품질 지표</h2>
        <canvas id="engagementChart" class="chart"></canvas>
        <div class="legend">
          <span><i class="swatch" style="background:var(--amber)"></i>WEZ steps</span>
          <span><i class="swatch" style="background:var(--teal)"></i>Min distance</span>
        </div>
      </div>
      <div class="panel">
        <h2>분리거리 curriculum 결과</h2>
        <canvas id="sepChart" class="chart"></canvas>
        <div class="note">각 거리는 같은 prefix에서 가장 최근 버전을 사용했고, 값은 최근 10 iter 평균입니다.</div>
      </div>
      <div class="panel">
        <h2>실험 진행별 최종 성능</h2>
        <canvas id="progressChart" class="chart"></canvas>
        <div class="note">대표 실험의 최근 10 iter win rate와 crash rate를 함께 비교합니다.</div>
      </div>
    </section>

    <section class="grid media-grid" style="margin-top:18px;">
      <div class="panel">
        <h2>Demo Video</h2>
        <video controls preload="metadata">
          <source src="{video_src}" type="video/mp4">
        </video>
        <p class="note">프로젝트에 포함된 대회 교전환경 reference video입니다. 훈련 로그 기반 실제 궤적 데모는 오른쪽 캔버스에서 재생됩니다.</p>
      </div>
      <div class="panel">
        <h2>훈련 리플레이 데모</h2>
        <div class="replay-wrap">
          <canvas id="replayCanvas"></canvas>
          <div class="replay-readout">
            <span id="replayTime">t=0.0s</span>
            <span id="replayDist">distance=-</span>
            <span id="replayHealth">target health=-</span>
          </div>
        </div>
        <p class="note">대표 리플레이: {html_escape(data['replay']['summary'].get('run'))}, iter {fmt_number(data['replay']['summary'].get('iteration'), digits=0)}, {html_escape(data['replay']['summary'].get('end_condition'))}</p>
      </div>
    </section>

    <section class="grid two" style="margin-top:18px;">
      <div class="panel wide">
        <h2>대표 실험 요약</h2>
        <table>
          <thead>
            <tr><th>Run</th><th>Last iter</th><th>Win</th><th>Crash</th><th>WEZ steps</th><th>Min distance</th><th>Reward</th></tr>
          </thead>
          <tbody>
            {''.join(key_rows)}
          </tbody>
        </table>
      </div>
      <div class="panel wide">
        <h2>분리거리 sweep</h2>
        <table>
          <thead>
            <tr><th>Separation</th><th>Run</th><th>Win</th><th>Min distance</th><th>WEZ steps</th></tr>
          </thead>
          <tbody>
            {''.join(sep_rows)}
          </tbody>
        </table>
      </div>
    </section>
  </main>

  <script id="report-data" type="application/json">{json_blob}</script>
  <script>
    const data = JSON.parse(document.getElementById('report-data').textContent);
    const css = getComputedStyle(document.documentElement);
    const colors = {{
      blue: css.getPropertyValue('--blue').trim(),
      green: css.getPropertyValue('--green').trim(),
      red: css.getPropertyValue('--red').trim(),
      amber: css.getPropertyValue('--amber').trim(),
      teal: css.getPropertyValue('--teal').trim(),
      muted: css.getPropertyValue('--muted').trim(),
      line: css.getPropertyValue('--line').trim(),
      ink: css.getPropertyValue('--ink').trim()
    }};

    function setupCanvas(canvas) {{
      const rect = canvas.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.max(1, Math.floor(rect.width * dpr));
      canvas.height = Math.max(1, Math.floor(rect.height * dpr));
      const ctx = canvas.getContext('2d');
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      return {{ctx, w: rect.width, h: rect.height}};
    }}

    function drawAxes(ctx, box, yMin, yMax, yLabel) {{
      ctx.strokeStyle = colors.line;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(box.l, box.t);
      ctx.lineTo(box.l, box.b);
      ctx.lineTo(box.r, box.b);
      ctx.stroke();
      ctx.fillStyle = colors.muted;
      ctx.font = '12px Arial';
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';
      for (let i = 0; i <= 4; i++) {{
        const value = yMin + (yMax - yMin) * i / 4;
        const y = box.b - (box.b - box.t) * i / 4;
        ctx.strokeStyle = colors.line;
        ctx.globalAlpha = 0.55;
        ctx.beginPath();
        ctx.moveTo(box.l, y);
        ctx.lineTo(box.r, y);
        ctx.stroke();
        ctx.globalAlpha = 1;
        ctx.fillText(yLabel(value), box.l - 8, y);
      }}
    }}

    function drawLineChart(canvas, series, opts) {{
      const {{ctx, w, h}} = setupCanvas(canvas);
      ctx.clearRect(0, 0, w, h);
      const box = {{l: 54, r: w - 18, t: 18, b: h - 34}};
      const xs = series.flatMap(s => s.points.map(p => p.x)).filter(Number.isFinite);
      const ys = series.flatMap(s => s.points.map(p => p.y)).filter(Number.isFinite);
      const xMin = Math.min(...xs), xMax = Math.max(...xs);
      let yMin = opts.yMin ?? Math.min(...ys), yMax = opts.yMax ?? Math.max(...ys);
      if (!Number.isFinite(yMin) || !Number.isFinite(yMax) || yMin === yMax) {{ yMin = 0; yMax = 1; }}
      const xScale = x => box.l + (x - xMin) / Math.max(1, xMax - xMin) * (box.r - box.l);
      const yScale = y => box.b - (y - yMin) / Math.max(1e-9, yMax - yMin) * (box.b - box.t);
      drawAxes(ctx, box, yMin, yMax, opts.yLabel || (v => v.toFixed(1)));
      series.forEach(s => {{
        ctx.strokeStyle = s.color;
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        s.points.forEach((p, i) => {{
          const x = xScale(p.x), y = yScale(p.y);
          if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }});
        ctx.stroke();
      }});
      ctx.fillStyle = colors.muted;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      ctx.fillText('iteration', (box.l + box.r) / 2, box.b + 12);
    }}

    function drawBarChart(canvas, rows, opts) {{
      const {{ctx, w, h}} = setupCanvas(canvas);
      ctx.clearRect(0, 0, w, h);
      const box = {{l: 54, r: w - 18, t: 18, b: h - 48}};
      const values = rows.map(r => r.value).filter(Number.isFinite);
      const yMin = 0;
      const yMax = opts.yMax ?? Math.max(1, ...values) * 1.1;
      drawAxes(ctx, box, yMin, yMax, opts.yLabel || (v => v.toFixed(1)));
      const slot = (box.r - box.l) / Math.max(1, rows.length);
      const barW = Math.max(16, Math.min(42, slot * 0.56));
      rows.forEach((row, i) => {{
        const x = box.l + slot * i + slot / 2;
        const y = box.b - (row.value - yMin) / Math.max(1e-9, yMax - yMin) * (box.b - box.t);
        ctx.fillStyle = row.color || colors.green;
        ctx.fillRect(x - barW / 2, y, barW, box.b - y);
        ctx.fillStyle = colors.ink;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.font = '12px Arial';
        ctx.fillText(row.label, x, box.b + 10);
      }});
    }}

    function renderCharts() {{
      const bt = data.bt_series.map(row => ({{
        x: row.iter,
        win_rate: row.win_rate,
        loss_rate: row.loss_rate,
        crash_rate: row.crash_rate,
        ep_wez_steps: row.ep_wez_steps,
        ep_min_distance: row.ep_min_distance
      }}));
      drawLineChart(document.getElementById('btChart'), [
        {{color: colors.green, points: bt.map(r => ({{x: r.x, y: r.win_rate}})).filter(p => p.y != null)}},
        {{color: colors.red, points: bt.map(r => ({{x: r.x, y: r.loss_rate}})).filter(p => p.y != null)}},
        {{color: colors.blue, points: bt.map(r => ({{x: r.x, y: r.crash_rate}})).filter(p => p.y != null)}}
      ], {{yMin: 0, yMax: 1, yLabel: v => Math.round(v * 100) + '%'}});

      const maxWez = Math.max(...bt.map(r => r.ep_wez_steps || 0), 1);
      drawLineChart(document.getElementById('engagementChart'), [
        {{color: colors.amber, points: bt.map(r => ({{x: r.x, y: r.ep_wez_steps}})).filter(p => p.y != null)}},
        {{color: colors.teal, points: bt.map(r => ({{x: r.x, y: (r.ep_min_distance || 0) / 20}})).filter(p => p.y != null)}}
      ], {{yMin: 0, yMax: Math.max(maxWez, 70), yLabel: v => v.toFixed(0)}});

      drawBarChart(document.getElementById('sepChart'), data.separation_runs.map(run => ({{
        label: String(run.separation_m),
        value: (run.tail10.win_rate || 0) * 100,
        color: colors.green
      }})), {{yMax: 100, yLabel: v => Math.round(v) + '%'}});

      const progressRows = data.key_runs.map(run => ({{
        label: run.name.replace('ic_s2_', '').replace('_v1', '').replace('_v2', '').slice(0, 10),
        value: (run.tail10.win_rate || 0) * 100,
        color: (run.tail10.crash_rate || 0) > 0.1 ? colors.red : colors.blue
      }}));
      drawBarChart(document.getElementById('progressChart'), progressRows, {{yMax: 100, yLabel: v => Math.round(v) + '%'}});
    }}

    function renderReplay() {{
      const canvas = document.getElementById('replayCanvas');
      const {{ctx, w, h}} = setupCanvas(canvas);
      const points = data.replay.points || [];
      if (!points.length) return;
      const pad = 34;
      const xs = points.flatMap(p => [p.ox, p.tx]);
      const ys = points.flatMap(p => [p.oy, p.ty]);
      const xMin = Math.min(...xs), xMax = Math.max(...xs);
      const yMin = Math.min(...ys), yMax = Math.max(...ys);
      const scale = Math.min((w - pad * 2) / Math.max(1, xMax - xMin), (h - pad * 2) / Math.max(1, yMax - yMin));
      const cx = (xMin + xMax) / 2;
      const cy = (yMin + yMax) / 2;
      const sx = x => w / 2 + (x - cx) * scale;
      const sy = y => h / 2 - (y - cy) * scale;
      let frame = 0;
      function drawPath(keyX, keyY, color, upto) {{
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.beginPath();
        for (let i = 0; i <= upto; i++) {{
          const p = points[i];
          const x = sx(p[keyX]), y = sy(p[keyY]);
          if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }}
        ctx.stroke();
      }}
      function tick() {{
        const p = points[frame];
        ctx.clearRect(0, 0, w, h);
        ctx.fillStyle = '#101820';
        ctx.fillRect(0, 0, w, h);
        ctx.strokeStyle = 'rgba(255,255,255,0.08)';
        ctx.lineWidth = 1;
        for (let x = 0; x < w; x += 48) {{ ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke(); }}
        for (let y = 0; y < h; y += 48) {{ ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke(); }}
        drawPath('ox', 'oy', '#56a6d6', frame);
        drawPath('tx', 'ty', '#e07464', frame);
        ctx.fillStyle = '#56a6d6';
        ctx.beginPath(); ctx.arc(sx(p.ox), sy(p.oy), 6, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = '#e07464';
        ctx.beginPath(); ctx.arc(sx(p.tx), sy(p.ty), 6, 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = 'rgba(255,255,255,0.34)';
        ctx.setLineDash([5, 5]);
        ctx.beginPath(); ctx.moveTo(sx(p.ox), sy(p.oy)); ctx.lineTo(sx(p.tx), sy(p.ty)); ctx.stroke();
        ctx.setLineDash([]);
        document.getElementById('replayTime').textContent = 't=' + (p.t || 0).toFixed(1) + 's';
        document.getElementById('replayDist').textContent = 'distance=' + Math.round(p.d) + 'm';
        document.getElementById('replayHealth').textContent = 'target health=' + (p.th ?? 0).toFixed(2);
        frame = (frame + 1) % points.length;
        requestAnimationFrame(() => setTimeout(tick, 38));
      }}
      tick();
    }}

    renderCharts();
    renderReplay();
    window.addEventListener('resize', () => {{
      renderCharts();
    }});
  </script>
</body>
</html>
"""


def main() -> None:
    summaries = list_run_summaries()
    if not summaries:
        raise SystemExit(f"No training logs found under {LOG_ROOT}")
    key_runs = build_key_runs(summaries)
    separation_runs = build_separation_runs(summaries)
    current = next((run for run in key_runs if run["name"] == "ic_s3_bt_v1"), None)
    if current is None:
        current = key_runs[-1] if key_runs else summaries[-1]
    data = {
        "current": current,
        "key_runs": key_runs,
        "separation_runs": separation_runs,
        "bt_series": read_series("ic_s3_bt_v1", [
            "win_rate",
            "loss_rate",
            "crash_rate",
            "ep_wez_steps",
            "ep_min_distance",
            "reward_mean",
            "ep_len_mean",
        ]),
        "replay": load_replay("ic_s3_bt_v1"),
    }
    OUT_HTML.write_text(build_html(data), encoding="utf-8")
    print(OUT_HTML)


if __name__ == "__main__":
    main()
