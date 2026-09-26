"""
Crucible — Self-Healing CI/CD Agent Dashboard (NiceGUI)
Run with: python app.py
"""

import json
import glob
import os
import subprocess
import sys
from datetime import datetime

# Load .env for local dev (no-op in cloud where env vars are injected directly)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from nicegui import ui, run

REPORTS_DIR = "reports"
HEAL_SCRIPT = os.path.join("scripts", "run_heal.py")

STATUS_MAP = {
    "clean": ("green", "CLEAN"),
    "healed": ("amber", "HEALED"),
    "unresolved": ("red", "UNRESOLVED"),
}
SUCCESS_STATUSES = ("clean", "healed")


def load_reports():
    paths = sorted(glob.glob(os.path.join(REPORTS_DIR, "*.json")))
    out = []
    for p in paths:
        try:
            with open(p) as f:
                d = json.load(f)
                d["_file"] = os.path.basename(p)
                out.append(d)
        except (json.JSONDecodeError, OSError):
            continue
    return out


def demo_reports():
    now = datetime.utcnow().isoformat()
    return [
        {"_file": "heal_demo_1.json", "target": "demo_sandbox/billing_bug", "timestamp": now,
         "status": "healed", "triage": {"result": "KeyError: 'tax_pct' — key mismatch in billing config."},
         "patch": {"original": "tax = amount * config['tax_rate']", "patched": "tax = amount * config['tax_pct']"},
         "verification": {"result": "tests passed"}},
        {"_file": "heal_demo_2.json", "target": "demo_sandbox/trial_1", "timestamp": now,
         "status": "clean", "triage": {"result": "no failures"},
         "patch": {}, "verification": {"result": "no action taken"}},
    ]


reports = reports_sorted = latest = None
total = success = 0
rate = 0.0


def reload_data():
    """(Re)load reports/*.json into module state. Call after a heal run completes."""
    global reports, reports_sorted, latest, total, success, rate
    reports = load_reports() or demo_reports()
    reports_sorted = sorted(reports, key=lambda r: r.get("timestamp", ""), reverse=True)
    latest = reports_sorted[0]
    total = len(reports_sorted)
    success = sum(1 for r in reports_sorted if r.get("status") in SUCCESS_STATUSES)
    rate = round(success / total * 100, 1) if total else 0


reload_data()
state = {"selected": latest}


ui.add_head_html("<style>.q-card{border-radius:10px !important}</style>")


@ui.refreshable
def content():
    r = state["selected"]
    color, label = STATUS_MAP.get(r.get("status", ""), ("red", "UNKNOWN"))

    # Header
    with ui.row().classes("w-full items-stretch gap-4"):
        with ui.card().classes("flex-1 border-l-4 border-primary"):
            ui.label("Crucible").classes("text-2xl font-bold")
            ui.label("Self-Healing CI/CD Agent · Autonomous failure triage & patch generation").classes("text-gray-500 text-sm")
        with ui.card().classes("items-end"):
            ui.label("LATEST STATUS").classes("text-xs text-gray-500")
            top_color, top_label = STATUS_MAP.get(latest.get("status", ""), ("red", "UNKNOWN"))
            ui.badge(top_label, color=top_color).classes("text-sm px-3 py-1")

    # Metrics
    with ui.row().classes("w-full gap-4 mt-4"):
        with ui.card().classes("flex-1"):
            ui.label("TOTAL RUNS").classes("text-xs text-gray-500")
            ui.label(str(total)).classes("text-2xl font-bold")
        with ui.card().classes("flex-1"):
            ui.label("SUCCESS RATE").classes("text-xs text-gray-500")
            ui.label(f"{rate}%").classes("text-2xl font-bold")
        with ui.card().classes("flex-1"):
            ui.label("LAST RUN").classes("text-xs text-gray-500")
            ui.label(latest.get("timestamp", "—")[:19]).classes("text-lg font-bold")

    # Tabs
    with ui.tabs().classes("w-full mt-4") as tabs:
        t_triage = ui.tab("Triage")
        t_patch = ui.tab("Patch")
        t_verify = ui.tab("Verification")
        t_history = ui.tab("History")

    with ui.tab_panels(tabs, value=t_triage).classes("w-full"):
        with ui.tab_panel(t_triage):
            triage = r.get("triage") or {}
            with ui.card().classes("w-full border-l-4 border-primary"):
                ui.label("ROOT CAUSE").classes("text-xs text-gray-500")
                ui.label(triage.get("result", "—")).classes("text-base mt-1")
                ui.label(f"Target: {r.get('target', '—')}").classes("text-sm text-gray-500 mt-2")

        with ui.tab_panel(t_patch):
            patch = r.get("patch") or {}
            if not patch:
                with ui.card().classes("w-full"):
                    ui.label("No patch was generated for this run.").classes("text-gray-500")
            elif "original" in patch and "patched" in patch:
                with ui.row().classes("w-full gap-4"):
                    with ui.card().classes("flex-1"):
                        ui.label("ORIGINAL").classes("text-xs text-gray-500")
                        ui.code(patch.get("original", "—")).classes("w-full")
                    with ui.card().classes("flex-1"):
                        ui.label("PATCHED").classes("text-xs text-gray-500")
                        ui.code(patch.get("patched", "—")).classes("w-full")
            else:
                with ui.card().classes("w-full"):
                    ui.label("PATCH DETAILS").classes("text-xs text-gray-500")
                    ui.code(json.dumps(patch, indent=2)).classes("w-full")

        with ui.tab_panel(t_verify):
            verification = r.get("verification") or {}
            with ui.row().classes("w-full gap-4"):
                with ui.card():
                    ui.label("VERIFICATION RESULT").classes("text-xs text-gray-500")
                    ui.label(label).classes("text-2xl font-bold mt-1")
                    ui.badge(verification.get("result", "—"), color=color)
                with ui.card().classes("flex-1"):
                    ui.label("DETAILS").classes("text-xs text-gray-500")
                    extra = {k: v for k, v in verification.items() if k != "result"}
                    ui.code(json.dumps(extra, indent=2) if extra else "—").classes("w-full")

        with ui.tab_panel(t_history):
            columns = [
                {"name": "timestamp", "label": "Timestamp", "field": "timestamp", "align": "left"},
                {"name": "target", "label": "Target", "field": "target", "align": "left"},
                {"name": "status", "label": "Status", "field": "status", "align": "left"},
            ]
            rows = [
                {"timestamp": x.get("timestamp", ""), "target": x.get("target", ""), "status": x.get("status", "")}
                for x in reports_sorted
            ]
            ui.table(columns=columns, rows=rows).classes("w-full")


