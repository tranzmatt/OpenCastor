# Kiosk Robot Face + High-Contrast Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a minimal animated SVG robot face served at `/face`, a high-contrast light theme in the Streamlit dashboard, a kiosk launch script, and systemd services so everything auto-starts on boot.

**Architecture:** The robot face is a standalone HTML page served by FastAPI at `GET /face` (same pattern as `GET /gamepad`). It polls `/api/status` every 500ms via JS to drive reactive animations. Streamlit runs on port 8501 as a separate process. Chromium launches in `--kiosk` mode pointed at `http://localhost:8000/face`. Three systemd user services wire it all together: gateway, dashboard, kiosk.

**Tech Stack:** FastAPI HTMLResponse, SVG + CSS animations, vanilla JS (Fetch API), Streamlit CSS injection, systemd user services, Chromium kiosk mode.

---

## Task 1: High-contrast light theme in dashboard.py

**Files:**
- Modify: `castor/dashboard.py:30-155` (the `<style>` block inside `st.markdown(...)`)

**Step 1: Replace the CSS block**

Find the `st.markdown("""\n<style>` block (line ~30) and replace every color token. The entire `<style>` block becomes:

```css
<style>
  /* ── base light theme ── */
  .stApp { background-color: #f5f7fa !important; color: #0d0d0d !important; }
  #MainMenu, footer, header { visibility: hidden; }

  /* ── desktop padding; tighter on mobile ── */
  .block-container { padding: 0.75rem 1.25rem 1rem !important; max-width: 100% !important; }
  @media (max-width: 768px) {
    .block-container { padding: 0.4rem 0.4rem 0.5rem !important; }
  }

  /* ── touch-friendly buttons (min 48 px tall) ── */
  [data-testid="stButton"] > button {
    min-height: 48px !important;
    font-size: 0.95rem !important;
    touch-action: manipulation;
    border-radius: 8px !important;
    background: #ffffff !important;
    color: #0d0d0d !important;
    border: 1px solid #d0d5dd !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08) !important;
  }
  [data-testid="stChatInput"] textarea { font-size: 1rem !important; }
  [data-testid="stTextInput"] input   { font-size: 1rem !important; min-height: 44px; }

  /* ── D-pad buttons ── */
  [data-testid="stButton"].dpad > button {
    min-height: 68px !important;
    font-size: 1.5rem !important;
    background: #ffffff !important;
    border: 1px solid #d0d5dd !important;
    border-radius: 12px !important;
    box-shadow: 0 2px 6px rgba(0,0,0,0.10) !important;
  }
  [data-testid="stButton"].dpad-stop > button {
    min-height: 68px !important;
    font-size: 1.1rem !important;
    background: #c00000 !important;
    color: #fff !important;
    border: none !important;
    border-radius: 12px !important;
  }

  /* ── metric cards ── */
  [data-testid="stMetric"] {
    background: #ffffff !important;
    border-radius: 8px !important;
    padding: 14px 16px !important;
    border: 1px solid #d0d5dd !important;
    border-left: 3px solid #0057ff !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.07) !important;
  }
  [data-testid="stMetricValue"] { font-size: 1.1rem !important; font-weight: 700 !important; color: #0d0d0d !important; }
  [data-testid="stMetricLabel"] {
    font-size: 0.68rem !important; color: #555f6e !important;
    text-transform: uppercase; letter-spacing: 0.06em;
  }

  /* ── section headers ── */
  .sh {
    color: #0d0d0d; font-size: 0.78rem; font-weight: 700;
    letter-spacing: 0.08em; text-transform: uppercase;
    border-left: 3px solid #0057ff; padding-left: 9px;
    margin: 10px 0 5px 0;
  }
  .sh.g { border-left-color: #007a2f; }
  .sh.o { border-left-color: #b35a00; }
  .sh.r { border-left-color: #c00000; }

  /* ── status bar ── */
  .status-bar {
    background: #ffffff; border: 1px solid #d0d5dd; border-radius: 8px;
    padding: 8px 14px; margin-bottom: 8px; font-family: monospace; font-size: 0.82rem;
    white-space: nowrap; overflow-x: auto; box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    color: #0d0d0d;
  }
  @media (max-width: 768px) { .status-bar { font-size: 0.72rem; padding: 6px 8px; } }

  /* ── status dots ── */
  .dot-g { display:inline-block;width:9px;height:9px;border-radius:50%;
            background:#007a2f;box-shadow:0 0 5px #007a2f;margin-right:3px;}
  .dot-r { display:inline-block;width:9px;height:9px;border-radius:50%;
            background:#c00000;box-shadow:0 0 5px #c00000;margin-right:3px;}
  .dot-y { display:inline-block;width:9px;height:9px;border-radius:50%;
            background:#b35a00;box-shadow:0 0 4px #b35a00;margin-right:3px;}
  .dot-x { display:inline-block;width:9px;height:9px;border-radius:50%;
            background:#9aa3af;margin-right:3px;}

  /* ── sensor badges ── */
  .bw { display:inline-block;background:#e6f4ec;color:#007a2f;border:1px solid #007a2f;
        border-radius:4px;font-size:0.62rem;font-weight:700;padding:1px 6px;text-transform:uppercase;}
  .bm { display:inline-block;background:#fff3e0;color:#b35a00;border:1px solid #b35a00;
        border-radius:4px;font-size:0.62rem;font-weight:700;padding:1px 6px;text-transform:uppercase;}
  .be { display:inline-block;background:#fdecea;color:#c00000;border:1px solid #c00000;
        border-radius:4px;font-size:0.62rem;font-weight:700;padding:1px 6px;text-transform:uppercase;}
  .bx { display:inline-block;background:#f0f1f3;color:#555f6e;border:1px solid #d0d5dd;
        border-radius:4px;font-size:0.62rem;font-weight:700;padding:1px 6px;text-transform:uppercase;}

  /* ── telem row ── */
  .tr { display:flex;align-items:center;gap:8px;padding:7px 10px;border-radius:6px;
        background:#ffffff;border:1px solid #d0d5dd;margin-bottom:5px;font-size:0.82rem;
        box-shadow:0 1px 2px rgba(0,0,0,0.05);}
  .tl { flex:1;font-weight:600;color:#0d0d0d;font-size:0.8rem; }
  .tv { color:#555f6e;font-size:0.76rem; }

  /* ── log terminal (keep dark for readability) ── */
  .log-term {
    background:#111827 !important;border:1px solid #374151 !important;border-radius:8px;
    padding:8px 12px;font-family:"JetBrains Mono","Fira Code","Consolas",monospace !important;
    font-size:0.7rem !important;color:#4ade80 !important;overflow-y:auto;max-height:320px;
  }

  /* ── camera offline pulse ── */
  @keyframes cam-pulse {
    0%,100% { border-color:#c00000; box-shadow:0 0 0px #c00000; }
    50%      { border-color:#ef4444; box-shadow:0 0 8px #c00000; }
  }

  /* ── tab label sizing ── */
  [data-testid="stTabs"] button { font-size: 0.82rem; padding: 8px 10px; color: #0d0d0d !important; }
  @media (max-width: 480px) {
    [data-testid="stTabs"] button { font-size: 0.7rem; padding: 6px 6px; }
  }

  /* ── misc ── */
  [data-testid="stDataFrame"] { font-size: 0.78rem; }
  hr { margin: 0.8rem 0 !important; }

  /* ── back-to-face link ── */
  .face-back {
    display:inline-block;padding:6px 14px;background:#0057ff;color:#fff !important;
    border-radius:8px;text-decoration:none;font-size:0.82rem;font-weight:600;
    box-shadow:0 1px 4px rgba(0,87,255,0.3);
  }
</style>
```

