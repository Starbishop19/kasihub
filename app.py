from flask import Flask, render_template, request, jsonify, session
import sqlite3
import requests
import os
import hashlib
import secrets

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

def get_db():
    conn = sqlite3.connect('kasihub.db')
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.sha256((password + salt).encode()).hexdigest()
    return salt, h

def verify_password(password, salt, stored_hash):
    _, h = hash_password(password, salt)
    return h == stored_hash

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"status": "error", "message": "not logged in"}), 401
        return f(*args, **kwargs)
    return decorated

def role_required(*roles):
    from functools import wraps
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_id' not in session:
                return jsonify({"status": "error", "message": "not logged in"}), 401
            if session['role'] not in roles:
                return jsonify({"status": "error", "message": "forbidden"}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator

def setup():
    db = get_db()
    c = db.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT UNIQUE,
                  password_salt TEXT,
                  password_hash TEXT,
                  water_level INTEGER,
                  power_status TEXT,
                  location TEXT,
                  role TEXT DEFAULT 'community')''')
    c.execute('''CREATE TABLE IF NOT EXISTS stores 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, type TEXT, 
                  has_power INTEGER, has_water INTEGER, location TEXT, owner_user_id INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS reports 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, issue TEXT, status TEXT, user TEXT, 
                  category TEXT DEFAULT 'other', location TEXT, lat REAL, lng REAL, 
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS outages 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, area TEXT, start_time TEXT, 
                  end_time TEXT, stage TEXT, notes TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS services 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, type TEXT, phone TEXT, 
                  address TEXT, is_open INTEGER DEFAULT 1)''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_reports_cat ON reports(category)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_users_loc ON users(location)')
    db.commit()
    db.close()

def seed():
    db = get_db()
    c = db.cursor()
    if c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        print("Seeding database...")
        admin_users = [
            ('Sipho', '12345', 'community', 85, 'online', 'Diepsloot West'),
            ('Nomsa', '12345', 'community', 40, 'scheduled_off', 'Diepsloot North'),
            ('Boxer Manager', 'boxer2024', 'business', 100, 'online', 'Diepsloot Central'),
            ('SAPS Officer', 'saps99', 'public_service', 100, 'online', 'Diepsloot Station')
        ]
        for name, pw, role, wl, ps, loc in admin_users:
            salt, h = hash_password(pw)
            c.execute("INSERT INTO users (name, password_salt, password_hash, water_level, power_status, location, role) VALUES (?,?,?,?,?,?,?)",
                      (name, salt, h, wl, ps, loc, role))
        db.commit()
        c.execute("SELECT id, name FROM users")
        user_map = {row['name']: row['id'] for row in c.fetchall()}
        boxer_id = user_map.get('Boxer Manager')
        stores = [
            ('Boxer Diepsloot', 'supermarket', 1, 1, 'Diepsloot West', boxer_id),
            ('Shoprite Checkers', 'supermarket', 1, 1, 'Diepsloot West', None),
            ('Local Spaza', 'spaza', 0, 1, 'Diepsloot East', None)
        ]
        for s in stores:
            c.execute("INSERT INTO stores (name, type, has_power, has_water, location, owner_user_id) VALUES (?,?,?,?,?,?)", s)
        reports = [
            ('Transformer blew up near Zone 1', 'open', 'Sipho', 'power', 'Zone 1', -25.9867, 28.0167),
            ('Water truck delayed at Stand 4', 'open', 'Nomsa', 'water', 'Stand 4', -25.9821, 28.0245),
            ('Suspicious vehicle spotted', 'open', 'SAPS Officer', 'crime', 'Station Area', -25.9899, 28.0112)
        ]
        for r in reports:
            c.execute("INSERT INTO reports (issue, status, user, category, location, lat, lng) VALUES (?,?,?,?,?,?,?)", r)
        outages = [
            ('power', 'Diepsloot West', 'Mon 18:00', 'Mon 21:00', 'Stage 4', 'Feeder 12 down'),
            ('power', 'Diepsloot North', 'Tue 06:00', 'Tue 09:00', 'Stage 2', 'Substation maintenance'),
            ('power', 'Diepsloot East', 'Wed 17:30', 'Wed 20:30', 'Stage 4', 'Rotating load shedding'),
            ('water', 'Zone 3 & 4', 'Thu 08:00', 'Fri 16:00', 'High pressure', 'Pipe replacement work'),
            ('water', 'Stand 1-6', 'Sat 00:00', 'Sun 23:59', 'Low pressure', 'Booster pump repair'),
        ]
        for o in outages:
            c.execute("INSERT INTO outages (type, area, start_time, end_time, stage, notes) VALUES (?,?,?,?,?,?)", o)
        services = [
            ('Diepsloot SAPS', 'police', '011 704 3000', 'Plot 1234, Main Rd', 1),
            ('Diepsloot Clinic', 'clinic', '011 704 3150', 'Corner of Ext 4', 1),
            ('Fire & Rescue', 'fire', '10177', 'Sandton Dispatch', 1),
            ('Ambulance (ER24)', 'ambulance', '082 911', 'National', 1),
            ('Electricity Faults', 'utility', '0860 437 111', 'Joburg City Power', 1),
            ('Water Emergencies', 'utility', '0860 111 911', 'Joburg Water', 1),
            ('Social Development', 'social', '0800 220 250', 'Child Welfare Line', 1),
        ]
        for s in services:
            c.execute("INSERT INTO services (name, type, phone, address, is_open) VALUES (?,?,?,?,?)", s)
        db.commit()
    db.close()

