from flask import Flask, render_template, request, jsonify, session
import sqlite3
import requests
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'kasihub_secret_dev_key_123')

def get_db():
    conn = sqlite3.connect('kasihub.db')
    conn.row_factory = sqlite3.Row
    return conn

def setup():
    db = get_db()
    c = db.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT, water_level INTEGER, power_status TEXT, location TEXT, role TEXT DEFAULT 'community')''')
    # Added owner_user_id column
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
    
    # Add indexes
    c.execute('CREATE INDEX IF NOT EXISTS idx_reports_cat ON reports(category)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_users_loc ON users(location)')
    
    db.commit()
    db.close()

def seed():
    db = get_db()
    c = db.cursor()
    
    # Seed Users
    if c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        print("Seeding database...")
        users = [
            ('Sipho', 85, 'online', 'Diepsloot West', 'community'),
            ('Nomsa', 40, 'scheduled_off', 'Diepsloot North', 'community'),
            ('Boxer Manager', 100, 'online', 'Diepsloot Central', 'business'),
            ('SAPS Officer', 100, 'online', 'Diepsloot Station', 'public_service')
        ]
        for u in users:
            c.execute("INSERT INTO users (name, water_level, power_status, location, role) VALUES (?,?,?,?,?)", u)
        db.commit() # Commit users first so we can get their IDs

        # Get IDs for ownership mapping
        c.execute("SELECT id, name FROM users")
        user_map = {row['name']: row['id'] for row in c.fetchall()}
        boxer_id = user_map.get('Boxer Manager')

        stores = [
            ('Boxer Diepsloot', 'supermarket', 1, 1, 'Diepsloot West', boxer_id),
            ('Shoprite Checkers', 'supermarket', 1, 1, 'Diepsloot West', None), # Community store
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
    username = data.get('username')
    role = data.get('role')
    if not username: return jsonify({"status": "error", "message": "Username required"}), 400
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE name = ? AND role = ?', (username, role)).fetchone()
    db.close()
    if user:
        session['user_id'] = user['id']
        session['username'] = user['name']
        session['role'] = user['role']
        session['location'] = user['location']
        return jsonify({"status": "success", "username": user['name'], "role": user['role'], "location": user['location'], "id": user['id']})
    return jsonify({"status": "error", "message": "Invalid credentials"}), 401

@app.route('/api/logout')
def logout():
    session.clear()
    return jsonify({"status": "ok"})

@app.route('/api/profile')
def get_profile():
    if 'user_id' not in session: return jsonify({"status": "error", "message": "not logged in"}), 401
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    db.close()
    return jsonify(dict(user))

@app.route('/api/predict-risk/<int:user_id>')
def risk_check(user_id):
    if 'user_id' not in session: return jsonify({"status": "error", "message": "not logged in"}), 401
    # Security: Users can only check their own risk unless they are public_service
    if user_id != session['user_id'] and session['role'] != 'public_service':
        return jsonify({"status": "error", "message": "forbidden"}), 403
        
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    db.close()
    if not user: return jsonify({"status": "error", "message": "no user found"}), 404
    
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
def find_helpers(location):
    if 'user_id' not in session: return jsonify({"status": "error", "message": "not logged in"}), 401
    db = get_db()
    helpers = db.execute('SELECT name, water_level, power_status FROM users WHERE location LIKE ? AND water_level > 80', (f'%{location}%',)).fetchall()
    db.close()
    return jsonify([dict(h) for h in helpers])

@app.route('/api/stores')
def get_stores():
    if 'user_id' not in session: return jsonify({"status": "error", "message": "not logged in"}), 401
    db = get_db()
    stores = db.execute('SELECT * FROM stores').fetchall()
    db.close()
    return jsonify([dict(s) for s in stores])

@app.route('/api/store/<int:sid>/status', methods=['POST'])
def update_store(sid):
    if 'user_id' not in session: return jsonify({"status": "error", "message": "not logged in"}), 401
    if session['role'] != 'business': return jsonify({"status": "error", "message": "only business accounts can do this"}), 403
    
    db = get_db()
    store = db.execute('SELECT * FROM stores WHERE id = ?', (sid,)).fetchone()
    
    if not store:
        db.close()
        return jsonify({"status": "error", "message": "Store not found"}), 404
        
    # NEW: Ownership Check
    if store['owner_user_id'] and store['owner_user_id'] != session['user_id']:
        db.close()
        return jsonify({"status": "error", "message": "Not your store"}), 403
        
    data = request.get_json()
    db.execute('UPDATE stores SET has_power = ?, has_water = ? WHERE id = ?', (1 if data.get('has_power') else 0, 1 if data.get('has_water') else 0, sid))
    db.commit(); db.close()
    return jsonify({"status": "ok"})

@app.route('/api/reports')
def get_reports():
    if 'user_id' not in session: return jsonify({"status": "error", "message": "not logged in"}), 401
    category = request.args.get('category')
    db = get_db()
    if category: rows = db.execute('SELECT * FROM reports WHERE category = ? ORDER BY id DESC LIMIT 50', (category,)).fetchall()
    else: rows = db.execute('SELECT * FROM reports ORDER BY id DESC LIMIT 50').fetchall()
    db.close()
    if session['role'] == 'public_service': return jsonify([dict(r) for r in rows])
    return jsonify([{"status": r["status"], "id": r["id"], "issue": r["issue"], "user": r["user"], "category": r["category"], "location": r["location"], "timestamp": r["timestamp"]} for r in rows])

@app.route('/api/report', methods=['POST'])
def add_report():
    if 'user_id' not in session: return jsonify({"status": "error", "message": "not logged in"}), 401
    data = request.get_json()
    issue = data.get('issue', '').strip() # Added strip()
    if not issue: return jsonify({"status": "error", "message": "need an issue"}), 400
    if len(issue) > 500: return jsonify({"status": "error", "message": "issue too long"}), 400 # Added length cap
    
    category = data.get('category', 'other')
    location = data.get('location') or session['location']
    lat = data.get('lat') or -25.9867
    lng = data.get('lng') or 28.0167
    db = get_db()
    c = db.cursor()
    c.execute('INSERT INTO reports (issue, status, user, category, location, lat, lng) VALUES (?, ?, ?, ?, ?, ?, ?)', (issue, 'open', session['username'], category, location, lat, lng))
    db.commit()
    new_id = c.lastrowid # Return ID for frontend optimistic update
    db.close()
    return jsonify({"status": "ok", "id": new_id})

@app.route('/api/report/<int:rid>/resolve', methods=['POST'])
def resolve_report(rid):
    if 'user_id' not in session: return jsonify({"status": "error", "message": "not logged in"}), 401
    if session['role'] != 'public_service': return jsonify({"status": "error", "message": "only public service can close reports"}), 403
    db = get_db()
    db.execute('UPDATE reports SET status = ? WHERE id = ?', ('resolved', rid))
    db.commit(); db.close()
    return jsonify({"status": "ok"})

@app.route('/api/map-dots')
def map_dots():
    if 'user_id' not in session: return jsonify({"status": "error", "message": "not logged in"}), 401
    if session['role'] != 'public_service': return jsonify([]), 200
    db = get_db()
    rows = db.execute('SELECT id, issue, category, location, lat, lng FROM reports WHERE status = "open"').fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/outages')
def get_outages():
    if 'user_id' not in session: return jsonify({"status": "error", "message": "not logged in"}), 401
    otype = request.args.get('type')
    db = get_db()
    if otype: rows = db.execute('SELECT * FROM outages WHERE type = ? ORDER BY id', (otype,)).fetchall()
    else: rows = db.execute('SELECT * FROM outages ORDER BY id').fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/services')
def get_services():
    if 'user_id' not in session: return jsonify({"status": "error", "message": "not logged in"}), 401
    stype = request.args.get('type')
    db = get_db()
    if stype: rows = db.execute('SELECT * FROM services WHERE type = ? ORDER BY name', (stype,)).fetchall()
    else: rows = db.execute('SELECT * FROM services ORDER BY type, name').fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/weather')
def get_weather():
    lat = -25.9867; lon = 28.0167
    api_key = os.getenv('OPENWEATHER_KEY', 'YOUR_OPENWEATHER_KEY')
    if api_key == 'YOUR_OPENWEATHER_KEY': return jsonify({"temp": 25, "desc": "Clear Sky", "warning": "None"})
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
def get_users():
    if 'user_id' not in session: return jsonify({"status": "error", "message": "not logged in"}), 401
    db = get_db()
    users = db.execute('SELECT id, name, location, water_level, power_status FROM users').fetchall()
    db.close()
    return jsonify([dict(u) for u in users])

@app.route('/api/water-level', methods=['POST'])
def update_water():
    if 'user_id' not in session: return jsonify({"status": "error", "message": "not logged in"}), 401
    data = request.get_json()
    level = int(data.get('water_level', 50))
    level = max(0, min(100, level))
    db = get_db()
    db.execute('UPDATE users SET water_level = ? WHERE id = ?', (level, session['user_id']))
    db.commit(); db.close()
    return jsonify({"status": "ok", "water_level": level})

@app.route('/api/stats')
def get_stats():
    if 'user_id' not in session: return jsonify({"status": "error", "message": "not logged in"}), 401
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
def business_profile():
    if 'user_id' not in session: return jsonify({"status": "error", "message": "not logged in"}), 401
    db = get_db(); loc = session['location']
    stores = db.execute('SELECT * FROM stores ORDER BY id').fetchall()
    total_crime = db.execute("SELECT COUNT(*) FROM reports WHERE category = 'crime'").fetchone()[0]
    resolved_crime = db.execute("SELECT COUNT(*) FROM reports WHERE category = 'crime' AND status = 'resolved'").fetchone()[0]
    zones = ['Diepsloot West', 'Diepsloot North', 'Diepsloot East', 'Diepsloot Central']
    zone_stats = []
    for z in zones:
        cnt = db.execute("SELECT COUNT(*) FROM reports WHERE category = 'crime' AND location LIKE ?", (f'%{z}%',)).fetchone()[0]
        # Fixed KeyError risk with .get()
        base = {'Diepsloot West': 12, 'Diepsloot North': 18, 'Diepsloot East': 9, 'Diepsloot Central': 22}.get(z, 10)
        rate = base + (cnt * 3)
        zone_stats.append({"zone": z, "burglary_rate": rate, "trend": "up" if cnt > 0 else "stable", "level": "high" if rate > 25 else ("medium" if rate > 15 else "low")})
    db.close()
    return jsonify({"status": "success", "stores": [dict(s) for s in stores], "crime_total": total_crime, "crime_resolved": resolved_crime, "zones": zone_stats, "user_location": loc})

if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG') == '1'
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=debug_mode)