**Step 2: Add "← Robot Face" back link**

After the CSS block and status bar render (around line ~290 where the status bar HTML is built), add a back link at the very top of the page, just before the status bar `st.markdown(...)` call:

```python
# ── back-to-face link ────────────────────────────────────────────────────────
_face_url = f"http://{_host}:8000/face"
st.markdown(
    f'<a class="face-back" href="{_face_url}">← Robot Face</a>',
    unsafe_allow_html=True,
)
```

Where `_host` is derived from `GW` URL: `_host = GW.split("://")[-1].split(":")[0]`.

**Step 3: Update inline color strings**

Search for hardcoded dark hex colors in inline style strings (not the CSS block) and update them:

| Old | New |
|---|---|
| `#0d1117` (backgrounds) | `#f5f7fa` or `#ffffff` |
| `#161b22` | `#ffffff` |
| `#e6edf3` (text) | `#0d0d0d` |
| `#adbac7` (muted text) | `#555f6e` |
| `#8b949e` | `#6b7280` |
| `#58a6ff` (accent blue) | `#0057ff` |
| `#3fb950` (green) | `#007a2f` |
| `#d29922` (amber) | `#b35a00` |
| `#f85149` / `#da3633` (red) | `#c00000` |
| `#30363d` / `#21262d` (borders) | `#d0d5dd` |
| `#1f6feb` (button bg) | `#0057ff` |

