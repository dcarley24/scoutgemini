# app.py

import os
import json
import sqlite3
import re
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify
# MODIFICATION: Import the new debrief function
from gemini_utils import generate_snapshot, generate_nudge_update, autofill_company_details, generate_debrief

app = Flask(__name__)
DB_PATH = 'scout.db'

# --- Database Initialization ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # MODIFICATION: Added columns for the debrief feature
    c.execute('''
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            industry TEXT,
            size TEXT,
            region TEXT,
            tags TEXT,
            persona TEXT,
            nudge TEXT,
            summary TEXT,
            discovery TEXT,
            raw_notes TEXT,          -- Added for debrief
            debrief_summary TEXT,  -- Added for debrief
            pushed_to_hubspot INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Check if new columns exist and add them if they don't, for backwards compatibility
    try:
        c.execute('SELECT raw_notes FROM snapshots LIMIT 1')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE snapshots ADD COLUMN raw_notes TEXT')
    try:
        c.execute('SELECT debrief_summary FROM snapshots LIMIT 1')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE snapshots ADD COLUMN debrief_summary TEXT')

    conn.commit()
    conn.close()

# MODIFICATION: New route to handle the debrief generation
@app.route('/debrief/<int:snapshot_id>', methods=['POST'])
def debrief(snapshot_id):
    raw_notes = request.form.get('raw_notes')
    if not raw_notes:
        return jsonify({'error': 'No notes provided'}), 400

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM snapshots WHERE id = ?', (snapshot_id,))
    snapshot = c.fetchone()

    if not snapshot:
        conn.close()
        return jsonify({'error': 'Snapshot not found'}), 404

    # Generate the debrief summary using the new utility function
    debrief_summary = generate_debrief(snapshot, raw_notes)

    # Update the database with both the raw notes and the AI-generated summary
    c.execute('UPDATE snapshots SET raw_notes = ?, debrief_summary = ? WHERE id = ?',
              (raw_notes, debrief_summary, snapshot_id))
    conn.commit()
    conn.close()

    # Return the generated summary to be displayed on the page
    return jsonify({'debrief_summary': debrief_summary})


# --- All other routes remain the same ---

def auto_tag(industry, size):
    tags = []
    industry = industry.lower()
    if "health" in industry or "med" in industry:
        tags.append("Compliance Risk")
    if "tech" in industry or "startup" in industry:
        tags.append("Rapid Tech Change")
    if size and any(char.isdigit() for char in size):
        size_num = int(re.sub(r'\D', '', size))
        if size_num > 1000:
            tags.append("Talent Pipeline Issues")
    if not tags:
        tags.append("General Training Need")
    return tags

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        name = request.form['name']
        industry = request.form['industry']
        size = request.form['size']
        region = request.form['region']
        persona = request.form['persona']
        nudge = ""
        tags = auto_tag(industry, size)

        summary, discovery = generate_snapshot(name, industry, size, region, tags, persona)

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
            INSERT INTO snapshots (name, industry, size, region, tags, persona, nudge, summary, discovery, pushed_to_hubspot)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        ''', (name, industry, size, region, ', '.join(tags), persona, nudge, summary, discovery))
        snapshot_id = c.lastrowid
        conn.commit()
        conn.close()

        return redirect(url_for('result', snapshot_id=snapshot_id))

    return render_template('index.html')

@app.route('/nudge/<int:snapshot_id>', methods=['GET', 'POST'])
def nudge(snapshot_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM snapshots WHERE id = ?', (snapshot_id,))
    snapshot = c.fetchone()

    if not snapshot:
        conn.close()
        return "Snapshot not found", 404

    if request.method == 'POST':
        new_nudge = request.form['nudge']
        updated_discovery = generate_nudge_update(snapshot, new_nudge)
        c.execute('UPDATE snapshots SET nudge = ?, discovery = ? WHERE id = ?',
                  (new_nudge, updated_discovery, snapshot_id))
        conn.commit()
        conn.close()
        return redirect(url_for('result', snapshot_id=snapshot_id))

    conn.close()
    return render_template('nudge.html', snapshot=snapshot)

@app.route('/autofill', methods=['POST'])
def autofill():
    name = request.json.get('name')
    if not name:
        return jsonify({'error': 'No name provided'}), 400
    data = autofill_company_details(name)
    if 'error' in data:
        return jsonify(data), 500
    return jsonify(data)

@app.route('/result/<int:snapshot_id>')
def result(snapshot_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM snapshots WHERE id = ?', (snapshot_id,))
    snapshot = c.fetchone()
    conn.close()
    if not snapshot:
        return "Snapshot not found", 404
    return render_template('result.html', snapshot=snapshot)

@app.route('/history')
def history():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM snapshots ORDER BY created_at DESC')
    records = c.fetchall()
    conn.close()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    return render_template('history.html', records=records, now=now)

@app.route('/push/<int:snapshot_id>', methods=['POST'])
def push(snapshot_id):
    return jsonify({'success': True, 'message': 'Push functionality not fully implemented.'})

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5012, debug=True)
