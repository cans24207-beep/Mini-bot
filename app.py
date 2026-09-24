import os, json, time, hmac, hashlib, datetime, urllib.parse
import psycopg2, psycopg2.extras
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
DATABASE_URL = os.environ.get('DATABASE_URL')
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
USDT_KURU = 40.0     # 1 USDT kaç TL
MIN_CEKIM = 100.0    # en az çekim (TL)
AD_LIMIT = 15        # 12 saatte reklam sayısı
AD_PUAN = 25
GUNLUK_PUAN = 100
# id: (grup k=kolay z=zorlu, başlık, puan, link)
TASKS = {
    'k1': ('k', 'Kanalımıza abone ol', 150, ''),
    'k2': ('k', 'Sohbet grubumuza katıl', 200, ''),
    'k3': ('k', 'Botu bir arkadaşına öner', 100, ''),
    'k4': ('k', 'Duyuru mesajını oku', 100, ''),
    'k5': ('k', 'Uygulamayı favorilere ekle', 100, ''),
    'z1': ('z', 'Instagram sayfamızı takip et', 300, ''),
    'z2': ('z', 'YouTube kanalına abone ol', 300, ''),
    'z3': ('z', '3 arkadaşını davet et', 400, ''),
    'z4': ('z', 'Uygulamaya yorum bırak', 400, ''),
    'z5': ('z', 'Anketi doldur', 500, ''),
}


_pool = []


def db():
    while _pool:
        c = _pool.pop()
        try:
            if not c.closed:
                k = c.cursor()
                c.autocommit = True
                k.execute('SELECT 1')
                c.autocommit = False
                k.close()
                return c
        except Exception:
            pass
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def release(c):
    try:
        c.rollback()
        if not c.closed and len(_pool) < 4:
            _pool.append(c)
            return
    except Exception:
        pass
    try:
        c.close()
    except Exception:
        pass


def init_db():
    c = db()
    k = c.cursor()
    k.execute("""CREATE TABLE IF NOT EXISTS users (
        telegram_id TEXT PRIMARY KEY, points INTEGER DEFAULT 0, balance REAL DEFAULT 0.0,
        ads_watched INTEGER DEFAULT 0, completed_tasks TEXT DEFAULT '[]', ref_count INTEGER DEFAULT 0,
        last_ad_time TEXT, last_daily_time TEXT, task_timestamps TEXT DEFAULT '{}')""")
    k.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS name TEXT')
    k.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS referrer TEXT')
    k.execute("""CREATE TABLE IF NOT EXISTS withdrawals (
        id SERIAL PRIMARY KEY, telegram_id TEXT, method TEXT, amount_tl REAL,
        details TEXT, status TEXT DEFAULT 'beklemede', created TEXT)""")
    c.commit()
    k.close()
    c.close()


init_db()


def fresh(ts):
    try:
        return datetime.datetime.now() - datetime.datetime.fromisoformat(ts) < datetime.timedelta(hours=12)
    except Exception:
        return False


def jl(s):
    try:
        return json.loads(s or '{}')
    except Exception:
        return {}


def get_user(c, uid):
    k = c.cursor()
    k.execute('SELECT * FROM users WHERE telegram_id = %s', (uid,))
    r = k.fetchone()
    if not r:
        k.execute('INSERT INTO users (telegram_id) VALUES (%s) ON CONFLICT (telegram_id) DO NOTHING', (uid,))
        k.execute('SELECT * FROM users WHERE telegram_id = %s', (uid,))
        r = k.fetchone()
        c.commit()
    k.close()
    return dict(r)


@app.before_request
def _auth():
    if not BOT_TOKEN or not request.path.startswith('/api/'):
        return None
    try:
        d = dict(urllib.parse.parse_qsl(request.headers.get('X-Init-Data', ''), keep_blank_values=True))
        h = d.pop('hash')
        chk = '\n'.join(k + '=' + v for k, v in sorted(d.items()))
        key = hmac.new(b'WebAppData', BOT_TOKEN.encode(), hashlib.sha256).digest()
        ok = hmac.compare_digest(hmac.new(key, chk.encode(), hashlib.sha256).hexdigest(), h)
        uid = str(json.loads(d['user'])['id'])
        body = request.get_json(silent=True) or {}
        if not ok or str(body.get('user_id')) != uid or time.time() - int(d['auth_date']) > 86400:
            raise ValueError
    except Exception:
        return jsonify({'success': False, 'error': 'Yetkisiz istek. Uygulamayı Telegram içinden aç.'}), 403
    return None