Run this search to find all instances:
```bash
grep -n "#0d1117\|#161b22\|#e6edf3\|#adbac7\|#8b949e\|#58a6ff\|#3fb950\|#d29922\|#f85149\|#da3633\|#30363d\|#21262d\|#1f6feb" castor/dashboard.py
```

**Step 4: Syntax-check**
```bash
python3 -c "import ast; ast.parse(open('castor/dashboard.py').read()); print('OK')"
```
Expected: `OK`

**Step 5: Commit**
```bash
git add castor/dashboard.py
git commit -m "feat: high-contrast light theme for dashboard"
```

---

## Task 2: Animated robot face at GET /face in api.py

**Files:**
- Modify: `castor/api.py` — insert after line 4808 (end of `gamepad_page` function)

**Step 1: Insert the /face route**

After the closing `return HTMLResponse(content=_html)` of `gamepad_page` (line 4808), add:

```python
@app.get("/face")
async def robot_face_page(token: str = ""):
    """Animated minimal geometric robot face — kiosk home screen.

    Polls /api/status every 500ms to drive reactive SVG animations.
    Long-press (2 s) anywhere navigates to the Streamlit dashboard (port 8501).
    No auth required (kiosk use).
    """
    from fastapi.responses import HTMLResponse
    _tok = token
    _html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>Castor</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box;}}
  html,body{{width:100%;height:100%;overflow:hidden;background:#f5f7fa;
             display:flex;align-items:center;justify-content:center;
             font-family:system-ui,sans-serif;user-select:none;-webkit-user-select:none;}}
  svg{{max-width:min(90vw,90vh);max-height:min(90vw,90vh);}}

  /* idle breathing glow on head */
  @keyframes breathe{{0%,100%{{filter:drop-shadow(0 0 4px #0057ff88);}}
                       50%{{filter:drop-shadow(0 0 18px #0057ffcc);}}}}
  #head{{animation:breathe 2.8s ease-in-out infinite;}}

  /* blink: eye inner circles scale to 0 vertically */
  @keyframes blink{{0%,90%,100%{{transform:scaleY(1);}}95%{{transform:scaleY(0.05);}}}}
  .eye-inner{{transform-origin:center;animation:blink 4s ease-in-out infinite;}}
  .eye-inner-r{{transform-origin:center;animation:blink 4s ease-in-out infinite 0.07s;}}

  /* mouth oscillation for speaking */
  @keyframes speak{{0%,100%{{d:path("M 155 230 Q 200 250 245 230");}}
                    50%{{d:path("M 155 235 Q 200 210 245 235");}}}}

  /* listening ring pulse */
  @keyframes listen-ring{{0%,100%{{r:130;opacity:0.25;}}50%{{r:145;opacity:0.7;}}}}
  #listen-ring{{display:none;animation:listen-ring 1s ease-in-out infinite;}}

  /* long-press progress ring */
  #lp-ring{{display:none;transform-origin:200px 200px;}}

  /* e-stop red glow */
  @keyframes estop-glow{{0%,100%{{filter:drop-shadow(0 0 8px #c00000);}}
                          50%{{filter:drop-shadow(0 0 28px #c00000);}}}}
  .estop-face{{animation:estop-glow 0.6s ease-in-out infinite;}}
</style>
</head>
<body>
<svg id="face" viewBox="0 0 400 400" xmlns="http://www.w3.org/2000/svg">
  <!-- listening pulse ring (behind head) -->
  <circle id="listen-ring" cx="200" cy="200" r="130" fill="none"
          stroke="#0057ff" stroke-width="4"/>

  <!-- long-press progress ring -->
  <circle id="lp-ring" cx="200" cy="200" r="122" fill="none"
          stroke="#0057ff" stroke-width="5" stroke-dasharray="767" stroke-dashoffset="767"
          stroke-linecap="round" transform="rotate(-90 200 200)"/>

  <!-- head: rounded hexagon via path -->
  <g id="head">
    <path id="head-path"
      d="M 200 70 L 295 115 L 295 285 L 200 330 L 105 285 L 105 115 Z"
      fill="none" stroke="#0057ff" stroke-width="5" stroke-linejoin="round"
      rx="20"/>
  </g>

  <!-- left eye -->
  <g id="eye-l">
    <circle cx="158" cy="185" r="22" fill="none" stroke="#0d0d0d" stroke-width="4"/>
    <circle class="eye-inner" cx="158" cy="185" r="11" fill="#0d0d0d"/>
  </g>

  <!-- right eye -->
  <g id="eye-r">
    <circle cx="242" cy="185" r="22" fill="none" stroke="#0d0d0d" stroke-width="4"/>
    <circle class="eye-inner eye-inner-r" cx="242" cy="185" r="11" fill="#0d0d0d"/>
  </g>

  <!-- mouth: calm arc default -->
  <path id="mouth" d="M 155 230 Q 200 255 245 230"
        fill="none" stroke="#0d0d0d" stroke-width="4" stroke-linecap="round"/>

  <!-- estop X eyes (hidden by default) -->
  <g id="x-eyes" style="display:none">
    <line x1="140" y1="167" x2="176" y2="203" stroke="#c00000" stroke-width="6" stroke-linecap="round"/>
    <line x1="176" y1="167" x2="140" y2="203" stroke="#c00000" stroke-width="6" stroke-linecap="round"/>
    <line x1="224" y1="167" x2="260" y2="203" stroke="#c00000" stroke-width="6" stroke-linecap="round"/>
    <line x1="260" y1="167" x2="224" y2="203" stroke="#c00000" stroke-width="6" stroke-linecap="round"/>
  </g>
</svg>

<script>
const TOKEN = "{_tok}";
const API   = window.location.origin;
const DASH  = "http://" + window.location.hostname + ":8501";
const LP_MS = 2000;
const LP_CIRC = 2 * Math.PI * 122; // stroke-dasharray circumference

// elements
const face      = document.getElementById("face");
const headPath  = document.getElementById("head-path");
const headG     = document.getElementById("head");
const eyeL      = document.getElementById("eye-l");
const eyeR      = document.getElementById("eye-r");
const xEyes     = document.getElementById("x-eyes");
const mouth     = document.getElementById("mouth");
const lpRing    = document.getElementById("lp-ring");
const lsRing    = document.getElementById("listen-ring");
const eyeInners = document.querySelectorAll(".eye-inner");

// state
let state = "idle"; // idle | moving | speaking | listening | estop | offline

function applyState(s) {{
  if (s === state) return;
  state = s;

  // reset
  headG.classList.remove("estop-face");
  xEyes.style.display = "none";
  eyeL.style.display = "block";
  eyeR.style.display = "block";
  lsRing.style.display = "none";
  headPath.setAttribute("stroke", "#0057ff");
  eyeInners.forEach(e => {{ e.style.transform = ""; }});
  mouth.style.animation = "";

  if (s === "idle") {{
    mouth.setAttribute("d", "M 155 230 Q 200 255 245 230");
  }} else if (s === "moving") {{
    // squint: scale eye inners smaller, straighter mouth
    eyeInners.forEach(e => {{
      e.style.transform = "scaleY(0.45)";
      e.style.transformBox = "fill-box";
      e.style.transformOrigin = "center";
    }});
    mouth.setAttribute("d", "M 160 232 Q 200 236 240 232");
  }} else if (s === "speaking") {{
    mouth.style.animation = "speak 0.35s ease-in-out infinite";
  }} else if (s === "listening") {{
    lsRing.style.display = "block";
    // wide eyes: scale inners bigger
    eyeInners.forEach(e => {{
      e.style.transform = "scale(1.3)";
      e.style.transformBox = "fill-box";
      e.style.transformOrigin = "center";
    }});
    mouth.setAttribute("d", "M 160 232 Q 200 236 240 232");
  }} else if (s === "estop") {{
    headPath.setAttribute("stroke", "#c00000");
    headG.classList.add("estop-face");
    xEyes.style.display = "block";
    eyeL.style.display = "none";
    eyeR.style.display = "none";
    mouth.setAttribute("d", "M 155 242 Q 200 222 245 242"); // frown
  }} else if (s === "offline") {{
    headPath.setAttribute("stroke", "#9aa3af");
    eyeInners.forEach(e => e.setAttribute("fill", "#9aa3af"));
    mouth.setAttribute("d", "M 160 232 Q 200 236 240 232");
  }}
}}

// poll API
async function poll() {{
  const headers = TOKEN ? {{"Authorization": "Bearer " + TOKEN}} : {{}};
  try {{
    const r = await fetch(API + "/api/status", {{headers}});
    if (!r.ok) {{ applyState("offline"); return; }}
    const d = await r.json();
    if (d.estop) {{
      applyState("estop");
    }} else if (d.listening) {{
      applyState("listening");
    }} else if (d.speaking) {{
      applyState("speaking");
    }} else if (Math.abs(d.linear||0) > 0.02 || Math.abs(d.angular||0) > 0.02) {{
      applyState("moving");
    }} else {{
      applyState("idle");
    }}
  }} catch(e) {{ applyState("offline"); }}
}}
setInterval(poll, 500);
poll();

// long-press to backstage
let lpTimer = null;
let lpStart = 0;
let lpAnim  = null;

function lpProgress(frac) {{
  const offset = LP_CIRC * (1 - frac);
  lpRing.style.strokeDashoffset = offset;
}}

function lpBegin(e) {{
  e.preventDefault();
  lpStart = Date.now();
  lpRing.style.display = "block";
  lpRing.style.strokeDashoffset = LP_CIRC;
  lpAnim = setInterval(() => {{
    const frac = Math.min((Date.now() - lpStart) / LP_MS, 1);
    lpProgress(frac);
    if (frac >= 1) {{
      clearInterval(lpAnim);
      window.location.href = DASH;
    }}
  }}, 16);
}}

function lpEnd() {{
  clearInterval(lpAnim);
  lpRing.style.display = "none";
}}

document.addEventListener("pointerdown", lpBegin);
document.addEventListener("pointerup",   lpEnd);
document.addEventListener("pointercancel", lpEnd);
</script>
</body>
</html>"""
    return HTMLResponse(content=_html)
```