def select_report(e):
    state["selected"] = next(x for x in reports_sorted if x["_file"] == e.value)
    content.refresh()


@ui.refreshable
def report_select():
    ui.select(
        {r["_file"]: r["_file"] for r in reports_sorted},
        value=state["selected"]["_file"],
        on_change=select_report,
    ).classes("w-full")


async def run_heal():
    target = target_select.value
    run_button.props("loading")
    run_button.disable()
    try:
        if not os.path.exists(HEAL_SCRIPT):
            ui.notify(f"'{HEAL_SCRIPT}' not found — check your working directory.", type="negative")
            return
        
        # Uses sys.executable to point strictly to the active virtual environment interpreter
        result = await run.io_bound(
            subprocess.run,
            [sys.executable, HEAL_SCRIPT, "--target", target],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode == 0:
            ui.notify("Heal cycle completed", type="positive")
        else:
            ui.notify(result.stderr.strip() or "Heal script failed", type="negative")
    except subprocess.TimeoutExpired:
        ui.notify("Heal script timed out after 300s", type="negative")
    except Exception as e:
        ui.notify(f"Failed to run heal script: {e}", type="negative")
    finally:
        run_button.props(remove="loading")
        run_button.enable()
        reload_data()
        state["selected"] = latest
        content.refresh()
        report_select.refresh()


# ---- Layout ----
with ui.left_drawer().classes("q-pa-md") as drawer:
    ui.label("SETTINGS").classes("text-xs text-gray-500")
    dark = ui.dark_mode(True)
    ui.switch("Dark mode", value=True, on_change=lambda e: dark.set_value(e.value))

    ui.separator().classes("my-3")
    ui.label("REPORT").classes("text-xs text-gray-500")
    report_select()

    ui.separator().classes("my-3")
    ui.label("HEAL").classes("text-xs text-gray-500")

    sandbox_root = "demo_sandbox"
    if os.path.isdir(sandbox_root):
        trial_options = sorted(
            d for d in os.listdir(sandbox_root)
            if os.path.isdir(os.path.join(sandbox_root, d))
        )
    else:
        trial_options = []

    if not trial_options:
        trial_options = ["trial_1", "trial_2", "trial_3"]

    trial_paths = {f"{sandbox_root}/{t}": t for t in trial_options}

    target_select = ui.select(
        trial_paths,
        value=list(trial_paths.keys())[0],
        label="Target path",
    ).classes("w-full")

    run_button = ui.button("Run Heal", on_click=run_heal).classes("w-full mt-2")

with ui.column().classes("w-full max-w-6xl mx-auto p-4"):
    content()

os.makedirs(REPORTS_DIR, exist_ok=True)
port = int(os.environ.get("PORT", 8080))
ui.run(title="Crucible", host="0.0.0.0", port=port, reload=False, show=False)