setup()
seed()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    if not username or not password:
        return jsonify({"status": "error", "message": "Username and password required"}), 400
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE name = ?', (username,)).fetchone()
    db.close()
    if not user:
        return jsonify({"status": "error", "message": "Invalid credentials"}), 401
    if not verify_password(password, user['password_salt'], user['password_hash']):
        return jsonify({"status": "error", "message": "Invalid credentials"}), 401
    session['user_id'] = user['id']
    session['username'] = user['name']
    session['role'] = user['role']
    session['location'] = user['location']
    return jsonify({
        "status": "success", "username": user['name'], "role": user['role'],
        "location": user['location'], "id": user['id']
    })

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    location = data.get('location', '').strip()
    role = data.get('role', 'community')
    if not username or not password or not location:
        return jsonify({"status": "error", "message": "All fields required"}), 400
    if len(password) < 6:
        return jsonify({"status": "error", "message": "Password must be at least 6 chars"}), 400
    if role not in ['community', 'business', 'public_service']:
        return jsonify({"status": "error", "message": "Invalid role"}), 400
    salt, h = hash_password(password)
    db = get_db()
    try:
        db.execute("INSERT INTO users (name, password_salt, password_hash, water_level, power_status, location, role) VALUES (?,?,?,?,?,?,?)",
                   (username, salt, h, 60, 'online', location, role))
        db.commit()
        new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    except sqlite3.IntegrityError:
        db.close()
        return jsonify({"status": "error", "message": "Username already taken"}), 409
    db.close()
    session['user_id'] = new_id
    session['username'] = username
    session['role'] = role
    session['location'] = location
    return jsonify({"status": "success", "user_id": new_id, "username": username})

@app.route('/api/logout')
def logout():
    session.clear()
    return jsonify({"status": "ok"})

@app.route('/api/profile')
@login_required
def get_profile():
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    db.close()
    return jsonify(dict(user))

@app.route('/api/predict-risk/<int:user_id>')
@login_required
def risk_check(user_id):
    if user_id != session['user_id'] and session['role'] != 'public_service':
        return jsonify({"status": "error", "message": "forbidden"}), 403
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    db.close()
    if not user:
        return jsonify({"status": "error", "message": "no user found"}), 404
    score = 0; tips = []
    if user['water_level'] < 50:
        days = int(user['water_level'] / 10)
        score += 30; tips.append(f"⚠️ Water Critical: ~{days} days left.")
    if user['power_status'] == 'scheduled_off':
        score += 40; tips.append("🔋 Power Drop Imminent: Charge devices NOW.")
    if 'Diepsloot' in user['location']:
        score += 20; tips.append("🌍 High Outage Density in area.")
    score = min(score, 100)
    sev = 'low'
    if score > 70: sev = 'high'
    elif score > 40: sev = 'medium'
    return jsonify({"status": "success", "user": user['name'], "risk_score": score, "severity": sev, "predictions": tips, "next_action": "Share Resources" if score > 50 else "Monitor Status"})