**Step 2: Syntax-check api.py**
```bash
python3 -c "import ast; ast.parse(open('castor/api.py').read()); print('OK')"
```
Expected: `OK`

**Step 3: Quick smoke test**
```bash
# Start gateway briefly and curl the page
curl -s http://localhost:8000/face | head -5
```
Expected: `<!DOCTYPE html>`

**Step 4: Commit**
```bash
git add castor/api.py
git commit -m "feat: animated geometric robot face at GET /face"
```

---

## Task 3: Kiosk launch script

**Files:**
- Create: `scripts/kiosk.sh`

**Step 1: Write the script**

```bash
#!/usr/bin/env bash
# scripts/kiosk.sh — OpenCastor kiosk launcher
# Waits for gateway + dashboard, then opens Chromium in kiosk mode.
set -euo pipefail

GATEWAY_URL="${OPENCASTOR_GATEWAY_URL:-http://localhost:8000}"
DASH_PORT="${OPENCASTOR_DASH_PORT:-8501}"
FACE_URL="${GATEWAY_URL}/face"
DISPLAY="${DISPLAY:-:0}"

log() { echo "[kiosk] $*"; }

wait_for() {
  local url="$1" label="$2" tries=0
  log "Waiting for $label at $url ..."
  until curl -sf "$url" >/dev/null 2>&1; do
    tries=$((tries+1))
    [ $tries -gt 60 ] && { log "Timeout waiting for $label"; exit 1; }
    sleep 2
  done
  log "$label ready."
}

wait_for "${GATEWAY_URL}/health" "gateway"
wait_for "http://localhost:${DASH_PORT}/_stcore/health" "dashboard"

log "Launching Chromium kiosk → $FACE_URL"
exec chromium-browser \
  --kiosk \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-restore-session-state \
  --no-first-run \
  --disable-features=Translate \
  --app="${FACE_URL}" \
  --display="${DISPLAY}"
```

