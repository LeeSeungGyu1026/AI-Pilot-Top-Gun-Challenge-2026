from __future__ import annotations

import csv
import json
import math
import argparse
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_ROOT = ROOT / "AIP_LIB" / "DogFightEnv" / "Release_260529"
TEAM_LOG_ROOT = ENV_ROOT / "artifacts" / "logs" / "team01"
TOOLS_ROOT = ENV_ROOT / "tools"
OUT_HTML = ROOT / "reports" / "replay_viewer_3d.html"
MESH_PATH = ENV_ROOT / "assets" / "meshes" / "f16" / "f16_simple_cc_by.obj"
THREE_SOURCE_PATH = ROOT / "reports" / "vendor" / "three.module.min.js"
ORBIT_SOURCE_PATH = ROOT / "reports" / "vendor" / "OrbitControls.js"
MAX_SAMPLES_PER_TRACK = 520

sys.path.insert(0, str(TOOLS_ROOT))

from web_log_viewer.log_data import (  # noqa: E402
    DEFAULT_WEZ_ANGLE_DEG,
    DEFAULT_WEZ_MIN_RANGE_M,
    DEFAULT_WEZ_RANGE_M,
    TRAIL_SECONDS,
    aircraft_display_length_for_extent,
    build_viewer_data,
    parse_obj_mesh,
    scene_extent_m,
)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


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


def as_int(value: object) -> int | None:
    number = as_float(value)
    return None if number is None else int(round(number))


def normalize_path(raw: object) -> Path | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    path = Path(text)
    if path.exists():
        return path
    try:
        rel = text.replace(str(ROOT), "").lstrip("\\/")
        candidate = ROOT / rel
        return candidate if candidate.exists() else None
    except OSError:
        return None


def round_or_none(value: object, digits: int = 3) -> float | None:
    number = as_float(value)
    return None if number is None else round(number, digits)


def sample_indices(length: int, max_samples: int) -> list[int]:
    if length <= 0:
        return []
    stride = max(1, math.ceil(length / max_samples))
    indices = list(range(0, length, stride))
    if indices[-1] != length - 1:
        indices.append(length - 1)
    return indices


def sample_track(track) -> dict[str, list]:
    indices = sample_indices(len(track.time), MAX_SAMPLES_PER_TRACK)
    return {
        "time": [round(track.time[i], 3) for i in indices],
        "position": [
            [
                round(track.position[i][0], 2),
                round(track.position[i][1], 2),
                round(track.position[i][2], 2),
            ]
            for i in indices
        ],
        "rollDeg": [round(track.roll_deg[i], 3) for i in indices],
        "pitchDeg": [round(track.pitch_deg[i], 3) for i in indices],
        "yawDeg": [round(track.yaw_deg[i], 3) for i in indices],
        "health": [
            None
            if not math.isfinite(track.health[i])
            else round(track.health[i], 4)
            for i in indices
        ],
    }


def load_replay(run_name: str, row: dict[str, str]) -> dict | None:
    ownship_log = normalize_path(row.get("ownship_log"))
    target_log = normalize_path(row.get("target_log"))
    if ownship_log is None or target_log is None:
        return None
    summary_path = normalize_path(row.get("summary_json"))
    fallback_end = row.get("end_condition") or "n/a"
    try:
        viewer = build_viewer_data(
            ownship_log=ownship_log,
            target_log=target_log,
            metadata_path=summary_path,
            fallback_end_condition=fallback_end,
        )
    except Exception as exc:
        return {
            "id": f"{run_name}:{row.get('iteration', '?')}:{row.get('episode', '?')}",
            "run": run_name,
            "label": f"load failed: {exc}",
            "error": str(exc),
        }

    extent = scene_extent_m(viewer.ownship, viewer.target)
    start_time = max(viewer.ownship.time[0], viewer.target.time[0])
    end_time = min(viewer.ownship.time[-1], viewer.target.time[-1])
    iteration = as_int(row.get("iteration"))
    episode = as_int(row.get("episode"))
    outcome = row.get("outcome") or "n/a"
    end_condition = row.get("end_condition") or viewer.end_condition
    min_distance = round_or_none(row.get("ep_min_distance"), 1)
    label = (
        f"iter {iteration if iteration is not None else '?':>3} / "
        f"ep {episode if episode is not None else '?'} / "
        f"{outcome}"
    )
    if min_distance is not None:
        label += f" / min {min_distance:.0f}m"
    return {
        "id": f"{run_name}:{iteration}:{episode}",
        "run": run_name,
        "label": label,
        "iteration": iteration,
        "sampledSteps": round_or_none(row.get("sampled_steps"), 0),
        "episode": episode,
        "steps": as_int(row.get("steps")),
        "outcome": outcome,
        "endCondition": end_condition,
        "totalReward": round_or_none(row.get("total_reward"), 3),
        "epMinDistance": min_distance,
        "ownshipHealth": round_or_none(row.get("ownship_health"), 4),
        "targetHealth": round_or_none(row.get("target_health"), 4),
        "startTime": round(start_time, 3),
        "endTime": round(end_time, 3),
        "duration": round(max(0.0, end_time - start_time), 3),
        "sceneExtentM": round(extent, 2),
        "aircraftDisplayLengthM": round(aircraft_display_length_for_extent(extent), 2),
        "ownship": sample_track(viewer.ownship),
        "target": sample_track(viewer.target),
    }


def build_runs(only_run: str | None = None) -> list[dict]:
    runs: list[dict] = []
    for run_dir in sorted(TEAM_LOG_ROOT.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not run_dir.is_dir():
            continue
        if only_run and run_dir.name != only_run:
            continue
        index_path = run_dir / "engagement_replays" / "replay_index.csv"
        rows = read_csv(index_path)
        if not rows:
            continue
        replays = []
        for row in rows:
            replay = load_replay(run_dir.name, row)
            if replay is not None:
                replays.append(replay)
        if not replays:
            continue
        replays.sort(
            key=lambda item: (
                item.get("iteration") if item.get("iteration") is not None else -1,
                item.get("episode") if item.get("episode") is not None else -1,
            ),
            reverse=True,
        )
        outcomes: dict[str, int] = {}
        for replay in replays:
            outcomes[replay.get("outcome", "n/a")] = outcomes.get(replay.get("outcome", "n/a"), 0) + 1
        runs.append(
            {
                "name": run_dir.name,
                "modified": datetime.fromtimestamp(run_dir.stat().st_mtime).isoformat(timespec="seconds"),
                "replayCount": len(replays),
                "outcomes": outcomes,
                "replays": replays,
            }
        )
    return runs


def html_escape_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":")).replace("</", "<\\/")


def build_html(data: dict) -> str:
    json_blob = html_escape_json(data)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    three_source = json.dumps(THREE_SOURCE_PATH.read_text(encoding="utf-8"), ensure_ascii=False).replace("</", "<\\/")
    orbit_source = json.dumps(ORBIT_SOURCE_PATH.read_text(encoding="utf-8"), ensure_ascii=False).replace("</", "<\\/")
    return (
        HTML_TEMPLATE
        .replace("__REPORT_DATA__", json_blob)
        .replace("__GENERATED_AT__", generated_at)
        .replace("__THREE_SOURCE__", three_source)
        .replace("__ORBIT_SOURCE__", orbit_source)
    )


