from flask import Flask, render_template, request, jsonify
import sqlite3
import os

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
            completed_tasks TEXT DEFAULT '',
            ref_count INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/user', methods=['GET'])
def get_user():
    telegram_id = request.args.get('telegram_id') or request.args.get('user_id')
    if not telegram_id:
        return jsonify({'error': 'Telegram ID gereklidir'}), 400

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,)).fetchone()

    if not user:
        conn.execute('INSERT INTO users (telegram_id, points, balance, ads_watched, completed_tasks, ref_count) VALUES (?, 0, 0.0, 0, 0, 0)', (telegram_id,))
        conn.commit()
        user = conn.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,)).fetchone()

    conn.close()
    
    user_dict = dict(user)
    return jsonify({
        'telegram_id': user_dict.get('telegram_id'),
        'points': user_dict.get('points', 0),
        'balance': user_dict.get('balance', 0.0),
        'ads_watched': user_dict.get('ads_watched', 0),
        'completed_tasks': user_dict.get('completed_tasks', 0),
        'ref_count': user_dict.get('ref_count', 0)
    })

@app.route('/api/user_data', methods=['POST'])
def user_data():
    data = request.get_json(silent=True) or {}
    telegram_id = str(data.get('user_id', '')).strip()
    
    if not telegram_id or telegram_id == 'None':
        return jsonify({'success': False, 'error': 'Kullanici bulunamadi.'}), 400

    conn = get_db_connection()
    conn.execute('INSERT OR IGNORE INTO users (telegram_id, points, balance, ads_watched, completed_tasks, ref_count) VALUES (?, 0, 0.0, 0, 0, 0)', (telegram_id,))
    conn.commit()
    
    user = conn.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,)).fetchone()
    conn.close()

    user_dict = dict(user)
    
    return jsonify({
        'success': True,
        'points': user_dict.get('points', 0),
        'balance': user_dict.get('balance', 0.0),
        'ads_watched': user_dict.get('ads_watched', 0),
        'completed_tasks': [],
        'ref_count': user_dict.get('ref_count', 0),
        'referrals': [],
        'can_claim_daily': True
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
        
    new_points = user['points'] + 25
    new_ads = user['ads_watched'] + 1
    
    conn.execute('UPDATE users SET points = ?, ads_watched = ? WHERE telegram_id = ?', (new_points, new_ads, telegram_id))
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
        
    new_points = user['points'] + 100
    conn.execute('UPDATE users SET points = ? WHERE telegram_id = ?', (new_points, telegram_id))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'points': new_points})

@app.route('/api/complete_task', methods=['POST'])
def complete_task():
    data = request.get_json(silent=True) or {}
    telegram_id = str(data.get('user_id', '')).strip()
    reward = int(data.get('reward', 0))
    
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,)).fetchone()
    
    if not user:
        conn.close()
        return jsonify({'success': False, 'error': 'Kullanici bulunamadi.'}), 400
        
    new_points = user['points'] + reward
    conn.execute('UPDATE users SET points = ? WHERE telegram_id = ?', (new_points, telegram_id))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'points': new_points, 'completed_tasks': []})

@app.route('/api/withdraw', methods=['POST'])
def withdraw():
    data = request.get_json(silent=True) or {}
    telegram_id = str(data.get('user_id', '')).strip()
    amount_pts = int(data.get('amount_pts', 0))
    
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,)).fetchone()
    
    if not user or user['points'] < amount_pts:
        conn.close()
        return jsonify({'success': False, 'error': 'Yetersiz puan veya kullanici bulunamadi.'}), 400
        
    new_points = user['points'] - amount_pts
    conn.execute('UPDATE users SET points = ? WHERE telegram_id = ?', (new_points, telegram_id))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'new_points': new_points})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