@app.route('/api/find-resources/<location>')
@login_required
def find_helpers(location):
    db = get_db()
    helpers = db.execute('SELECT name, water_level, power_status FROM users WHERE location LIKE ? AND water_level > 80', (f'%{location}%',)).fetchall()
    db.close()
    return jsonify([dict(h) for h in helpers])

@app.route('/api/stores')
@login_required
def get_stores():
    db = get_db()
    stores = db.execute('SELECT * FROM stores').fetchall()
    db.close()
    return jsonify([dict(s) for s in stores])

@app.route('/api/store/<int:sid>/status', methods=['POST'])
@role_required('business')
def update_store(sid):
    db = get_db()
    store = db.execute('SELECT * FROM stores WHERE id = ?', (sid,)).fetchone()
    if not store:
        db.close()
        return jsonify({"status": "error", "message": "Store not found"}), 404
    if store['owner_user_id'] and store['owner_user_id'] != session['user_id']:
        db.close()
        return jsonify({"status": "error", "message": "Not your store"}), 403
    data = request.get_json()
    db.execute('UPDATE stores SET has_power = ?, has_water = ? WHERE id = ?', (1 if data.get('has_power') else 0, 1 if data.get('has_water') else 0, sid))
    db.commit(); db.close()
    return jsonify({"status": "ok"})

@app.route('/api/reports')
@login_required
def get_reports():
    category = request.args.get('category')
    db = get_db()
    if category:
        rows = db.execute('SELECT * FROM reports WHERE category = ? ORDER BY id DESC LIMIT 50', (category,)).fetchall()
    else:
        rows = db.execute('SELECT * FROM reports ORDER BY id DESC LIMIT 50').fetchall()
    db.close()
    if session['role'] == 'public_service':
        return jsonify([dict(r) for r in rows])
    return jsonify([{"status": r["status"], "id": r["id"], "issue": r["issue"], "user": r["user"], "category": r["category"], "location": r["location"], "timestamp": r["timestamp"]} for r in rows])

@app.route('/api/report', methods=['POST'])
@login_required
def add_report():
    data = request.get_json()
    issue = data.get('issue', '').strip()
    if not issue:
        return jsonify({"status": "error", "message": "need an issue"}), 400
    if len(issue) > 500:
        return jsonify({"status": "error", "message": "issue too long"}), 400
    category = data.get('category', 'other')
    location = data.get('location') or session['location']
    lat = data.get('lat') or -25.9867
    lng = data.get('lng') or 28.0167
    db = get_db()
    c = db.cursor()
    c.execute('INSERT INTO reports (issue, status, user, category, location, lat, lng) VALUES (?, ?, ?, ?, ?, ?, ?)', (issue, 'open', session['username'], category, location, lat, lng))
    db.commit()
    new_id = c.lastrowid
    db.close()
    return jsonify({"status": "ok", "id": new_id})

@app.route('/api/report/<int:rid>/resolve', methods=['POST'])
@role_required('public_service')
def resolve_report(rid):
    db = get_db()
    c = db.cursor()
    c.execute('UPDATE reports SET status = ? WHERE id = ?', ('resolved', rid))
    if c.rowcount == 0:
        db.commit()
        db.close()
        return jsonify({"status": "error", "message": "report not found"}), 404
    db.commit(); db.close()
    return jsonify({"status": "ok"})

@app.route('/api/map-dots')
@login_required
def map_dots():
    if session['role'] != 'public_service':
        return jsonify([]), 200
    db = get_db()
    rows = db.execute('SELECT id, issue, category, location, lat, lng FROM reports WHERE status = "open"').fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/outages')