def api(path):
    def deco(fn):
        def view():
            d = request.get_json(silent=True) or {}
            uid = str(d.get('user_id', '')).strip()
            if not uid or uid == 'None':
                return jsonify({'success': False, 'error': 'Kullanıcı bulunamadı.'}), 400
            c = db()
            try:
                return jsonify(fn(c, get_user(c, uid), uid, d))
            except Exception as e:
                c.rollback()
                print('HATA', path, e)
                return jsonify({'success': False, 'error': 'Sunucu hatası, tekrar dene.'}), 500
            finally:
                release(c)
        app.add_url_rule('/api/' + path, 'v_' + path, view, methods=['POST'])
        return fn
    return deco


@app.after_request
def _nocache(r):
    if request.path == '/':
        r.headers['Cache-Control'] = 'no-store'
    return r


@app.route('/')
def index():
    return render_template('index.html')


@api('state')
def state(c, u, uid, d):
    k = c.cursor()
    if d.get('name') and str(d['name'])[:40] != (u.get('name') or ''):
        k.execute('UPDATE users SET name = %s WHERE telegram_id = %s', (str(d['name'])[:40], uid))
    ref = str(d.get('ref') or '').strip()
    if ref and ref != uid and not u.get('referrer') and u['points'] == 0 and u['ads_watched'] == 0:
        k.execute('SELECT 1 FROM users WHERE telegram_id = %s', (ref,))
        if k.fetchone():
            k.execute('UPDATE users SET referrer = %s WHERE telegram_id = %s', (ref, uid))
            k.execute('UPDATE users SET ref_count = ref_count + 1 WHERE telegram_id = %s', (ref,))
    k.execute('SELECT telegram_id, name FROM users WHERE referrer = %s ORDER BY telegram_id DESC LIMIT 50', (uid,))
    refs = [r['name'] or ('Kullanıcı ...' + r['telegram_id'][-4:]) for r in k.fetchall()]
    c.commit()
    ts = jl(u['task_timestamps'])
    return {
        'success': True, 'points': u['points'], 'balance': round(u['balance'] or 0, 2),
        'ads': u['ads_watched'] if fresh(u['last_ad_time']) else 0,
        'daily': not fresh(u['last_daily_time']),
        'ref_count': u['ref_count'] or 0, 'refs': refs,
        'done': [t for t, v in ts.items() if fresh(v)],
        'tasks': [{'id': t, 'g': v[0], 't': v[1], 'p': v[2], 'u': v[3]} for t, v in TASKS.items()],
        'usdt': USDT_KURU, 'min': MIN_CEKIM,
    }


@api('watch_ad')
def watch_ad(c, u, uid, d):
    now = datetime.datetime.now()
    ads = u['ads_watched'] if fresh(u['last_ad_time']) else 0
    try:
        gecen = (now - datetime.datetime.fromisoformat(u['last_ad_time'])).total_seconds()
    except Exception:
        gecen = 999
    if gecen < 4:
        return {'success': False, 'error': 'Çok hızlı, birkaç saniye bekleyin.'}
    if ads >= AD_LIMIT:
        return {'success': False, 'error': '12 saatlik reklam limitine ulaştınız (%d/%d).' % (AD_LIMIT, AD_LIMIT)}
    k = c.cursor()
    k.execute('UPDATE users SET points = points + %s, ads_watched = %s, last_ad_time = %s WHERE telegram_id = %s AND last_ad_time IS NOT DISTINCT FROM %s RETURNING points',
              (AD_PUAN, ads + 1, now.isoformat(), uid, u['last_ad_time']))
    r = k.fetchone()
    if not r:
        c.rollback()
        return {'success': False, 'error': 'Çok hızlı, tekrar dene.'}
    c.commit()
    return {'success': True, 'points': r['points'], 'ads_watched': ads + 1}