HTML_TEMPLATE = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>3D Dogfight Replay Viewer</title>
  <style>
    :root {
      --bg: #eef1ea;
      --panel: #fbfcf8;
      --ink: #1f292c;
      --muted: #667174;
      --line: #d5dcd3;
      --blue: #2f79c2;
      --red: #c84f4a;
      --green: #31835d;
      --amber: #b87920;
      --scene: #11171b;
      --scene2: #1c2428;
      --shadow: 0 10px 24px rgba(28, 36, 38, 0.12);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      background: var(--bg);
      font-family: Arial, "Malgun Gothic", sans-serif;
      letter-spacing: 0;
      overflow: hidden;
      overflow-x: hidden;
    }
    .app {
      height: 100vh;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
    }
    .toolbar {
      display: grid;
      grid-template-columns: minmax(220px, 1.1fr) minmax(260px, 1.5fr) auto auto auto auto minmax(260px, 1fr);
      gap: 10px;
      align-items: center;
      padding: 10px 12px;
      background: var(--panel);
      border-bottom: 1px solid var(--line);
      box-shadow: var(--shadow);
      z-index: 5;
    }
    .brand {
      font-weight: 700;
      font-size: 16px;
      white-space: nowrap;
    }
    select, button, input[type="range"] {
      font: inherit;
    }
    select {
      width: 100%;
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: white;
      color: var(--ink);
      padding: 8px 10px;
    }
    button {
      border: 1px solid var(--line);
      background: white;
      color: var(--ink);
      border-radius: 6px;
      min-width: 38px;
      min-height: 36px;
      padding: 6px 10px;
      cursor: pointer;
    }
    button:hover, button.active {
      border-color: var(--blue);
      color: var(--blue);
    }
    .speed {
      display: grid;
      grid-template-columns: auto minmax(100px, 150px) 42px;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 13px;
      white-space: nowrap;
    }
    .record-note {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.35;
      min-width: 0;
    }
    .record-note strong {
      color: var(--ink);
      font-weight: 600;
    }
    .workspace {
      min-height: 0;
      display: grid;
      grid-template-columns: minmax(0, 1fr) 330px;
    }
    .scene-area {
      position: relative;
      min-width: 0;
      min-height: 0;
      background: var(--scene);
    }
    #scene-root {
      position: absolute;
      inset: 0;
    }
    .hud {
      position: absolute;
      color: #eef3f0;
      background: rgba(17, 23, 27, 0.74);
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 6px;
      padding: 10px 12px;
      font-family: Consolas, "Courier New", monospace;
      font-size: 13px;
      line-height: 1.45;
      white-space: pre;
      pointer-events: none;
    }
    .hud-left { left: 14px; top: 14px; }
    .hud-right { right: 14px; top: 14px; text-align: right; }
    .timeline {
      position: absolute;
      left: 16px;
      right: 16px;
      bottom: 16px;
      display: grid;
      grid-template-columns: 70px minmax(0, 1fr) 70px;
      gap: 12px;
      align-items: center;
      color: #eef3f0;
      background: rgba(17, 23, 27, 0.76);
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 6px;
      padding: 10px 12px;
      font-family: Consolas, "Courier New", monospace;
      font-size: 13px;
    }
    .side {
      min-height: 0;
      overflow: auto;
      background: var(--panel);
      border-left: 1px solid var(--line);
      padding: 14px;
    }
    .section {
      padding: 12px 0;
      border-bottom: 1px solid var(--line);
    }
    .section:first-child { padding-top: 0; }
    .section:last-child { border-bottom: 0; }
    h1, h2 {
      margin: 0;
      font-size: 15px;
    }
    h2 {
      margin-bottom: 10px;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0;
    }
    .readout {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 8px 12px;
      font-size: 13px;
      line-height: 1.5;
    }
    .readout span { color: var(--muted); }
    .readout strong { text-align: right; }
    .toggles {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px 10px;
      font-size: 13px;
    }
    .toggles label {
      display: flex;
      align-items: center;
      gap: 6px;
      min-height: 28px;
    }
    .camera-buttons {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 6px;
    }
    .camera-buttons button {
      font-size: 13px;
      min-height: 32px;
      padding: 4px 6px;
    }
    .outcome {
      display: inline-block;
      padding: 2px 7px;
      border-radius: 999px;
      background: #edf3ee;
      color: var(--green);
      font-weight: 700;
      font-size: 12px;
    }
    .outcome.loss { color: var(--red); background: #f8eeee; }
    .outcome.timeout { color: var(--amber); background: #f8f0e4; }
    .legend {
      display: grid;
      gap: 8px;
      font-size: 13px;
      color: var(--muted);
    }
    .swatch {
      display: inline-block;
      width: 12px;
      height: 12px;
      border-radius: 50%;
      margin-right: 7px;
      vertical-align: -1px;
    }
    .meta {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
    }
    .error {
      position: absolute;
      inset: 18px;
      display: none;
      place-items: center;
      color: #f6d5d5;
      background: rgba(30, 16, 16, 0.86);
      border: 1px solid rgba(255, 180, 180, 0.25);
      border-radius: 8px;
      padding: 22px;
      text-align: center;
      z-index: 9;
    }
    @media (max-width: 960px) {
      body {
        overflow-y: auto;
        overflow-x: hidden;
      }
      .app { min-height: 100vh; height: auto; }
      .toolbar {
        grid-template-columns: 1fr;
      }
      .workspace {
        grid-template-columns: 1fr;
      }
      .scene-area {
        width: 100vw;
        max-width: 100vw;
        overflow: hidden;
        height: 68vh;
        min-height: 440px;
      }
      .side {
        border-left: 0;
        border-top: 1px solid var(--line);
      }
      .hud {
        font-size: 11px;
        padding: 8px;
      }
      .hud-right {
        left: 14px;
        right: auto;
        top: auto;
        bottom: 72px;
        max-width: calc(100% - 28px);
        text-align: left;
      }
      .timeline {
        left: 14px;
        right: auto;
        width: calc(100vw - 28px);
        grid-template-columns: 44px minmax(0, 1fr);
        gap: 8px;
      }
      #time-end { display: none; }
    }
  </style>
</head>
<body>
  <div class="app">
    <header class="toolbar">
      <h1 class="brand">3D Dogfight Replay Viewer</h1>
      <select id="run-select" aria-label="훈련 선택"></select>
      <select id="replay-select" aria-label="에피소드 선택"></select>
      <button id="play-button" type="button" title="재생/일시정지">Play</button>
      <button id="reset-button" type="button" title="처음으로">Reset</button>
      <button id="record-button" type="button" title="Record current replay as WebM">Record WEBM</button>
      <label class="speed">
        <span>Speed</span>
        <input id="speed-input" type="number" min="0" max="24" step="0.1" value="1.0" inputmode="decimal" aria-label="Playback speed multiplier">
        <strong id="speed-value">1.0x</strong>
      </label>
      <div id="record-save-note" class="record-note" aria-live="polite"></div>
    </header>

    <main class="workspace">
      <section class="scene-area">
        <div id="scene-root"></div>
        <div id="hud-left" class="hud"></div>
        <div id="hud-right" class="hud hud-right"></div>
        <div class="timeline">
          <span id="time-start">0.0s</span>
          <input id="timeline" type="range" min="0" max="1" step="0.001" value="0">
          <span id="time-end">0.0s</span>
        </div>
        <div id="error-box" class="error"></div>
      </section>

      <aside class="side">
        <section class="section">
          <h2>Replay</h2>
          <div class="readout">
            <span>Outcome</span><strong id="outcome-readout"></strong>
            <span>End</span><strong id="end-readout"></strong>
            <span>Iteration</span><strong id="iter-readout"></strong>
            <span>Episode</span><strong id="episode-readout"></strong>
            <span>Steps</span><strong id="steps-readout"></strong>
            <span>Reward</span><strong id="reward-readout"></strong>
            <span>Min Distance</span><strong id="min-distance-readout"></strong>
          </div>
        </section>

        <section class="section">
          <h2>Tactical</h2>
          <div class="readout">
            <span>Range</span><strong id="range-readout"></strong>
            <span>Closure</span><strong id="closure-readout"></strong>
            <span>Rel Alt</span><strong id="relalt-readout"></strong>
            <span>Blue ATA</span><strong id="own-ata-readout"></strong>
            <span>Blue WEZ</span><strong id="own-wez-readout"></strong>
            <span>Red WEZ</span><strong id="target-wez-readout"></strong>
          </div>
        </section>

        <section class="section">
          <h2>View</h2>
          <div class="camera-buttons" role="group" aria-label="카메라 모드">
            <button type="button" data-camera="agent" class="active">Agent Chase</button>
            <button type="button" data-camera="center">Center</button>
            <button type="button" data-camera="blue">Blue</button>
            <button type="button" data-camera="red">Red</button>
          </div>
        </section>

        <section class="section">
          <h2>Display</h2>
          <div class="toggles">
            <label><input id="toggle-trails" type="checkbox" checked> Trails</label>
            <label><input id="toggle-grid" type="checkbox" checked> Grid</label>
            <label><input id="toggle-blue-wez" type="checkbox" checked> Blue WEZ</label>
            <label><input id="toggle-red-wez" type="checkbox" checked> Red WEZ</label>
          </div>
        </section>

        <section class="section">
          <h2>Legend</h2>
          <div class="legend">
            <span><i class="swatch" style="background:var(--blue)"></i>Blue ownship</span>
            <span><i class="swatch" style="background:var(--red)"></i>Red target</span>
            <span><i class="swatch" style="background:var(--amber)"></i>WEZ cone</span>
          </div>
        </section>

        <section class="section">
          <h2>Data</h2>
          <div class="meta" id="data-readout"></div>
        </section>
      </aside>
    </main>
  </div>

  <script id="viewer-data" type="application/json">__REPORT_DATA__</script>
  <script type="module">
    const threeSource = __THREE_SOURCE__;
    const orbitSource = __ORBIT_SOURCE__;
    const threeUrl = URL.createObjectURL(new Blob([threeSource], { type: "text/javascript" }));
    const orbitUrl = URL.createObjectURL(new Blob([
      orbitSource.replace("'./three.module.min.js'", JSON.stringify(threeUrl))
    ], { type: "text/javascript" }));
    const THREE = await import(threeUrl);
    const { OrbitControls } = await import(orbitUrl);

    const DATA = JSON.parse(document.getElementById("viewer-data").textContent);
    const $ = id => document.getElementById(id);
    const css = getComputedStyle(document.documentElement);
    const COLORS = {
      blue: 0x2f79c2,
      red: 0xc84f4a,
      blueTrail: 0x7bb7e6,
      redTrail: 0xee8178,
      blueWez: 0x4d9ce8,
      redWez: 0xf07868,
      grid: 0x93a19a,
      sky: 0xd7e4e4,
      ground: 0xd9dfd1,
      scene: css.getPropertyValue("--scene").trim()
    };
    const MODEL_YAW_OFFSET_DEG = 180;

    const State = {
      run: null,
      replay: null,
      playing: true,
      speed: DATA.defaults.speed || 1,
      simTime: 0,
      lastNow: 0,
      cameraMode: "agent",
      frameCount: 0,
      recording: false
    };

    const Scene = {
      root: $("scene-root"),
      scene: null,
      renderer: null,
      camera: null,
      controls: null,
      aircraftGeometry: null,
      blue: null,
      red: null,
      blueTrail: null,
      redTrail: null,
      blueWez: null,
      redWez: null,
      grid: null,
      blueWezWire: null,
      redWezWire: null
    };

    window.ReplayViewer3D = {
      ready: false,
      framesRendered: 0,
      activeRun: null,
      activeReplay: null,
      webgl: false
    };

    init();

    function init() {
      populateRunSelect();
      bindEvents();
      initScene();
      selectRun(DATA.preferredRun || DATA.runs[0]?.name);
      animate(0);
    }

    function populateRunSelect() {
      const select = $("run-select");
      select.innerHTML = "";
      DATA.runs.forEach(run => {
        const option = document.createElement("option");
        option.value = run.name;
        option.textContent = `${run.name} (${run.replayCount})`;
        select.appendChild(option);
      });
    }

    function bindEvents() {
      $("run-select").addEventListener("change", event => selectRun(event.target.value));
      $("replay-select").addEventListener("change", event => {
        const replay = State.run?.replays.find(item => item.id === event.target.value);
        if (replay) selectReplay(replay);
      });
      $("play-button").addEventListener("click", () => {
        State.playing = !State.playing;
        $("play-button").textContent = State.playing ? "Pause" : "Play";
      });
      $("reset-button").addEventListener("click", () => {
        if (!State.replay) return;
        State.simTime = State.replay.startTime;
        State.playing = false;
        $("play-button").textContent = "Play";
        updateFrame();
      });
      $("record-button").addEventListener("click", recordCurrentReplay);
      $("speed-input").addEventListener("input", event => {
        setPlaybackSpeed(event.target.value);
      });
      $("timeline").addEventListener("input", event => {
        if (!State.replay) return;
        const ratio = Number(event.target.value);
        State.simTime = lerp(State.replay.startTime, State.replay.endTime, ratio);
        State.playing = false;
        $("play-button").textContent = "Play";
        updateFrame();
      });
      $("toggle-trails").addEventListener("change", updateVisibility);
      $("toggle-grid").addEventListener("change", updateVisibility);
      $("toggle-blue-wez").addEventListener("change", updateVisibility);
      $("toggle-red-wez").addEventListener("change", updateVisibility);
      document.querySelectorAll("[data-camera]").forEach(button => {
        button.addEventListener("click", () => {
          State.cameraMode = button.dataset.camera;
          document.querySelectorAll("[data-camera]").forEach(item => item.classList.toggle("active", item === button));
          updateFrame();
        });
      });
      window.addEventListener("resize", resizeRenderer);
    }

    function initScene() {
      Scene.scene = new THREE.Scene();
      Scene.scene.background = new THREE.Color(0xd8e4e3);
      Scene.scene.fog = new THREE.Fog(0xd8e4e3, 8000, 32000);

      Scene.camera = new THREE.PerspectiveCamera(50, 1, 1, 80000);
      Scene.camera.up.set(0, 0, 1);

      Scene.renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
      Scene.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      Scene.renderer.outputColorSpace = THREE.SRGBColorSpace;
      Scene.root.appendChild(Scene.renderer.domElement);
      window.ReplayViewer3D.webgl = Boolean(Scene.renderer.getContext());

      Scene.controls = new OrbitControls(Scene.camera, Scene.renderer.domElement);
      Scene.controls.enableDamping = true;
      Scene.controls.dampingFactor = 0.08;
      Scene.controls.screenSpacePanning = false;

      Scene.scene.add(new THREE.AmbientLight(0xffffff, 0.68));
      const sun = new THREE.DirectionalLight(0xffffff, 1.22);
      sun.position.set(0.4, -0.7, 1.0).normalize();
      Scene.scene.add(sun);

      Scene.aircraftGeometry = buildAircraftGeometry(DATA.mesh);
      resizeRenderer();
    }

    function selectRun(name) {
      const run = DATA.runs.find(item => item.name === name) || DATA.runs[0];
      State.run = run;
      $("run-select").value = run.name;
      const replaySelect = $("replay-select");
      replaySelect.innerHTML = "";
      run.replays.forEach(replay => {
        const option = document.createElement("option");
        option.value = replay.id;
        option.textContent = replay.label;
        replaySelect.appendChild(option);
      });
      selectReplay(run.replays[0]);
    }

    function selectReplay(replay) {
      if (!replay || replay.error) {
        showError(replay?.error || "No replay data");
        return;
      }
      hideError();
      clearReplayObjects();
      State.replay = replay;
      State.simTime = replay.startTime;
      State.playing = true;
      $("play-button").textContent = "Pause";
      $("replay-select").value = replay.id;
      window.ReplayViewer3D.activeRun = State.run.name;
      window.ReplayViewer3D.activeReplay = replay.id;
      setupReplayObjects();
      updateReplayReadout();
      updateRecordSaveNote();
      updateFrame();
      window.ReplayViewer3D.ready = true;
    }

    function setupReplayObjects() {
      const replay = State.replay;
      const blueMat = new THREE.MeshPhongMaterial({ color: COLORS.blue, shininess: 48 });
      const redMat = new THREE.MeshPhongMaterial({ color: COLORS.red, shininess: 48 });
      Scene.blue = new THREE.Mesh(Scene.aircraftGeometry, blueMat);
      Scene.red = new THREE.Mesh(Scene.aircraftGeometry, redMat);
      Scene.scene.add(Scene.blue, Scene.red);

      Scene.blueTrail = makeLine(COLORS.blueTrail);
      Scene.redTrail = makeLine(COLORS.redTrail);
      Scene.scene.add(Scene.blueTrail, Scene.redTrail);

      Scene.blueWez = makeWezMesh(COLORS.blueWez);
      Scene.redWez = makeWezMesh(COLORS.redWez);
      Scene.blueWezWire = makeLine(COLORS.blueWez);
      Scene.redWezWire = makeLine(COLORS.redWez);
      Scene.scene.add(Scene.blueWez, Scene.redWez, Scene.blueWezWire, Scene.redWezWire);

      const bounds = replayBounds(replay);
      const gridSize = Math.max(2500, replay.sceneExtentM * 2.2);
      Scene.grid = new THREE.GridHelper(gridSize, 24, COLORS.grid, COLORS.grid);
      Scene.grid.rotation.x = Math.PI / 2;
      Scene.grid.position.set(bounds.cx, bounds.cy, bounds.minZ - 180);
      Scene.grid.material.opacity = 0.28;
      Scene.grid.material.transparent = true;
      Scene.scene.add(Scene.grid);

      setInitialCamera();
      updateVisibility();
      $("time-start").textContent = `${replay.startTime.toFixed(1)}s`;
      $("time-end").textContent = `${replay.endTime.toFixed(1)}s`;
    }

    function clearReplayObjects() {
      ["blue", "red", "blueTrail", "redTrail", "blueWez", "redWez", "grid", "blueWezWire", "redWezWire"].forEach(key => {
        const object = Scene[key];
        if (!object) return;
        Scene.scene.remove(object);
        disposeObject(object);
        Scene[key] = null;
      });
    }

    function buildAircraftGeometry(mesh) {
      const vertices = [];
      mesh.vertices.forEach(vertex => vertices.push(vertex[0], vertex[1], vertex[2]));
      const indices = [];
      mesh.triangles.forEach(triangle => indices.push(triangle[0], triangle[1], triangle[2]));
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.Float32BufferAttribute(vertices, 3));
      geometry.setIndex(indices);
      geometry.computeVertexNormals();
      return geometry;
    }

    function makeLine(color) {
      return new THREE.Line(
        new THREE.BufferGeometry(),
        new THREE.LineBasicMaterial({
          color,
          linewidth: 2,
          transparent: true,
          opacity: 0.96,
          depthTest: false
        })
      );
    }

    function makeWezMesh(color) {
      return new THREE.Mesh(
        new THREE.BufferGeometry(),
        new THREE.MeshBasicMaterial({
          color,
          transparent: true,
          opacity: 0.24,
          side: THREE.DoubleSide,
          depthWrite: false
        })
      );
    }

    function updateVisibility() {
      if (Scene.blueTrail) Scene.blueTrail.visible = $("toggle-trails").checked;
      if (Scene.redTrail) Scene.redTrail.visible = $("toggle-trails").checked;
      if (Scene.grid) Scene.grid.visible = $("toggle-grid").checked;
      if (Scene.blueWez) Scene.blueWez.visible = $("toggle-blue-wez").checked;
      if (Scene.blueWezWire) Scene.blueWezWire.visible = $("toggle-blue-wez").checked;
      if (Scene.redWez) Scene.redWez.visible = $("toggle-red-wez").checked;
      if (Scene.redWezWire) Scene.redWezWire.visible = $("toggle-red-wez").checked;
    }

    function animate(now) {
      requestAnimationFrame(animate);
      const dt = State.lastNow ? (now - State.lastNow) / 1000 : 0;
      State.lastNow = now;
      if (State.replay && State.playing) {
        State.simTime += dt * State.speed;
        if (State.simTime > State.replay.endTime) {
          State.simTime = State.replay.startTime;
        }
        updateFrame();
      }
      Scene.controls?.update();
      Scene.renderer?.render(Scene.scene, Scene.camera);
      State.frameCount += 1;
      window.ReplayViewer3D.framesRendered = State.frameCount;
    }

    function updateFrame() {
      const replay = State.replay;
      if (!replay || !Scene.blue || !Scene.red) return;
      const bi = nearestIndex(replay.ownship.time, State.simTime);
      const ri = nearestIndex(replay.target.time, State.simTime);
      updateAircraft(Scene.blue, replay.ownship, bi, replay.aircraftDisplayLengthM);
      updateAircraft(Scene.red, replay.target, ri, replay.aircraftDisplayLengthM);
      updateTrail(Scene.blueTrail, replay.ownship);
      updateTrail(Scene.redTrail, replay.target);
      const attackFlash = isBlueAttackFlash(bi, ri);
      updateWez(Scene.blueWez, Scene.blueWezWire, replay.ownship, bi, attackFlash ? 0xffd640 : COLORS.blueWez);
      updateWez(Scene.redWez, Scene.redWezWire, replay.target, ri, COLORS.redWez);
      updateHud(bi, ri);
      updateFollowCamera(bi, ri);
      updateTimeline();
    }

    function updateAircraft(object, track, index, scaleValue) {
      const pos = track.position[index];
      const matrix = aircraftVisualMatrix(track.rollDeg[index], track.pitchDeg[index], track.yawDeg[index]);
      const rot = new THREE.Matrix4().set(
        matrix[0][0], matrix[0][1], matrix[0][2], 0,
        matrix[1][0], matrix[1][1], matrix[1][2], 0,
        matrix[2][0], matrix[2][1], matrix[2][2], 0,
        0, 0, 0, 1
      );
      object.position.set(pos[0], pos[1], pos[2]);
      object.quaternion.setFromRotationMatrix(rot);
      object.scale.setScalar(scaleValue);
    }

    function updateTrail(line, track) {
      if (!line) return;
      const points = [];
      for (let i = 0; i < track.time.length; i += 1) {
        if (track.time[i] <= State.simTime) {
          const p = track.position[i];
          points.push(new THREE.Vector3(p[0], p[1], p[2]));
        }
      }
      line.geometry.dispose();
      line.geometry = new THREE.BufferGeometry().setFromPoints(points);
    }

    function updateWez(mesh, wire, track, index, color) {
      if (!mesh || !wire) return;
      mesh.material.color.setHex(color);
      wire.material.color.setHex(color);
      mesh.material.opacity = color === 0xffd640 ? 0.38 : 0.24;
      const pos = track.position[index];
      const dir = forwardVector(track.yawDeg[index], track.pitchDeg[index]);
      const geometry = buildWezGeometry(
        new THREE.Vector3(pos[0], pos[1], pos[2]),
        new THREE.Vector3(dir[0], dir[1], dir[2]),
        DATA.defaults.wezMinRangeM,
        DATA.defaults.wezRangeM,
        DATA.defaults.wezAngleDeg
      );
      mesh.geometry.dispose();
      mesh.geometry = geometry;
      wire.geometry.dispose();
      wire.geometry = new THREE.WireframeGeometry(geometry);
    }

    function buildWezGeometry(nose, direction, minRange, maxRange, angleDeg) {
      const dir = direction.lengthSq() > 0 ? direction.clone().normalize() : new THREE.Vector3(1, 0, 0);
      const halfAngle = THREE.MathUtils.degToRad(angleDeg / 2);
      const nearRadius = minRange * Math.tan(halfAngle);
      const farRadius = maxRange * Math.tan(halfAngle);
      let ref = new THREE.Vector3(0, 0, 1);
      if (Math.abs(dir.dot(ref)) > 0.98) ref = new THREE.Vector3(0, 1, 0);
      const side = new THREE.Vector3().crossVectors(dir, ref).normalize();
      const up = new THREE.Vector3().crossVectors(side, dir).normalize();
      const nearCenter = nose.clone().addScaledVector(dir, minRange);
      const farCenter = nose.clone().addScaledVector(dir, maxRange);
      const vertices = [];
      const indices = [];
      const resolution = 44;
      for (let step = 0; step < resolution; step += 1) {
        const theta = 2 * Math.PI * step / resolution;
        const radial = side.clone().multiplyScalar(Math.cos(theta)).add(up.clone().multiplyScalar(Math.sin(theta)));
        const nearPoint = nearCenter.clone().addScaledVector(radial, nearRadius);
        const farPoint = farCenter.clone().addScaledVector(radial, farRadius);
        vertices.push(nearPoint.x, nearPoint.y, nearPoint.z, farPoint.x, farPoint.y, farPoint.z);
      }
      for (let step = 0; step < resolution; step += 1) {
        const next = (step + 1) % resolution;
        const nearA = step * 2;
        const farA = nearA + 1;
        const nearB = next * 2;
        const farB = nearB + 1;
        indices.push(nearA, nearB, farB, nearA, farB, farA);
      }
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.Float32BufferAttribute(vertices, 3));
      geometry.setIndex(indices);
      geometry.computeVertexNormals();
      return geometry;
    }

    function updateHud(bi, ri) {
      const replay = State.replay;
      const own = replay.ownship;
      const target = replay.target;
      const ownPos = own.position[bi];
      const targetPos = target.position[ri];
      const relative = sub(targetPos, ownPos);
      const distance = norm(relative);
      const ownForward = forwardVector(own.yawDeg[bi], own.pitchDeg[bi]);
      const targetForward = forwardVector(target.yawDeg[ri], target.pitchDeg[ri]);
      const ownAta = angleBetweenDeg(ownForward, relative);
      const targetAta = angleBetweenDeg(targetForward, scale(relative, -1));
      const closure = distance > 0 ? -dot(relative, sub(velocityAt(target, ri), velocityAt(own, bi))) / distance : 0;
      const ownWez = inWez(distance, ownAta);
      const targetWez = inWez(distance, targetAta);
      const attackFlash = ownWez && isBlueAttackFlash(bi, ri);

      $("hud-left").textContent =
        `${State.playing ? "PLAY" : "PAUSE"}  ${State.simTime.toFixed(2)}s  x${State.speed.toFixed(1)}\\n` +
        `Blue alt ${fmt0(ownPos[2])}m  hp ${fmtHealth(own.health[bi])}\\n` +
        `Red  alt ${fmt0(targetPos[2])}m  hp ${fmtHealth(target.health[ri])}` +
        `${attackFlash ? "\\nATTACK: Blue WEZ flash" : ""}`;
      $("hud-right").textContent =
        `Range     ${fmt0(distance)} m\\n` +
        `Closure   ${fmt1(closure)} m/s\\n` +
        `Rel Alt   ${fmt0(targetPos[2] - ownPos[2])} m\\n` +
        `Blue ATA  ${fmt1(ownAta)} deg\\n` +
        `Blue WEZ  ${ownWez ? "IN" : "out"}\\n` +
        `Red WEZ   ${targetWez ? "IN" : "out"}`;
      $("range-readout").textContent = `${fmt0(distance)} m`;
      $("closure-readout").textContent = `${fmt1(closure)} m/s`;
      $("relalt-readout").textContent = `${fmt0(targetPos[2] - ownPos[2])} m`;
      $("own-ata-readout").textContent = `${fmt1(ownAta)} deg`;
      $("own-wez-readout").textContent = ownWez ? "IN" : "out";
      $("target-wez-readout").textContent = targetWez ? "IN" : "out";
    }

    function updateReplayReadout() {
      const replay = State.replay;
      const outcomeClass = String(replay.outcome || "").toLowerCase();
      $("outcome-readout").innerHTML = `<span class="outcome ${outcomeClass}">${replay.outcome || "n/a"}</span>`;
      $("end-readout").textContent = replay.endCondition || "n/a";
      $("iter-readout").textContent = replay.iteration ?? "n/a";
      $("episode-readout").textContent = replay.episode ?? "n/a";
      $("steps-readout").textContent = replay.steps ?? "n/a";
      $("reward-readout").textContent = formatMaybe(replay.totalReward, 1);
      $("min-distance-readout").textContent = replay.epMinDistance == null ? "n/a" : `${replay.epMinDistance.toFixed(0)} m`;
      $("data-readout").innerHTML =
        `generated: ${DATA.generatedAt}<br>` +
        `runs: ${DATA.runs.length}, replays: ${DATA.replayCount}<br>` +
        `samples: ${replay.ownship.time.length} blue / ${replay.target.time.length} red<br>` +
        `WEZ: ${DATA.defaults.wezMinRangeM.toFixed(1)}-${DATA.defaults.wezRangeM.toFixed(1)} m, ${DATA.defaults.wezAngleDeg.toFixed(1)} deg`;
    }

    function recordFileName(replay = State.replay) {
      if (!replay || !State.run) return "selected_replay_agent_chase.webm";
      const iteration = replay.iteration == null ? "unknown" : String(replay.iteration).padStart(6, "0");
      return `${State.run.name}_${iteration}_agent_chase.webm`;
    }

    function updateRecordSaveNote(extra = "") {
      const note = $("record-save-note");
      if (!note) return;
      note.innerHTML =
        `WEBM 저장 위치: <strong>브라우저 기본 다운로드 폴더</strong> ` +
        `(보통 <strong>C:\\Users\\GYU\\Downloads</strong>)<br>` +
        `파일명: <strong>${recordFileName()}</strong>${extra}`;
    }

    function updateTimeline() {
      const replay = State.replay;
      const denom = replay.endTime - replay.startTime;
      const ratio = denom > 0 ? (State.simTime - replay.startTime) / denom : 0;
      $("timeline").value = String(THREE.MathUtils.clamp(ratio, 0, 1));
    }

    function setInitialCamera() {
      const replay = State.replay;
      const bounds = replayBounds(replay);
      const scaleValue = Math.max(replay.sceneExtentM, DATA.defaults.wezRangeM * 2.6, 1800);
      const focal = new THREE.Vector3(bounds.cx, bounds.cy, bounds.cz);
      Scene.camera.position.set(
        focal.x + 0.52 * scaleValue,
        focal.y - 0.72 * scaleValue,
        focal.z + 0.42 * scaleValue
      );
      Scene.camera.near = 1;
      Scene.camera.far = Math.max(90000, scaleValue * 12);
      Scene.camera.updateProjectionMatrix();
      Scene.controls.target.copy(focal);
      Scene.controls.update();
    }

    function updateFollowCamera(bi, ri) {
      if (State.cameraMode === "agent") {
        updateAgentChaseCamera(bi, ri);
        return;
      }
      const focal = cameraFocalPoint(bi, ri);
      const delta = focal.clone().sub(Scene.controls.target);
      if (delta.lengthSq() < 1e-6) return;
      Scene.camera.position.add(delta);
      Scene.controls.target.copy(focal);
      Scene.controls.update();
    }

    function cameraFocalPoint(bi, ri) {
      const replay = State.replay;
      const blue = replay.ownship.position[bi];
      const red = replay.target.position[ri];
      if (State.cameraMode === "blue") return new THREE.Vector3(blue[0], blue[1], blue[2]);
      if (State.cameraMode === "red") return new THREE.Vector3(red[0], red[1], red[2]);
      return new THREE.Vector3((blue[0] + red[0]) / 2, (blue[1] + red[1]) / 2, (blue[2] + red[2]) / 2);
    }

    function updateAgentChaseCamera(bi, ri) {
      const replay = State.replay;
      const blue = replay.ownship.position[bi];
      const red = replay.target.position[ri];
      const bluePos = new THREE.Vector3(blue[0], blue[1], blue[2]);
      const redPos = new THREE.Vector3(red[0], red[1], red[2]);
      const range = Math.max(1, redPos.distanceTo(bluePos));
      const forward = new THREE.Vector3(...forwardVector(replay.ownship.yawDeg[bi], replay.ownship.pitchDeg[bi])).normalize();
      const worldUp = new THREE.Vector3(0, 0, 1);
      let right = new THREE.Vector3().crossVectors(forward, worldUp);
      if (right.lengthSq() < 1e-6) right = new THREE.Vector3(1, 0, 0);
      right.normalize();
      const backDistance = THREE.MathUtils.clamp(range * 0.74, 380, 680);
      const height = THREE.MathUtils.clamp(range * 0.24, 125, 245);
      const sideOffset = THREE.MathUtils.clamp(range * 0.08, 32, 72);
      const desiredPosition = bluePos.clone()
        .addScaledVector(forward, -backDistance)
        .addScaledVector(worldUp, height)
        .addScaledVector(right, sideOffset);
      const desiredTarget = bluePos.clone().lerp(redPos, 0.74).addScaledVector(worldUp, 28);
      Scene.camera.position.lerp(desiredPosition, 0.34);
      Scene.controls.target.lerp(desiredTarget, 0.44);
      Scene.controls.update();
    }

    function isBlueAttackFlash(bi, ri) {
      const target = State.replay?.target;
      const own = State.replay?.ownship;
      if (!target || !own || ri < 0 || bi < 0) return false;
      if (!isTrackPairInWez(own, target, bi, ri)) return false;
      const next = Math.min(ri + 1, target.time.length - 1);
      return healthDrops(target.health[ri], target.health[next]);
    }

    function healthDrops(before, after) {
      const prev = Number(before);
      const curr = Number(after);
      return Number.isFinite(prev) && Number.isFinite(curr) && curr < prev - 0.0001;
    }

    function isTrackPairInWez(own, target, bi, ri) {
      const ownPos = own.position[bi];
      const targetPos = target.position[ri];
      if (!ownPos || !targetPos) return false;
      const relative = sub(targetPos, ownPos);
      const ownForward = forwardVector(own.yawDeg[bi], own.pitchDeg[bi]);
      return inWez(norm(relative), angleBetweenDeg(ownForward, relative));
    }

    function setPlaybackSpeed(rawValue) {
      const parsed = Number(rawValue);
      if (!Number.isFinite(parsed)) return;
      State.speed = THREE.MathUtils.clamp(parsed, 0, 24);
      $("speed-input").value = String(State.speed);
      $("speed-value").textContent = `${State.speed.toFixed(1)}x`;
    }

    function replayBounds(replay) {
      const points = replay.ownship.position.concat(replay.target.position);
      const xs = points.map(p => p[0]);
      const ys = points.map(p => p[1]);
      const zs = points.map(p => p[2]);
      const minX = Math.min(...xs), maxX = Math.max(...xs);
      const minY = Math.min(...ys), maxY = Math.max(...ys);
      const minZ = Math.min(...zs), maxZ = Math.max(...zs);
      return {
        minX, maxX, minY, maxY, minZ, maxZ,
        cx: (minX + maxX) / 2,
        cy: (minY + maxY) / 2,
        cz: (minZ + maxZ) / 2
      };
    }

    function resizeRenderer() {
      const rect = Scene.root.getBoundingClientRect();
      const width = Math.max(1, Math.floor(rect.width));
      const height = Math.max(1, Math.floor(rect.height));
      Scene.renderer.setSize(width, height, false);
      Scene.camera.aspect = width / height;
      Scene.camera.updateProjectionMatrix();
    }

    function createRecordingCanvas(sourceCanvas) {
      const rect = sourceCanvas.getBoundingClientRect();
      const scale = 2;
      const recordingCanvas = document.createElement("canvas");
      recordingCanvas.width = Math.max(1, Math.floor(rect.width * scale));
      recordingCanvas.height = Math.max(1, Math.floor(rect.height * scale));
      recordingCanvas.dataset.recordingScale = String(scale);
      return recordingCanvas;
    }

    function drawRecordingFrame(recordingCanvas, sourceCanvas) {
      const ctx = recordingCanvas.getContext("2d");
      if (!ctx) return;
      const scale = Number(recordingCanvas.dataset.recordingScale || 1);
      const width = recordingCanvas.width / scale;
      const height = recordingCanvas.height / scale;
      ctx.save();
      ctx.setTransform(scale, 0, 0, scale, 0, 0);
      ctx.clearRect(0, 0, width, height);
      ctx.drawImage(sourceCanvas, 0, 0, width, height);
      drawHudOverlay(ctx, $("hud-left"), "left");
      drawHudOverlay(ctx, $("hud-right"), "right");
      drawTimelineOverlay(ctx);
      ctx.restore();
    }

    function drawHudOverlay(ctx, element, align = "left") {
      if (!element || !element.textContent) return;
      const sceneRect = $("scene-root").getBoundingClientRect();
      const rect = element.getBoundingClientRect();
      const x = rect.left - sceneRect.left;
      const y = rect.top - sceneRect.top;
      drawRoundedBox(ctx, x, y, rect.width, rect.height, 6, "rgba(17,23,27,0.74)", "rgba(255,255,255,0.18)");
      const style = getComputedStyle(element);
      const fontSize = parseFloat(style.fontSize) || 13;
      const lineHeight = parseFloat(style.lineHeight) || fontSize * 1.45;
      ctx.font = `${fontSize}px Consolas, "Courier New", monospace`;
      ctx.fillStyle = "#eef3f0";
      ctx.textBaseline = "top";
      ctx.textAlign = align;
      const paddingX = 12;
      const paddingY = 10;
      const textX = align === "right" ? x + rect.width - paddingX : x + paddingX;
      element.textContent.split("\\n").forEach((line, index) => {
        ctx.fillText(line, textX, y + paddingY + index * lineHeight);
      });
    }

    function drawTimelineOverlay(ctx) {
      const element = document.querySelector(".timeline");
      if (!element) return;
      const sceneRect = $("scene-root").getBoundingClientRect();
      const rect = element.getBoundingClientRect();
      const x = rect.left - sceneRect.left;
      const y = rect.top - sceneRect.top;
      drawRoundedBox(ctx, x, y, rect.width, rect.height, 6, "rgba(17,23,27,0.76)", "rgba(255,255,255,0.18)");
      const startText = $("time-start").textContent || "";
      const endText = $("time-end").textContent || "";
      const ratio = Number($("timeline").value || 0);
      ctx.font = '13px Consolas, "Courier New", monospace';
      ctx.fillStyle = "#eef3f0";
      ctx.textBaseline = "middle";
      ctx.textAlign = "left";
      ctx.fillText(startText, x + 12, y + rect.height / 2);
      ctx.textAlign = "right";
      ctx.fillText(endText, x + rect.width - 12, y + rect.height / 2);
      const trackX = x + 82;
      const trackW = Math.max(24, rect.width - 164);
      const trackY = y + rect.height / 2;
      ctx.strokeStyle = "rgba(238,243,240,0.34)";
      ctx.lineWidth = 4;
      ctx.lineCap = "round";
      ctx.beginPath();
      ctx.moveTo(trackX, trackY);
      ctx.lineTo(trackX + trackW, trackY);
      ctx.stroke();
      ctx.strokeStyle = "#7aa7d9";
      ctx.beginPath();
      ctx.moveTo(trackX, trackY);
      ctx.lineTo(trackX + trackW * THREE.MathUtils.clamp(ratio, 0, 1), trackY);
      ctx.stroke();
      ctx.fillStyle = "#eef3f0";
      ctx.beginPath();
      ctx.arc(trackX + trackW * THREE.MathUtils.clamp(ratio, 0, 1), trackY, 5, 0, Math.PI * 2);
      ctx.fill();
    }

    function drawRoundedBox(ctx, x, y, width, height, radius, fill, stroke) {
      const r = Math.min(radius, width / 2, height / 2);
      ctx.beginPath();
      ctx.moveTo(x + r, y);
      ctx.lineTo(x + width - r, y);
      ctx.quadraticCurveTo(x + width, y, x + width, y + r);
      ctx.lineTo(x + width, y + height - r);
      ctx.quadraticCurveTo(x + width, y + height, x + width - r, y + height);
      ctx.lineTo(x + r, y + height);
      ctx.quadraticCurveTo(x, y + height, x, y + height - r);
      ctx.lineTo(x, y + r);
      ctx.quadraticCurveTo(x, y, x + r, y);
      ctx.closePath();
      ctx.fillStyle = fill;
      ctx.fill();
      ctx.strokeStyle = stroke;
      ctx.lineWidth = 1;
      ctx.stroke();
    }

    function recordCurrentReplay() {
      const button = $("record-button");
      const speedInput = $("speed-input");
      const replay = State.replay;
      const canvas = Scene.renderer?.domElement;
      if (!replay || !canvas || typeof MediaRecorder === "undefined") {
        button.textContent = "Recording unsupported";
        window.setTimeout(() => { button.textContent = "Record WEBM"; }, 1800);
        return;
      }
      const recordingSpeed = Math.max(0.1, Number(State.speed) || 1);
      const previousSpeedInputDisabled = speedInput.disabled;
      State.speed = recordingSpeed;
      speedInput.value = String(recordingSpeed);
      $("speed-value").textContent = `${recordingSpeed.toFixed(1)}x`;
      updateRecordSaveNote(` <br>녹화 배속: <strong>${recordingSpeed.toFixed(1)}x</strong>`);
      const previousPixelRatio = Scene.renderer.getPixelRatio();
      Scene.renderer.setPixelRatio(Math.max(previousPixelRatio, 2));
      resizeRenderer();
      const recordingCanvas = createRecordingCanvas(canvas);
      if (typeof recordingCanvas.captureStream !== "function") {
        Scene.renderer.setPixelRatio(previousPixelRatio);
        resizeRenderer();
        button.textContent = "Recording unsupported";
        window.setTimeout(() => { button.textContent = "Record WEBM"; }, 1800);
        return;
      }
      let compositeFrame = 0;
      const drawComposite = () => {
        drawRecordingFrame(recordingCanvas, canvas);
        if (State.recording) compositeFrame = window.requestAnimationFrame(drawComposite);
      };
      const stream = recordingCanvas.captureStream(60);
      const mimeType = MediaRecorder.isTypeSupported("video/webm;codecs=vp9")
        ? "video/webm;codecs=vp9"
        : "video/webm";
      const recorder = new MediaRecorder(stream, {
        mimeType,
        videoBitsPerSecond: 16000000,
      });
      const chunks = [];
      recorder.addEventListener("dataavailable", event => {
        if (event.data && event.data.size > 0) chunks.push(event.data);
      });
      recorder.addEventListener("stop", () => {
        window.cancelAnimationFrame(compositeFrame);
        stream.getTracks().forEach(track => track.stop());
        const blob = new Blob(chunks, { type: "video/webm" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = recordFileName(replay);
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
        button.disabled = false;
        button.textContent = "Record WEBM";
        speedInput.disabled = previousSpeedInputDisabled;
        Scene.renderer.setPixelRatio(previousPixelRatio);
        resizeRenderer();
        State.recording = false;
        updateRecordSaveNote(" <br>최근 녹화 파일 다운로드를 시작했습니다.");
      });
      State.simTime = replay.startTime;
      State.playing = true;
      $("play-button").textContent = "Pause";
      button.disabled = true;
      speedInput.disabled = true;
      State.recording = true;
      button.textContent = "Recording...";
      drawComposite();
      recorder.start();
      window.setTimeout(
        () => recorder.state === "recording" && recorder.stop(),
        Math.ceil(((replay.duration / recordingSpeed) + 0.35) * 1000)
      );
    }

    function showError(message) {
      const box = $("error-box");
      box.textContent = message;
      box.style.display = "grid";
    }

    function hideError() {
      $("error-box").style.display = "none";
    }

    function disposeObject(object) {
      object.traverse?.(child => {
        child.geometry?.dispose?.();
        if (Array.isArray(child.material)) child.material.forEach(material => material.dispose?.());
        else child.material?.dispose?.();
      });
    }

    function aircraftVisualMatrix(rollDeg, pitchDeg, yawDeg) {
      return matmul3(attitudeMatrix(rollDeg, pitchDeg, yawDeg), zRotationMatrix(MODEL_YAW_OFFSET_DEG));
    }

    function attitudeMatrix(rollDeg, pitchDeg, yawDeg) {
      const roll = THREE.MathUtils.degToRad(rollDeg);
      const pitch = THREE.MathUtils.degToRad(-pitchDeg);
      const yaw = THREE.MathUtils.degToRad(90 - yawDeg);
      const cr = Math.cos(roll), sr = Math.sin(roll);
      const cp = Math.cos(pitch), sp = Math.sin(pitch);
      const cy = Math.cos(yaw), sy = Math.sin(yaw);
      const rotX = [[1, 0, 0], [0, cr, -sr], [0, sr, cr]];
      const rotY = [[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]];
      const rotZ = [[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]];
      return matmul3(matmul3(rotZ, rotY), rotX);
    }

    function zRotationMatrix(deg) {
      const rad = THREE.MathUtils.degToRad(deg);
      const c = Math.cos(rad), s = Math.sin(rad);
      return [[c, -s, 0], [s, c, 0], [0, 0, 1]];
    }

    function matmul3(a, b) {
      const out = [[0, 0, 0], [0, 0, 0], [0, 0, 0]];
      for (let row = 0; row < 3; row += 1) {
        for (let col = 0; col < 3; col += 1) {
          out[row][col] = a[row][0] * b[0][col] + a[row][1] * b[1][col] + a[row][2] * b[2][col];
        }
      }
      return out;
    }

    function forwardVector(yawDeg, pitchDeg) {
      const yaw = THREE.MathUtils.degToRad(yawDeg);
      const pitch = THREE.MathUtils.degToRad(pitchDeg);
      const direction = [
        Math.sin(yaw) * Math.cos(pitch),
        Math.cos(yaw) * Math.cos(pitch),
        Math.sin(pitch),
      ];
      const length = norm(direction);
      return length > 0 ? scale(direction, 1 / length) : [1, 0, 0];
    }

    function nearestIndex(times, value) {
      let low = 0, high = times.length;
      while (low < high) {
        const mid = Math.floor((low + high) / 2);
        if (times[mid] <= value) low = mid + 1;
        else high = mid;
      }
      return Math.max(0, Math.min(low - 1, times.length - 1));
    }

    function velocityAt(track, index) {
      if (track.time.length < 2) return [0, 0, 0];
      const prev = Math.max(0, index - 1);
      const next = Math.min(track.time.length - 1, index + 1);
      const dt = track.time[next] - track.time[prev];
      return dt > 0 ? scale(sub(track.position[next], track.position[prev]), 1 / dt) : [0, 0, 0];
    }

    function angleBetweenDeg(a, b) {
      const an = norm(a), bn = norm(b);
      if (an <= 0 || bn <= 0) return 0;
      const cosine = THREE.MathUtils.clamp(dot(a, b) / (an * bn), -1, 1);
      return THREE.MathUtils.radToDeg(Math.acos(cosine));
    }

    function inWez(rangeM, ataDeg) {
      return rangeM >= DATA.defaults.wezMinRangeM &&
        rangeM <= DATA.defaults.wezRangeM &&
        ataDeg <= Math.max(0, DATA.defaults.wezAngleDeg / 2);
    }

    function sub(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
    function scale(v, s) { return [v[0] * s, v[1] * s, v[2] * s]; }
    function dot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
    function norm(v) { return Math.sqrt(dot(v, v)); }
    function lerp(a, b, t) { return a + (b - a) * t; }
    function fmt0(v) { return Number.isFinite(v) ? v.toFixed(0) : "n/a"; }
    function fmt1(v) { return Number.isFinite(v) ? v.toFixed(1) : "n/a"; }
    function fmtHealth(v) { return v == null ? "n/a" : Number(v).toFixed(3); }
    function formatMaybe(v, digits) { return v == null ? "n/a" : Number(v).toFixed(digits); }
  </script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", default=None, help="Limit the viewer to one run directory under artifacts/logs/team01.")
    parser.add_argument("--out", type=Path, default=OUT_HTML, help="Output HTML path.")
    args = parser.parse_args()

    runs = build_runs(args.run)
    if not runs:
        raise SystemExit(f"No replay_index.csv files found under {TEAM_LOG_ROOT}")
    data = {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "preferredRun": args.run,
        "envRoot": str(ENV_ROOT),
        "teamLogRoot": str(TEAM_LOG_ROOT),
        "replayCount": sum(run["replayCount"] for run in runs),
        "defaults": {
            "speed": 1.0,
            "trailSeconds": TRAIL_SECONDS,
            "wezMinRangeM": DEFAULT_WEZ_MIN_RANGE_M,
            "wezRangeM": DEFAULT_WEZ_RANGE_M,
            "wezAngleDeg": DEFAULT_WEZ_ANGLE_DEG,
        },
        "mesh": parse_obj_mesh(MESH_PATH),
        "runs": runs,
    }
    args.out.write_text(build_html(data), encoding="utf-8")
    print(args.out)
    print(f"runs={len(runs)} replays={data['replayCount']}")


if __name__ == "__main__":
    main()