**Step 2: Make executable**
```bash
chmod +x scripts/kiosk.sh
```

**Step 3: Commit**
```bash
git add scripts/kiosk.sh
git commit -m "feat: kiosk launch script for Chromium robot face"
```

---

## Task 4: Systemd services on Alex

**Files (written directly on Alex, not in git):**
- Create: `~/.config/systemd/user/opencastor-dashboard.service`
- Create: `~/.config/systemd/user/opencastor-kiosk.service`
- Modify: `~/.config/systemd/user/opencastor.service` (add `[Install]` if missing)

**Step 1: Write dashboard service**

SSH to Alex and create:

```ini
# ~/.config/systemd/user/opencastor-dashboard.service
[Unit]
Description=OpenCastor Streamlit Dashboard
After=opencastor.service
Wants=opencastor.service

[Service]
Type=simple
WorkingDirectory=/home/craigm26/OpenCastor
Environment=OPENCASTOR_API_TOKEN=ea3c155db3cdc1a3221a7ebfe683954d85924784a5e87a45accbd848c3497b4f
Environment=OPENCASTOR_GATEWAY_URL=http://localhost:8000
ExecStart=/home/craigm26/opencastor-env/bin/python -m streamlit run \
    /home/craigm26/OpenCastor/castor/dashboard.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.fileWatcherType none \
    --server.headless true
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

**Step 2: Write kiosk service**

```ini
# ~/.config/systemd/user/opencastor-kiosk.service
[Unit]
Description=OpenCastor Kiosk (Chromium robot face)
After=opencastor-dashboard.service graphical-session.target
Wants=opencastor-dashboard.service graphical-session.target

