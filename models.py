import pandas as pd, sqlite3, os, time, csv
from datetime import datetime

class AdRecommender:
    def __init__(self, ad_data_path, db_path, users_root):
        self.db_path = db_path
        self.ad_data_path = ad_data_path
        self.users_root = users_root
        self.ads = pd.read_csv(ad_data_path).fillna('')
        if 'ad_id' not in self.ads.columns:
            self.ads['ad_id'] = ['ad_' + str(i) for i in range(len(self.ads))]
        if 'details' not in self.ads.columns:
            self.ads['details'] = ''
        self.initialize_database()

    def initialize_database(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS ad_metrics (
            ad_id TEXT PRIMARY KEY,
            impressions INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            dislikes INTEGER DEFAULT 0,
            last_updated INTEGER
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS user_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            ad_id TEXT,
            impressions INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            dislikes INTEGER DEFAULT 0,
            last_updated INTEGER,
            UNIQUE(user_id, ad_id)
        )''')
        conn.commit()
        for ad in self.ads['ad_id'].tolist():
            c.execute('INSERT OR IGNORE INTO ad_metrics(ad_id, impressions, clicks, dislikes, last_updated) VALUES (?,?,?,?,?)', (ad,0,0,0,int(time.time())))
        conn.commit()
        conn.close()

    def _exec(self, query, params=(), commit=False):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(query, params)
        if commit:
            conn.commit()
            conn.close()
            return None
        rows = c.fetchall()
        conn.close()
        return rows

    # --- user management ---
    def register_user(self, username, password):
        
        uname = username.strip().lower()
        if not uname or not password:
            raise ValueError("username and password required")
        user_folder = os.path.join(self.users_root, uname)
        if os.path.exists(user_folder):
            raise FileExistsError("username already exists")
        os.makedirs(user_folder, exist_ok=False)
        with open(os.path.join(user_folder, 'details.txt'), 'w', encoding='utf-8') as f:
            f.write(f"Username: {uname}\\nPassword: {password}\\nCreated: {datetime.utcnow().isoformat()}\\n")
        ads_csv = os.path.join(user_folder, 'ads.csv')
        with open(ads_csv, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['ad_id','impressions','clicks','dislikes','last_updated'])
        self._exec('INSERT INTO users(username, password) VALUES (?,?)', (uname, password), commit=True)
        return True

    def authenticate_user(self, username, password):
        uname = username.strip().lower()
        rows = self._exec('SELECT id, username FROM users WHERE username=? AND password=?', (uname, password))
        return rows and len(rows) > 0

    def user_exists(self, username):
        uname = username.strip().lower()
        rows = self._exec('SELECT id FROM users WHERE username=?', (uname,))
        return bool(rows)

    # --- recommendation and metrics ---
    def recommend(self, user_id, current_page, interests, max_results=5):
        ads = self.ads.copy()
        def score_row(row):
            s = 0.0
            page = str(row.get('target_page','') or '')
            cat = str(row.get('category','') or '')
            if current_page and page and current_page.split('?')[0] in page:
                s += 2.0
            if current_page and cat and current_page.split('/')[0] in cat:
                s += 1.0
            if interests:
                for tok in str(interests).split(','):
                    if tok.strip() and tok.strip().lower() in str(row.get('keywords','') or '').lower():
                        s += 0.5
            return s
        ads['score'] = ads.apply(score_row, axis=1)
        rows = self._exec('SELECT ad_id, impressions, clicks, dislikes FROM ad_metrics')
        metrics = {r[0]: {'impressions': r[1], 'clicks': r[2], 'dislikes': r[3]} for r in rows}
        user_rows = self._exec('SELECT ad_id, impressions, clicks, dislikes FROM user_metrics WHERE user_id=?', (user_id,))
        user_metrics = {r[0]: {'impressions': r[1], 'clicks': r[2], 'dislikes': r[3]} for r in user_rows} if user_rows else {}
        final = []
        for _, row in ads.iterrows():
            ad = row.to_dict()
            ad_id = ad.get('ad_id')
            m = metrics.get(ad_id, {'impressions':0,'clicks':0,'dislikes':0})
            um = user_metrics.get(ad_id, {'impressions':0,'clicks':0,'dislikes':0})
            ctr = (m['clicks'] / m['impressions'] * 100) if m['impressions'] > 0 else 0.0
            penalty = m.get('dislikes',0)*0.5 + um.get('dislikes',0)*2.0
            final_score = ad.get('score',0) + (ctr/10.0) - penalty
            
            if um.get('dislikes',0) >= 2:
                continue
            ad_out = {
                'ad_id': ad_id,
                'title': ad.get('title',''),
                'description': ad.get('description',''),
                'image_url': ad.get('image_url',''),
                'target_page': ad.get('target_page',''),
                'category': ad.get('category',''),
                'details': ad.get('details',''),
                'score': final_score,
                'ctr': round(ctr,2),
                'global_dislikes': m.get('dislikes',0),
                'user_dislikes': um.get('dislikes',0)
            }
            final.append(ad_out)
        final_sorted = sorted(final, key=lambda x: x['score'], reverse=True)
        results = final_sorted[:max_results]

        for ad in results:
            aid = ad['ad_id']
            self._exec('UPDATE ad_metrics SET impressions = impressions + 1, last_updated = ? WHERE ad_id = ?', (int(time.time()), aid), commit=True)
            self._exec('INSERT OR IGNORE INTO user_metrics(user_id, ad_id, impressions, clicks, dislikes, last_updated) VALUES (?,?,?,?,?,?)', (user_id, aid, 0,0,0,int(time.time())), commit=True)
            self._exec('UPDATE user_metrics SET impressions = impressions + 1, last_updated = ? WHERE user_id=? AND ad_id=?', (int(time.time()), user_id, aid), commit=True)
            user_folder = os.path.join(self.users_root, user_id)
            if os.path.exists(user_folder):
                csv_path = os.path.join(user_folder, 'ads.csv')
                rows = {}
                if os.path.exists(csv_path):
                    with open(csv_path, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for r in reader:
                            rows[r['ad_id']] = r
                r = rows.get(aid, {'ad_id':aid,'impressions':'0','clicks':'0','dislikes':'0','last_updated':''})
                r['impressions'] = str(int(r.get('impressions',0)) + 1)
                r['last_updated'] = datetime.utcnow().isoformat()
                rows[aid] = r
                with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                    w = csv.writer(f)
                    w.writerow(['ad_id','impressions','clicks','dislikes','last_updated'])
                    for v in rows.values():
                        w.writerow([v['ad_id'], v['impressions'], v['clicks'], v['dislikes'], v['last_updated']])
        return results

    def record_click(self, ad_id, user_id=None):
        self._exec('UPDATE ad_metrics SET clicks = clicks + 1, last_updated = ? WHERE ad_id = ?', (int(time.time()), ad_id), commit=True)
        self._exec('INSERT OR IGNORE INTO user_metrics(user_id, ad_id, impressions, clicks, dislikes, last_updated) VALUES (?,?,?,?,?,?)', (user_id, ad_id, 0,0,0,int(time.time())), commit=True)
        self._exec('UPDATE user_metrics SET clicks = clicks + 1, last_updated = ? WHERE user_id=? AND ad_id=?', (int(time.time()), user_id, ad_id), commit=True)
        user_folder = os.path.join(self.users_root, user_id)
        if os.path.exists(user_folder):
            csv_path = os.path.join(user_folder, 'ads.csv')
            rows = {}
            if os.path.exists(csv_path):
                with open(csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        rows[r['ad_id']] = r
            r = rows.get(ad_id, {'ad_id':ad_id,'impressions':'0','clicks':'0','dislikes':'0','last_updated':''})
            r['clicks'] = str(int(r.get('clicks',0)) + 1)
            r['last_updated'] = datetime.utcnow().isoformat()
            rows[ad_id] = r
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow(['ad_id','impressions','clicks','dislikes','last_updated'])
                for v in rows.values():
                    w.writerow([v['ad_id'], v['impressions'], v['clicks'], v['dislikes'], v['last_updated']])

    def record_dislike(self, ad_id, user_id=None):
        self._exec('UPDATE ad_metrics SET dislikes = dislikes + 1, last_updated = ? WHERE ad_id = ?', (int(time.time()), ad_id), commit=True)
        self._exec('INSERT OR IGNORE INTO user_metrics(user_id, ad_id, impressions, clicks, dislikes, last_updated) VALUES (?,?,?,?,?,?)', (user_id, ad_id, 0,0,0,int(time.time())), commit=True)
        self._exec('UPDATE user_metrics SET dislikes = dislikes + 1, last_updated = ? WHERE user_id=? AND ad_id=?', (int(time.time()), user_id, ad_id), commit=True)
        
        user_folder = os.path.join(self.users_root, user_id)
        if os.path.exists(user_folder):
            csv_path = os.path.join(user_folder, 'ads.csv')
            rows = {}
            if os.path.exists(csv_path):
                with open(csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        rows[r['ad_id']] = r
            r = rows.get(ad_id, {'ad_id':ad_id,'impressions':'0','clicks':'0','dislikes':'0','last_updated':''})
            r['dislikes'] = str(int(r.get('dislikes',0)) + 1)
            r['last_updated'] = datetime.utcnow().isoformat()
            rows[ad_id] = r
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow(['ad_id','impressions','clicks','dislikes','last_updated'])
                for v in rows.values():
                    w.writerow([v['ad_id'], v['impressions'], v['clicks'], v['dislikes'], v['last_updated']])

    def get_ads_with_metrics(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT ad_id, impressions, clicks, dislikes FROM ad_metrics')
        rows = c.fetchall()
        conn.close()
        metrics = {r[0]: {'impressions': r[1], 'clicks': r[2], 'dislikes': r[3]} for r in rows}
        out = []
        for _, row in self.ads.iterrows():
            ad = row.to_dict()
            m = metrics.get(ad['ad_id'], {'impressions':0,'clicks':0,'dislikes':0})
            ctr = (m['clicks'] / m['impressions'] * 100) if m['impressions'] > 0 else 0.0
            ad_out = {
                'ad_id': ad.get('ad_id'),
                'title': ad.get('title',''),
                'description': ad.get('description',''),
                'image_url': ad.get('image_url',''),
                'target_page': ad.get('target_page',''),
                'category': ad.get('category',''),
                'details': ad.get('details',''),
                'impressions': m['impressions'],
                'clicks': m['clicks'],
                'dislikes': m['dislikes'],
                'ctr': round(ctr, 2)
            }
            out.append(ad_out)
        return out

    def get_admin_metrics(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT ad_id, impressions, clicks, dislikes, last_updated FROM ad_metrics')
        ads = [{'ad_id': r[0], 'impressions': r[1], 'clicks': r[2], 'dislikes': r[3], 'last_updated': r[4]} for r in c.fetchall()]
        c.execute('SELECT user_id, ad_id, impressions, clicks, dislikes, last_updated FROM user_metrics')
        users = [{'user_id': r[0], 'ad_id': r[1], 'impressions': r[2], 'clicks': r[3], 'dislikes': r[4], 'last_updated': r[5]} for r in c.fetchall()]
        
        c.execute('SELECT username, password FROM users')
        urows = [{'username': r[0], 'password': r[1]} for r in c.fetchall()]
        conn.close()
        
        folders = []
        try:
            for fn in os.listdir(self.users_root):
                path = os.path.join(self.users_root, fn)
                if os.path.isdir(path):
                    folders.append(fn)
        except Exception:
            folders = []
        return {'ads': ads, 'users_metrics': users, 'users_db': urows, 'user_folders': folders}