@login_required
def get_outages():
    otype = request.args.get('type')
    db = get_db()
    if otype:
        rows = db.execute('SELECT * FROM outages WHERE type = ? ORDER BY id', (otype,)).fetchall()
    else:
        rows = db.execute('SELECT * FROM outages ORDER BY id').fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/services')
@login_required
def get_services():
    stype = request.args.get('type')
    db = get_db()
    if stype:
        rows = db.execute('SELECT * FROM services WHERE type = ? ORDER BY name', (stype,)).fetchall()
    else:
        rows = db.execute('SELECT * FROM services ORDER BY type, name').fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/weather')
def get_weather():
    lat = -25.9867; lon = 28.0167
    api_key = os.getenv('OPENWEATHER_KEY', '')
    if not api_key:
        return jsonify({"temp": 25, "desc": "Clear Sky", "warning": "None"})
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=metric"
        r = requests.get(url, timeout=5); r.raise_for_status()
        data = r.json()
        temp = data['main']['temp']; desc = data['weather'][0]['description']
        warning = "None"
        if temp > 32: warning = "Heatwave Warning"
        elif 'rain' in desc or 'thunder' in desc: warning = "Storm Warning"
        return jsonify({"temp": round(temp), "desc": desc, "warning": warning})
    except Exception as e:
        print(e); return jsonify({"status": "error", "message": "Weather API failed"})

@app.route('/api/users')
@login_required
def get_users():
    db = get_db()
    users = db.execute('SELECT id, name, location, water_level, power_status FROM users').fetchall()
    db.close()
    return jsonify([dict(u) for u in users])

@app.route('/api/water-level', methods=['POST'])
@login_required
def update_water():
    data = request.get_json()
    try:
        level = int(data.get('water_level', 50))
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "water_level must be a number"}), 400
    level = max(0, min(100, level))
    db = get_db()
    db.execute('UPDATE users SET water_level = ? WHERE id = ?', (level, session['user_id']))
    db.commit(); db.close()
    return jsonify({"status": "ok", "water_level": level})

@app.route('/api/stats')
@login_required
def get_stats():
    db = get_db()
    user = db.execute('SELECT water_level, power_status FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    c = db.cursor()
    c.execute('SELECT COUNT(*) FROM users'); user_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM reports WHERE status = 'open'"); open_reports = c.fetchone()[0]
    db.close()
    risk = 0
    if user['water_level'] < 50: risk += 50
    if user['power_status'] == 'scheduled_off': risk += 30
    return jsonify({"status": "success", "users": user_count, "reports": open_reports, "water": user['water_level'], "power": user['power_status'], "risk_score": risk})

@app.route('/api/business-profile')
@login_required
def business_profile():
    db = get_db()
    loc = session['location']
    stores = db.execute('SELECT * FROM stores ORDER BY id').fetchall()
    total_crime = db.execute("SELECT COUNT(*) FROM reports WHERE category = 'crime'").fetchone()[0]
    resolved_crime = db.execute("SELECT COUNT(*) FROM reports WHERE category = 'crime' AND status = 'resolved'").fetchone()[0]
    zones = ['Diepsloot West', 'Diepsloot North', 'Diepsloot East', 'Diepsloot Central']
    zone_stats = []
    for z in zones:
        cnt = db.execute("SELECT COUNT(*) FROM reports WHERE category = 'crime' AND location LIKE ?", (f'%{z}%',)).fetchone()[0]
        base = {'Diepsloot West': 12, 'Diepsloot North': 18, 'Diepsloot East': 9, 'Diepsloot Central': 22}.get(z, 10)
        rate = base + (cnt * 3)
        zone_stats.append({"zone": z, "burglary_rate": rate, "trend": "up" if cnt > 0 else "stable", "level": "high" if rate > 25 else ("medium" if rate > 15 else "low")})
    db.close()
    return jsonify({"status": "success", "stores": [dict(s) for s in stores], "crime_total": total_crime, "crime_resolved": resolved_crime, "zones": zone_stats, "user_location": loc})

if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG') == '1'
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=debug_mode)