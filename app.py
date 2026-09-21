from flask import Flask, render_template_string, request, jsonify
import sqlite3, datetime, json, os

app = Flask(__name__)

HTML_Content = """<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>İzle Kazan</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        :root {
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --accent: #38bdf8;
            --text-color: #f8fafc;
            --text-secondary: #94a3b8;
            --btn-bg: #2563eb;
            --btn-hover: #1d4ed8;
        }
        body {
            background-color: var(--bg-color);
            color: var(--text-color);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 15px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        .container {
            width: 100%;
            max-width: 400px;
        }
        .header {
            background: var(--card-bg);
            padding: 20px;
            border-radius: 16px;
            text-align: center;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            margin-bottom: 15px;
        }
        .balance-box {
            font-size: 28px;
            font-weight: bold;
            color: var(--accent);
            margin: 10px 0;
        }
        .points-box {
            font-size: 14px;
            color: var(--text-secondary);
        }
        .card {
            background: var(--card-bg);
            padding: 15px;
            border-radius: 14px;
            margin-bottom: 12px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.2);
        }
        .card h3 {
            margin: 0 0 10px 0;
            font-size: 16px;
            color: var(--accent);
        }
        button {
            width: 100%;
            background-color: var(--btn-bg);
            color: white;
            border: none;
            padding: 12px;
            border-radius: 10px;
            font-size: 15px;
            font-weight: bold;
            cursor: pointer;
            transition: background 0.2s;
            margin-top: 5px;
        }
        button:hover {
            background-color: var(--btn-hover);
        }
        button:disabled {
            background-color: #475569;
            cursor: not-allowed;
        }
        .msg {
            font-size: 12px;
            text-align: center;
            margin-top: 5px;
            color: #34d399;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="points-box">Puanınız: <span id="points">0</span> Puan</div>
            <div class="balance-box" id="balance">0.00 TL</div>
            <div class="points-box">İzlenen Reklam: <span id="adsCount">0</span>/10</div>
        </div>

        <div class="card">
            <h3>🎁 Günlük Ödül</h3>
            <p style="font-size: 13px; color: var(--text-secondary); margin: 0 0 10px 0;">Her 12 saatte bir 100 puan kazan!</p>
            <button id="dailyBtn" onclick="claimDaily()">Günlük Ödülü Al</button>
        </div>

        <div class="card">
            <h3>📺 Reklam İzle Kazan</h3>
            <p style="font-size: 13px; color: var(--text-secondary); margin: 0 0 10px 0;">İzle başı 25 puan kazan (12 saatte 10 hak).</p>
            <button onclick="watchAd()">Reklam İzle</button>
        </div>

        <div class="card">
            <h3>💰 Puanı Bakiyeye Çevir</h3>
            <p style="font-size: 13px; color: var(--text-secondary); margin: 0 0 10px 0;">1000 Puan = 35 TL</p>
            <button onclick="convertPoints()">Hepsini Çevir</button>
        </div>
    </div>

    <script>
        const tg = window.Telegram.WebApp;
        tg.expand();
        const userId = tg.initDataUnsafe?.user?.id ? String(tg.initDataUnsafe.user.id) : "test_user_123";

        function loadUserData() {
            fetch('/api/user_data', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId })
            })
            .then(res => res.json())
            .then(data => {
                if(data.success) {
                    document.getElementById('points').innerText = data.points;
                    document.getElementById('balance').innerText = data.balance.toFixed(2) + ' TL';
                    document.getElementById('adsCount').innerText = data.ads_watched;
                    if(!data.can_claim_daily) {
                        document.getElementById('dailyBtn').innerText = "Ödül Alındı (Bekliyor)";
                        document.getElementById('dailyBtn').disabled = true;
                    }
                }
            });
        }

        function watchAd() {
            fetch('/api/watch_ad', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId })
            })
            .then(res => res.json())
            .then(data => {
                if(data.success) {
                    alert('Reklam izlendi! +25 Puan');
                    loadUserData();
                } else {
                    alert(data.error || 'Bir hata oluştu.');
                }
            });
        }

        function claimDaily() {
            fetch('/api/claim_daily', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId })
            })
            .then(res => res.json())
            .then(data => {
                if(data.success) {
                    alert('Günlük ödül alındı! +100 Puan');
                    loadUserData();
                } else {
                    alert(data.error || 'Zaten alındı.');
                }
            });
        }

        function convertPoints() {
            let pts = parseInt(document.getElementById('points').innerText);
            if(pts < 1000) {
                alert('En az 1000 puanınız olmalıdır.');
                return;
            }
            fetch('/api/convert', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId, amount_pts: pts })
            })
            .then(res => res.json())
            .then(data => {
                if(data.success) {
                    alert('Puanlar başarıyla bakiyeye dönüştürüldü!');
                    loadUserData();
                } else {
                    alert(data.error || 'Yetersiz puan.');
                }
            });
        }

        loadUserData();
    </script>
</body>
</html>
"""

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
    return render_template_string(HTML_Content)

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
        'referrals': [],
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

@app.route('/api/referral_stats', methods=['POST'])
def referral_stats():
    return jsonify({'success': True, 'referrals': [], 'ref_count': 0})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
