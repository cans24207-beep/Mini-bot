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

@app.route('/api/watch_ad', methods=['POST'])
def watch_ad():
    data = request.get_json(silent=True) or {}
    telegram_id = str(data.get('user_id', '')).strip()
    if not telegram_id or telegram_id == 'None':
        return jsonify({'success': False, 'error': 'Kullanici bulunamadi.'}), 400

    conn = get_db_connection()
    conn.execute('INSERT OR IGNORE INTO users (telegram_id, points, balance) VALUES (?, 0, 0.0)', (telegram_id,))
    conn.execute('UPDATE users SET points = points + 25, ads_watched = ads_watched + 1 WHERE telegram_id = ?', (telegram_id,))
    conn.commit()
    user = conn.execute('SELECT points, ads_watched FROM users WHERE telegram_id = ?', (telegram_id,)).fetchone()
    conn.close()

    return jsonify({'success': True, 'points': user['points'], 'ads_watched': user['ads_watched']})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
@app.route('/api/watch_ad', methods=['POST'])
def watch_ad():
    data = request.get_json()
    user_id = data.get('userId')
    
    # Kullanıcıyı veritabanından bul
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT points, last_ad_watched FROM users WHERE id = %s', (user_id,))
    user = cur.fetchone()
    
    if not user:
        cur.close()
        conn.close()
        return jsonify({'success': False, 'message': 'Kullanıcı bulunamadı.'}), 404
        
    last_watched = user[1]
    now = datetime.now()
    
    # 25 saniye geçmeden tekrar ödül verilmesini engelle (Cooldown)
    if last_watched and (now - last_watched).total_seconds() < 25:
        cur.close()
        conn.close()
        return jsonify({'success': False, 'message': 'Çok hızlı istek atıldı, lütfen bekleyin.'}), 400
        
    # Puanı 4 artır ve son izleme zamanını güncelle
    cur.execute(
        'UPDATE users SET points = points + 4, last_ad_watched = %s WHERE id = %s',
        (now, user_id)
    )
    conn.commit()
    cur.close()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Reklam ödülü eklendi!'})
@app.route('/api/complete_task', methods=['POST'])
def complete_task():
    data = request.get_json()
    user_id = data.get('userId')
    task_id = data.get('taskId')
    reward = data.get('reward', 0)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Bu görev daha önce yapılmış mı kontrol et
        cur.execute('SELECT * FROM completed_tasks WHERE user_id = %s AND task_id = %s', (user_id, task_id))
        if cur.fetchone():
            return jsonify({'success': False, 'message': 'Bu görev zaten tamamlandı.'}), 400
            
        # Görevi kaydet ve puanı ekle
        cur.execute('INSERT INTO completed_tasks (user_id, task_id) VALUES (%s, %s)', (user_id, task_id))
        cur.execute('UPDATE users SET points = points + %s WHERE id = %s', (reward, user_id))
        
        conn.commit()
        return jsonify({'success': True, 'message': 'Görev ödülü eklendi!'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()
@app.route('/api/convert_points', methods=['POST'])
def convert_points():
    data = request.get_json()
    user_id = data.get('userId')
    points_to_convert = data.get('pointsToConvert', 0)
    cash_earned = data.get('cashEarned', 0.0)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Kullanıcının güncel puanını kontrol et
        cur.execute('SELECT points FROM users WHERE id = %s', (user_id,))
        user = cur.fetchone()
        
        if not user or user[0] < points_to_convert:
            return jsonify({'success': False, 'message': 'Yetersiz puan!'}), 400
            
        # Puanı düşür ve nakit bakiyeyi artır
        cur.execute(
            'UPDATE users SET points = points - %s, balance = balance + %s WHERE id = %s',
            (points_to_convert, cash_earned, user_id)
        )
        
        conn.commit()
        return jsonify({'success': True, 'message': 'Dönüştürme başarılı, puanlar güncellendi!'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()
@app.route('/api/claim_daily', methods=['POST'])
def claim_daily():
    data = request.get_json()
    user_id = data.get('userId')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Örnek günlük ödül mantığı (puan ekleme)
        cur.execute('UPDATE users SET points = points + 50 WHERE id = %s', (user_id,))
        conn.commit()
        return jsonify({'success': True, 'message': 'Günlük ödül alındı!'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()