@api('claim_daily')
def claim_daily(c, u, uid, d):
    if fresh(u['last_daily_time']):
        return {'success': False, 'error': 'Günlük ödülü 12 saatte bir alabilirsiniz.'}
    k = c.cursor()
    k.execute('UPDATE users SET points = points + %s, last_daily_time = %s WHERE telegram_id = %s AND last_daily_time IS NOT DISTINCT FROM %s RETURNING points',
              (GUNLUK_PUAN, datetime.datetime.now().isoformat(), uid, u['last_daily_time']))
    r = k.fetchone()
    if not r:
        c.rollback()
        return {'success': False, 'error': 'Tekrar dene.'}
    c.commit()
    return {'success': True, 'points': r['points']}


@api('task')
def task(c, u, uid, d):
    tid = str(d.get('task_id', ''))
    if tid not in TASKS:
        return {'success': False, 'error': 'Görev bulunamadı.'}
    ts = jl(u['task_timestamps'])
    if fresh(ts.get(tid)):
        return {'success': False, 'error': 'Bu görev 12 saatte bir yapılabilir.'}
    old = u['task_timestamps']
    ts[tid] = datetime.datetime.now().isoformat()
    k = c.cursor()
    k.execute('UPDATE users SET points = points + %s, task_timestamps = %s WHERE telegram_id = %s AND task_timestamps IS NOT DISTINCT FROM %s RETURNING points',
              (TASKS[tid][2], json.dumps(ts), uid, old))
    r = k.fetchone()
    if not r:
        c.rollback()
        return {'success': False, 'error': 'Tekrar dene.'}
    c.commit()
    return {'success': True, 'points': r['points'], 'reward': TASKS[tid][2]}


@api('convert')
def convert(c, u, uid, d):
    try:
        n = int(d.get('amount_pts') or 0)
    except Exception:
        n = 0
    if n < 1000:
        return {'success': False, 'error': 'En az 1000 puan çevrilebilir.'}
    k = c.cursor()
    k.execute('UPDATE users SET points = points - %s, balance = balance + %s WHERE telegram_id = %s AND points >= %s RETURNING points, balance',
              (n, n / 1000.0 * 35.0, uid, n))
    r = k.fetchone()
    if not r:
        c.rollback()
        return {'success': False, 'error': 'Yetersiz puan.'}
    c.commit()
    return {'success': True, 'points': r['points'], 'balance': round(r['balance'], 2)}


@api('withdraw')
def withdraw(c, u, uid, d):
    if not BOT_TOKEN:
        return {'success': False, 'error': 'Çekim şu an kapalı.'}
    try:
        amt = float(d.get('amount') or 0)
    except Exception:
        amt = 0
    method = d.get('method')
    det = str(d.get('details', '')).strip()[:200]
    if method not in ('havale', 'usdt') or not (amt >= MIN_CEKIM) or len(det) < 10:
        return {'success': False, 'error': 'Bilgileri kontrol edin. En az %d TL çekilebilir.' % MIN_CEKIM}
    if method == 'havale' and 'TR' not in det.upper():
        return {'success': False, 'error': 'Geçerli bir IBAN girin.'}
    if method == 'usdt':
        det += ' | %.2f USDT' % (amt / USDT_KURU)
    k = c.cursor()
    k.execute('UPDATE users SET balance = balance - %s WHERE telegram_id = %s AND balance >= %s RETURNING balance',
              (amt, uid, amt))
    r = k.fetchone()
    if not r:
        c.rollback()
        return {'success': False, 'error': 'Yetersiz bakiye.'}
    k.execute('INSERT INTO withdrawals (telegram_id, method, amount_tl, details, created) VALUES (%s, %s, %s, %s, %s)',
              (uid, method, amt, det, datetime.datetime.now().isoformat()))
    c.commit()
    return {'success': True, 'balance': round(r['balance'], 2)}


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
