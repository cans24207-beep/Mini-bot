import sqlite3
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

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
            completed_tasks INTEGER DEFAULT 0,
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
    telegram_id = request.args.get('telegram_id')
    if not telegram_id:
        return jsonify({'error': 'Telegram ID gereklidir'}), 400
        
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,)).fetchone()
    
    if not user:
        conn.execute('INSERT INTO users (telegram_id, points, balance) VALUES (?, 0, 0.0)', (telegram_id,))
        conn.commit()
        user = conn.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,)).fetchone()
        
    conn.close()
    return jsonify(dict(user))

@app.route('/api/convert', methods=['POST'])
def convert_points():
    data = request.get_json()
    telegram_id = data.get('telegram_id')
    points_to_convert = data.get('points', 1200)
    
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,)).fetchone()
    
    if not user or user['points'] < points_to_convert:
        conn.close()
        return jsonify({'success': False, 'message': 'Yetersiz puan!'}), 400
        
    earned_try = (points_to_convert / 1000) * 35.0
    new_points = user['points'] - points_to_convert
    new_balance = user['balance'] + earned_try
    
    conn.execute('UPDATE users SET points = ?, balance = ? WHERE telegram_id = ?', 
                 (new_points, new_balance, telegram_id))
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True, 
        'new_points': new_points, 
        'new_balance': new_balance
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
