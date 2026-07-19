#!/usr/bin/env python3
"""
app.py
========
A simple local web UI for run_week.py -- drag in files, click a button,
download the schedule. No command line needed once this is running.

HOW TO START IT
----------------
    pip install flask ortools numbers-parser
    python app.py

Then open http://127.0.0.1:5000 in a browser. Leave the terminal window
open while you use it (that's what's actually running the scheduler
behind the scenes) -- it's fine to minimize it.

This runs entirely on your own computer. Nothing is uploaded anywhere
else; files you drop in stay in this folder's uploads/ and state/
directories.
"""

import os
import subprocess
import sys
import uuid
from datetime import datetime

from flask import Flask, request, render_template_string, send_file, redirect, url_for, flash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "schedules")
STATE_DIR = os.path.join(BASE_DIR, "state")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(STATE_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = "local-only-not-sensitive"


def state_file(name):
    return os.path.join(STATE_DIR, name)


def state_status():
    """What's cached and ready to reuse, for display on the home page."""
    checks = {
        "Roster (roles)": state_file("roster.csv"),
        "Hourly rates": state_file("hourly_rates.csv"),
        "Shift requirements": state_file("shift_requirements.csv"),
        "Department targets": state_file("targets.csv"),
        "Leadership pools": state_file("pools.csv"),
        "Presence requirements": state_file("presence_requirements.csv"),
        "Preferred assignments": state_file("preferred_assignments.csv"),
    }
    status = {}
    for label, path in checks.items():
        if os.path.exists(path):
            mtime = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%b %d, %Y %I:%M %p")
            status[label] = f"Ready (updated {mtime})"
        else:
            status[label] = "Not set up yet"
    return status


PAGE = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>The Dwarf House -- Weekly Scheduler</title>
  <style>
    :root { --red: #a11f2f; --cream: #faf6ef; --ink: #2b2420; }
    * { box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--cream); color: var(--ink); margin: 0; padding: 0;
    }
    header {
      background: var(--red); color: white; padding: 24px 32px;
    }
    header h1 { margin: 0; font-size: 22px; font-weight: 600; }
    header p { margin: 4px 0 0; opacity: 0.9; font-size: 14px; }
    .wrap { max-width: 780px; margin: 0 auto; padding: 32px; }
    .card {
      background: white; border-radius: 10px; padding: 24px 28px;
      margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    .card h2 { margin-top: 0; font-size: 17px; }
    .card h2 .badge {
      display: inline-block; font-size: 11px; font-weight: 600;
      padding: 2px 8px; border-radius: 10px; margin-left: 8px; vertical-align: middle;
    }
    .badge.required { background: #fde2e2; color: #a11f2f; }
    .badge.optional { background: #eee; color: #666; }
    label { display: block; font-size: 14px; font-weight: 600; margin-bottom: 6px; }
    .hint { font-size: 13px; color: #777; margin: -2px 0 10px; }
    input[type=file] {
      width: 100%; padding: 10px; border: 1.5px dashed #ccc; border-radius: 8px;
      background: #fafafa; font-size: 13px; margin-bottom: 4px;
    }
    .status-grid { display: grid; grid-template-columns: 1fr auto; gap: 8px 16px; font-size: 14px; }
    .status-grid div:nth-child(odd) { color: #555; }
    .status-grid div:nth-child(even) { font-weight: 600; }
    .ready { color: #1a7a3c; }
    .not-ready { color: #999; }
    details { margin-top: 8px; }
    summary { cursor: pointer; font-size: 14px; font-weight: 600; color: var(--red); padding: 6px 0; }
    button {
      background: var(--red); color: white; border: none; padding: 14px 28px;
      border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; width: 100%;
    }
    button:hover { opacity: 0.92; }
    .flash { background: #fff3cd; border: 1px solid #ffe08a; padding: 12px 16px; border-radius: 8px; margin-bottom: 16px; font-size: 14px; }
    .flash.error { background: #fde2e2; border-color: #f5b5b5; }
    pre {
      background: #1e1e1e; color: #d4d4d4; padding: 16px; border-radius: 8px;
      overflow-x: auto; font-size: 13px; line-height: 1.5; white-space: pre-wrap;
    }
    .download-btn {
      display: inline-block; background: #1a7a3c; color: white; text-decoration: none;
      padding: 14px 28px; border-radius: 8px; font-weight: 600; margin-top: 12px;
    }
    .row { display: flex; gap: 16px; }
    .row label { flex: 1; }
  </style>
</head>
<body>
  <header>
    <h1>Weekly Scheduler</h1>
    <p>The Dwarf House &mdash; drop in this week's files, get a schedule back</p>
  </header>
  <div class="wrap">

    {% with messages = get_flashed_messages(with_categories=true) %}
      {% for category, message in messages %}
        <div class="flash {{ category }}">{{ message }}</div>
      {% endfor %}
    {% endwith %}

    {% if result %}
    <div class="card">
      {% if result_filename %}
        <h2>Done</h2>
        <a class="download-btn" href="{{ url_for('download', filename=result_filename) }}">Download this week's schedule</a>
      {% else %}
        <h2>The run didn't finish -- here's what happened</h2>
      {% endif %}
      <pre>{{ result }}</pre>
      <p><a href="{{ url_for('index') }}">&larr; Back to try again</a></p>
    </div>
    {% else %}

    <form method="post" action="/run" enctype="multipart/form-data">
      <div class="card">
        <h2>This week's availability <span class="badge required">Required every week</span></h2>
        <label for="availability">HotSchedules Availability Report (.csv)</label>
        <div class="hint">The one file you'll always have on hand. Everything else below is reused automatically from last time unless you provide a new one.</div>
        <input type="file" id="availability" name="availability" accept=".csv" required>
      </div>

      <details class="card">
        <summary>Something else changed this week? (roster, pay rates, targets)</summary>
        <br>
        <label for="staff_export">New hires or role changes &rarr; Staff Export (.numbers)</label>
        <input type="file" id="staff_export" name="staff_export" accept=".numbers">
        <br><br>
        <label for="timecard">Pay rates changed &rarr; Timecard Report (.csv)</label>
        <input type="file" id="timecard" name="timecard" accept=".csv">
        <br><br>
        <label for="targets">Department budgets changed &rarr; Hours Target Sheet (.csv)</label>
        <input type="file" id="targets" name="targets" accept=".csv">
      </details>

      <details class="card">
        <summary>Update leadership pools, presence rules, or pinned assignments?</summary>
        <br>
        <label for="pools">Leadership / custom pools (.csv)</label>
        <input type="file" id="pools" name="pools" accept=".csv">
        <br><br>
        <label for="presence">Presence requirements (.csv)</label>
        <input type="file" id="presence" name="presence" accept=".csv">
        <br><br>
        <label for="preferred">Preferred assignments (.csv)</label>
        <input type="file" id="preferred" name="preferred" accept=".csv">
      </details>

      <div class="card">
        <h2>Current setup</h2>
        <div class="status-grid">
          {% for label, status in state_status.items() %}
            <div>{{ label }}</div>
            <div class="{{ 'ready' if 'Ready' in status else 'not-ready' }}">{{ status }}</div>
          {% endfor %}
        </div>
      </div>

      <div class="card">
        <button type="submit">Build this week's schedule</button>
        <p class="hint" style="text-align:center; margin-top:10px;">Usually takes 1&ndash;2 minutes.</p>
      </div>
    </form>

    {% endif %}
  </div>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(PAGE, result=None, state_status=state_status())


@app.route("/run", methods=["POST"])
def run():
    availability = request.files.get("availability")
    if not availability or availability.filename == "":
        flash("Please choose an availability file -- that one's required every week.", "error")
        return redirect(url_for("index"))

    run_id = uuid.uuid4().hex[:8]
    run_upload_dir = os.path.join(UPLOAD_DIR, run_id)
    os.makedirs(run_upload_dir, exist_ok=True)

    def save_if_present(field_name):
        f = request.files.get(field_name)
        if f and f.filename:
            path = os.path.join(run_upload_dir, f.filename)
            f.save(path)
            return path
        return None

    availability_path = save_if_present("availability")
    staff_export_path = save_if_present("staff_export")
    timecard_path = save_if_present("timecard")
    targets_path = save_if_present("targets")
    pools_path = save_if_present("pools")
    presence_path = save_if_present("presence")
    preferred_path = save_if_present("preferred")

    output_filename = f"schedule_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    output_path = os.path.join(OUTPUT_DIR, output_filename)

    cmd = [
        sys.executable, os.path.join(BASE_DIR, "run_week.py"),
        "--new-availability", availability_path,
        "--state-dir", STATE_DIR,
        "--output", output_path,
        "--time-limit", "120",
    ]
    if staff_export_path:
        cmd += ["--new-staff-export", staff_export_path]
    if timecard_path:
        cmd += ["--new-timecard", timecard_path]
    if targets_path:
        cmd += ["--new-targets", targets_path]
    if pools_path:
        cmd += ["--pools", pools_path]
    if presence_path:
        cmd += ["--presence-requirements", presence_path]
    if preferred_path:
        cmd += ["--preferred-assignments", preferred_path]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    output_log = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")

    if proc.returncode != 0 or not os.path.exists(output_path):
        flash("Something went wrong building the schedule -- see the log below.", "error")
        return render_template_string(PAGE, result=output_log, result_filename=None, state_status=state_status())

    return render_template_string(PAGE, result=output_log, result_filename=output_filename, state_status=state_status())


@app.route("/download/<filename>")
def download(filename):
    path = os.path.join(OUTPUT_DIR, filename)
    return send_file(path, as_attachment=True)


if __name__ == "__main__":
    print("\nStarting the scheduler UI...")
    print("Open this in your browser: http://127.0.0.1:5000\n")
    print("Leave this window open while you use it. Press Ctrl+C to stop.\n")
    app.run(debug=False, port=5000)
