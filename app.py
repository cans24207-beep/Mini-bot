from flask import Flask, render_template, request, jsonify
import sqlite3, datetime, json, os

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            telegram_id TEXT PRIMARY KEY,
            points INTEGER DEFAULT 0,
            balance REAL DEFAULT 0.0,
            ads_watched INTEGER DEFAULT 0,
            completed_tasks TEXT DEFAULT '[]',
            ref_count INTEGER DEFAULT 0,
            last_ad_time TEXT,
            last_daily_time TEXT,
            task_timestamps TEXT DEFAULT '{}'
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/user_data', methods=['POST'])
def user_data():
    data = request.get_json(silent=True) or {}
    telegram_id = str(data.get('user_id', '')).strip()
    if not telegram_id or telegram_id == 'None':
        return jsonify({'success': False, 'error': 'Kullanici bulunamadi.'}), 400
    conn = get_db_connection()
    conn.execute('INSERT OR IGNORE INTO users (telegram_id, points, balance, ads_watched, completed_tasks, ref_count, task_timestamps) VALUES (?, 0, 0.0, 0, "[]", 0, "{}")', (telegram_id,))
    conn.commit()
    user = conn.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,)).fetchone()
    conn.close()
    user_dict = dict(user)
    
    can_claim_daily = True
    if user_dict.get('last_daily_time'):
        last_daily = datetime.datetime.fromisoformat(user_dict['last_daily_time'])
        if datetime.datetime.now() - last_daily < datetime.timedelta(hours=12):
            can_claim_daily = False
            
    try:
        completed = json.loads(user_dict.get('completed_tasks', '[]'))
    except:
        completed = []

    return jsonify({
        'success': True,
        'points': user_dict.get('points', 0),
        'balance': user_dict.get('balance', 0.0),
        'ads_watched': user_dict.get('ads_watched', 0),
        'completed_tasks': completed,
        'ref_count': user_dict.get('ref_count', 0),
        'can_claim_daily': can_claim_daily
    })

@app.route('/api/watch_ad', methods=['POST'])
def watch_ad():
    data = request.get_json(silent=True) or {}
    telegram_id = str(data.get('user_id', '')).strip()
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,)).fetchone()
    if not user:
        conn.close()
        return jsonify({'success': False, 'error': 'Kullanici bulunamadi.'}), 400
    
    ads_watched = user['ads_watched']
    last_ad = user['last_ad_time']
    if last_ad:
        last_ad_time = datetime.datetime.fromisoformat(last_ad)
        if datetime.datetime.now() - last_ad_time >= datetime.timedelta(hours=12):
            ads_watched = 0
            
    if ads_watched >= 10:
        conn.close()
        return jsonify({'success': False, 'error': '12 saatlik reklam limitine ulaştınız (10/10).'})
        
    new_points = user['points'] + 25
    new_ads = ads_watched + 1
    now_str = datetime.datetime.now().isoformat()
    conn.execute('UPDATE users SET points = ?, ads_watched = ?, last_ad_time = ? WHERE telegram_id = ?', (new_points, new_ads, now_str, telegram_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'points': new_points, 'ads_watched': new_ads})

@app.route('/api/claim_daily', methods=['POST'])
def claim_daily():
    data = request.get_json(silent=True) or {}
    telegram_id = str(data.get('user_id', '')).strip()
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,)).fetchone()
    if not user:
        conn.close()
        return jsonify({'success': False, 'error': 'Kullanici bulunamadi.'}), 400
        
    if user['last_daily_time']:
        last_daily = datetime.datetime.fromisoformat(user['last_daily_time'])
        if datetime.datetime.now() - last_daily < datetime.timedelta(hours=12):
            conn.close()
            return jsonify({'success': False, 'error': 'Günlük ödülü 12 saatte bir alabilirsiniz.'})
            
    new_points = user['points'] + 100
    now_str = datetime.datetime.now().isoformat()
    conn.execute('UPDATE users SET points = ?, last_daily_time = ? WHERE telegram_id = ?', (new_points, now_str, telegram_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'points': new_points})

@app.route('/api/complete_task', methods=['POST'])
def complete_task():
    data = request.get_json(silent=True) or {}
    telegram_id = str(data.get('user_id', '')).strip()
    task_id = str(data.get('task_id', ''))
    reward = int(data.get('reward', 0))
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,)).fetchone()
    if not user:
        conn.close()
        return jsonify({'success': False, 'error': 'Kullanici bulunamadi.'}), 400
        
    try:
        completed = json.loads(user['completed_tasks'] or '[]')
    except:
        completed = []
        
    if task_id in completed:
        conn.close()
        return jsonify({'success': False, 'error': 'Bu görev zaten tamamlandı.'})
        
    completed.append(task_id)
    new_points = user['points'] + reward
    conn.execute('UPDATE users SET points = ?, completed_tasks = ? WHERE telegram_id = ?', (new_points, json.dumps(completed), telegram_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'points': new_points})

@app.route('/api/convert', methods=['POST'])
def convert_points():
    data = request.get_json(silent=True) or {}
    telegram_id = str(data.get('user_id', '')).strip()
    amount_pts = int(data.get('amount_pts', 0))
    if amount_pts <= 0:
        return jsonify({'success': False, 'error': 'Geçersiz miktar.'}), 400
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,)).fetchone()
    if not user or user['points'] < amount_pts:
        conn.close()
        return jsonify({'success': False, 'error': 'Yetersiz puan.'}), 400
        
    new_points = user['points'] - amount_pts
    earned_tl = (amount_pts / 1000.0) * 35.0
    new_balance = user['balance'] + earned_tl
    conn.execute('UPDATE users SET points = ?, balance = ? WHERE telegram_id = ?', (new_points, new_balance, telegram_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'points': new_points, 'balance': new_balance})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