[Service]
Type=simple
WorkingDirectory=/home/craigm26/OpenCastor
Environment=DISPLAY=:0
Environment=OPENCASTOR_API_TOKEN=ea3c155db3cdc1a3221a7ebfe683954d85924784a5e87a45accbd848c3497b4f
Environment=OPENCASTOR_GATEWAY_URL=http://localhost:8000
ExecStart=/home/craigm26/OpenCastor/scripts/kiosk.sh
Restart=on-failure
RestartSec=10

[Install]
WantedBy=graphical-session.target
```

**Step 3: Enable all three services on Alex**

```bash
ssh craigm26@alex.local "
  systemctl --user daemon-reload
  systemctl --user enable opencastor.service opencastor-gamepad.service opencastor-dashboard.service opencastor-kiosk.service
  systemctl --user start opencastor-dashboard.service
  systemctl --user start opencastor-kiosk.service
  systemctl --user status opencastor-dashboard.service opencastor-kiosk.service --no-pager
"
```

Expected: both show `active (running)`.

**Step 4: Enable lingering so user services survive logout/reboot**

```bash
ssh craigm26@alex.local "loginctl enable-linger craigm26"
```

**Step 5: Verify on reboot**

```bash
ssh craigm26@alex.local "sudo reboot"
# Wait ~30s
ssh craigm26@alex.local "systemctl --user status opencastor.service opencastor-dashboard.service opencastor-kiosk.service --no-pager | grep -E 'Active|Loaded'"
```

Expected: all three `Active: active (running)`.

---

## Task 5: Push and deploy

**Step 1: Push to GitHub**
```bash
git push origin main
```

**Step 2: Pull on Alex**
```bash
ssh craigm26@alex.local "cd ~/OpenCastor && git pull --ff-only"
```

**Step 3: Restart gateway to pick up new /face route**
```bash
ssh craigm26@alex.local "systemctl --user restart opencastor.service"
```

**Step 4: Smoke-test the face page from your machine**
```bash
curl -s http://alex.local:8000/face | grep -c "DOCTYPE"
```
Expected: `1`

**Step 5: Final verify — open in browser**

Navigate to `http://alex.local:8000/face` and confirm:
- Geometric face renders with hexagon head, two eyes, arc mouth
- Long-press 2 seconds shows a blue progress ring, then navigates to `:8501`
- Dashboard has white background with dark text
- `← Robot Face` link appears at top of dashboard
