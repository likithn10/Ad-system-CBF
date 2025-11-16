import random
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
import sqlite3, os, json, time
from pathlib import Path
from csv import DictReader, writer
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "dev-secret-change-this"

# Limit uploads to 5 MB
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent
ADS_DB = str(BASE_DIR / "ads.db")
USERS_DB = str(BASE_DIR / "users.db")
USERS_FOLDER = BASE_DIR / "users"                  # for JSON and data files
STATIC_UPLOAD_ROOT = BASE_DIR / "static" / "users" # for web-served images
AD_CSV = str(BASE_DIR / "ad_inventory.csv")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

def open_ads_db():
    return sqlite3.connect(ADS_DB)

def open_users_db():
    return sqlite3.connect(USERS_DB)

# --- User folder prefs helpers ---
def get_user_folder(username):
    return USERS_FOLDER / username

def load_user_preferences(username):
    folder = get_user_folder(username)
    prefs_file = folder / "preferences.json"
    if prefs_file.exists():
        try:
            with open(prefs_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"likes": [], "dislikes": []}
    return {"likes": [], "dislikes": []}

def save_user_preferences(username, prefs):
    folder = get_user_folder(username)
    os.makedirs(folder, exist_ok=True)
    prefs_file = folder / "preferences.json"
    with open(prefs_file, "w", encoding="utf-8") as f:
        json.dump(prefs, f)

# --- Profile helpers (save JSON under users/<username>/profile.json) ---
def load_user_profile(username):
    folder = get_user_folder(username)
    os.makedirs(folder, exist_ok=True)
    path = folder / "profile.json"
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_user_profile(username, data):
    folder = get_user_folder(username)
    os.makedirs(folder, exist_ok=True)
    path = folder / "profile.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# --- Upload helpers (save images under static/users/<username>/...) ---
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def ensure_user_upload_dir(username: str) -> Path:
    user_dir = STATIC_UPLOAD_ROOT / username
    os.makedirs(user_dir, exist_ok=True)
    return user_dir

def save_uploaded_image(file_storage, username: str, prefix: str) -> str:
    """
    Saves an uploaded image for user and returns the web path like:
    /static/users/<username>/<saved_filename>
    """
    if not file_storage or file_storage.filename.strip() == "":
        return ""
    filename = secure_filename(file_storage.filename)
    if not allowed_file(filename):
        raise ValueError("Unsupported file type. Allowed: png, jpg, jpeg, gif, webp")
    user_dir = ensure_user_upload_dir(username)
    ts = int(time.time())
    root, ext = os.path.splitext(filename)
    saved_name = f"{prefix}_{ts}{ext.lower()}"
    saved_path = user_dir / saved_name
    file_storage.save(saved_path)
    # return web path
    return f"/static/users/{username}/{saved_name}"

# --- DB migrations / initializers ---
def ensure_links_column_and_populate():
    conn = open_ads_db(); c = conn.cursor()
    c.execute("PRAGMA table_info(ads)")
    cols = [r[1] for r in c.fetchall()]
    if "link" not in cols:
        try:
            c.execute("ALTER TABLE ads ADD COLUMN link TEXT")
            conn.commit()
        except Exception:
            pass

    # Populate from CSV if missing
    if os.path.exists(AD_CSV):
        try:
            by_title = {}
            with open(AD_CSV, "r", encoding="utf-8") as f:
                reader = DictReader(f)
                for row in reader:
                    t = (row.get("title") or "").strip()
                    if t:
                        by_title[t.lower()] = (row.get("link") or "").strip()
            c.execute("SELECT id, title, link FROM ads")
            for ad_id, title, link in c.fetchall():
                if title and (not link or link.strip() == ""):
                    cand = by_title.get(title.strip().lower(), "")
                    if cand:
                        c.execute("UPDATE ads SET link=? WHERE id=?", (cand, ad_id))
            conn.commit()
        except Exception:
            pass
    conn.close()

def ensure_publish_columns():
    """Add columns needed for user-published ads."""
    conn = open_ads_db(); c = conn.cursor()
    c.execute("PRAGMA table_info(ads)")
    cols = [r[1] for r in c.fetchall()]

    to_add = []
    if "owner" not in cols: to_add.append(("owner", "TEXT"))
    if "is_active" not in cols: to_add.append(("is_active", "INTEGER DEFAULT 1"))
    if "start_date" not in cols: to_add.append(("start_date", "TEXT"))
    if "end_date" not in cols: to_add.append(("end_date", "TEXT"))
    if "created_at" not in cols: to_add.append(("created_at", "TEXT"))
    for name, typ in to_add:
        try:
            c.execute(f"ALTER TABLE ads ADD COLUMN {name} {typ}")
        except Exception:
            pass
    conn.commit(); conn.close()

def ensure_csv_header():
    if not os.path.exists(AD_CSV):
        with open(AD_CSV, "w", encoding="utf-8", newline="") as f:
            w = writer(f)
            w.writerow([
                "ad_id","title","category","keywords","target_page","image_url",
                "ctr","clicks","impressions","details","link"
            ])

# --- Auth (register/login/logout) ---
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        if not username or not password:
            return render_template("register.html", error="Username & password required")

        conn = open_users_db()
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return render_template("register.html", error="Username already taken")
        conn.close()

        folder = get_user_folder(username)
        os.makedirs(folder, exist_ok=True)
        with open(folder / "details.txt", "w", encoding="utf-8") as f:
            f.write(f"Username: {username}\nPassword: {password}\n")
        save_user_preferences(username, {"likes": [], "dislikes": []})

        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")

        conn = open_users_db()
        c = conn.cursor()
        c.execute("SELECT id, username, password, role FROM users WHERE username=?", (username,))
        row = c.fetchone()
        conn.close()

        if not row:
            return render_template("login.html", error="No account found. Please register first.")
        elif row[2] != password:
            return render_template("login.html", error="Invalid credentials")
        else:
            session.clear()
            session["user"] = {"id": row[0], "username": row[1], "role": row[3] if len(row) > 3 else "user"}
            
            session["ad_seed"] = random.randint(1, 10**9)

            flash("Login successful!", "success")
            return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

# --- Main page ---
@app.route("/")
def index():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("index.html", user=session["user"])

# --- Ads API ---
@app.route("/get_ads")
def get_ads():
    conn = open_ads_db(); c = conn.cursor()
    c.execute("""SELECT id, title, category, keywords, target_page, image_url, ctr, clicks, impressions, details, link
                 FROM ads""")
    rows = c.fetchall()
    conn.close()

    ads = []
    for r in rows:
        ads.append({
            "id": int(r[0]),
            "title": r[1] or "",
            "category": r[2] or "",
            "keywords": r[3] or "",
            "target_page": r[4] or "",
            "image_url": r[5] or "",
            "ctr": float(r[6] or 0.0),
            "clicks": int(r[7] or 0),
            "impressions": int(r[8] or 0),
            "details": r[9] or "No details available.",
            "link": r[10] or ""
        })

    # Dedupe by title (keep highest CTR)
    dedup_map = {}
    for ad in ads:
        title = (ad.get("title") or "").strip()
        key = title.lower() if title else f"id-{ad['id']}"
        if key not in dedup_map or ad["ctr"] > dedup_map[key]["ctr"]:
            dedup_map[key] = ad
    ads = list(dedup_map.values())

    # Personalization sources
    prefs = {"likes": [], "dislikes": []}
    liked_categories = set()
    disliked_categories = set()
    if "user" in session:
        username = session["user"]["username"]
        prefs = load_user_preferences(username)
        conn = open_ads_db(); c = conn.cursor()
        for ad_id in prefs.get("likes", []):
            c.execute("SELECT category FROM ads WHERE id=?", (ad_id,))
            row = c.fetchone()
            if row and row[0]: liked_categories.add(row[0])
        for ad_id in prefs.get("dislikes", []):
            c.execute("SELECT category FROM ads WHERE id=?", (ad_id,))
            row = c.fetchone()
            if row and row[0]: disliked_categories.add(row[0])
        conn.close()

    # Stronger scoring already present above (LIKE_BOOST etc.)

    def session_jitter(ad_id: int) -> float:
        """
        Stable jitter per session to vary initial ranking after each login.
        Keeps order consistent during the session but different across logins.
        """
        seed = f"{session.get('ad_seed', 0)}:{ad_id}"
        rng = random.Random(seed)
        return rng.uniform(-3.0, 3.0)  # small nudge; CTR/likes dominate
    
    # Stronger scoring so rank visibly changes
    LIKE_BOOST = 15.0
    DISLIKE_PENALTY = 15.0
    CAT_LIKE_BOOST = 7.0
    CAT_DISLIKE_PENALTY = 7.0

    def score(ad):
        s = ad["ctr"] * 100.0  # base on CTR percent for visibility
        if "user" in session:
            if ad["id"] in prefs.get("likes", []): s += LIKE_BOOST
            if ad["id"] in prefs.get("dislikes", []): s -= DISLIKE_PENALTY
            if ad["category"] in liked_categories: s += CAT_LIKE_BOOST
            if ad["category"] in disliked_categories: s -= CAT_DISLIKE_PENALTY
        # NEW: session-stable jitter so order differs after each login
            s += session_jitter(ad["id"])
        return s

    for ad in ads:
        ad["score"] = score(ad)

    ads.sort(key=lambda a: a["score"], reverse=True)
    return jsonify(ads[:10])

# --- Engagement ---
@app.route("/like/<int:ad_id>", methods=["POST"])
def like_ad(ad_id):
    if "user" not in session:
        return jsonify({"error": "not logged in"}), 403
    username = session["user"]["username"]
    prefs = load_user_preferences(username)
    if ad_id not in prefs.get("likes", []):
        prefs["likes"].append(ad_id)
    if ad_id in prefs.get("dislikes", []):
        prefs["dislikes"].remove(ad_id)
    save_user_preferences(username, prefs)
    return jsonify({"status": "ok"})

@app.route("/dislike/<int:ad_id>", methods=["POST"])
def dislike_ad(ad_id):
    if "user" not in session:
        return jsonify({"error": "not logged in"}), 403
    username = session["user"]["username"]
    prefs = load_user_preferences(username)
    if ad_id not in prefs.get("dislikes", []):
        prefs["dislikes"].append(ad_id)
    if ad_id in prefs.get("likes", []):
        prefs["likes"].remove(ad_id)
    save_user_preferences(username, prefs)

    # optional CTR penalty
    conn = open_ads_db(); c = conn.cursor()
    c.execute("SELECT ctr FROM ads WHERE id=?", (ad_id,))
    row = c.fetchone()
    if row:
        old_ctr = float(row[0] or 0.0)
        new_ctr = max(0.0, old_ctr - 0.4)
        c.execute("UPDATE ads SET ctr = ? WHERE id=?", (new_ctr, ad_id))
        conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

@app.route("/click/<int:ad_id>", methods=["POST"])
def click_ad(ad_id):
    conn = open_ads_db(); c = conn.cursor()
    c.execute("UPDATE ads SET clicks = clicks + 1 WHERE id=?", (ad_id,))
    c.execute("""
        UPDATE ads
        SET ctr = CAST(clicks AS FLOAT) / CASE WHEN impressions = 0 THEN 1 ELSE impressions END
        WHERE id=?
    """, (ad_id,))
    conn.commit(); conn.close()
    return jsonify({"status": "ok"})

# --- Publish Ads (with image upload) ---
@app.route("/publish", methods=["GET", "POST"])
def publish():
    if "user" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        category = (request.form.get("category") or "").strip()
        keywords = (request.form.get("keywords") or "").strip()
        link = (request.form.get("link") or "").strip()
        details = (request.form.get("details") or "").strip()
        duration = int(request.form.get("duration_days") or "7")

        image_file = request.files.get("image_file")
        if not title or not image_file:
            flash("Title and Image are required.", "danger")
            return redirect(url_for("publish"))
        owner = session["user"]["username"]

        try:
            image_url = save_uploaded_image(image_file, owner, prefix="ad")
        except ValueError as ve:
            flash(str(ve), "danger")
            return redirect(url_for("publish"))

        start_dt = datetime.utcnow()
        end_dt = start_dt + timedelta(days=max(1, duration))
        created_at = start_dt

        conn = open_ads_db(); c = conn.cursor()
        c.execute("""INSERT INTO ads (title, category, keywords, target_page, image_url, ctr, clicks, impressions, details,
                                      link, owner, is_active, start_date, end_date, created_at)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                  (title, category, keywords, "", image_url, 0.0, 0, 0, details,
                   link, owner, 1, start_dt.isoformat(), end_dt.isoformat(), created_at.isoformat()))
        conn.commit()
        new_id = c.lastrowid
        conn.close()

        # CSV export/backup (optional)
        ensure_csv_header()
        with open(AD_CSV, "a", encoding="utf-8", newline="") as f:
            w = writer(f)
            w.writerow([
                new_id, title, category, keywords, "", image_url,
                0, 0, 0, details, link
            ])

        flash("Your ad has been published!", "success")
        return redirect(url_for("my_ads"))

    return render_template("publish.html")

@app.route("/my-ads")
def my_ads():
    if "user" not in session:
        return redirect(url_for("login"))
    owner = session["user"]["username"]
    conn = open_ads_db(); c = conn.cursor()
    c.execute("""SELECT id, title, category, image_url, clicks, impressions, ctr, is_active, start_date, end_date, created_at
                 FROM ads WHERE owner=? ORDER BY id DESC""", (owner,))
    rows = c.fetchall()
    conn.close()
    ads = []
    for r in rows:
        ads.append({
            "id": r[0], "title": r[1], "category": r[2], "image_url": r[3],
            "clicks": r[4], "impressions": r[5],
            "ctr": round((r[6] or 0.0)*100, 2) if isinstance(r[6], float) and r[6] <= 1 else round(r[6] or 0.0, 2),
            "is_active": r[7], "start_date": r[8], "end_date": r[9], "created_at": r[10],
        })
    return render_template("my-ads.html", ads=ads)

@app.route("/ad/toggle/<int:ad_id>", methods=["POST"])
def toggle_ad(ad_id):
    if "user" not in session:
        return jsonify({"error": "not logged in"}), 403
    owner = session["user"]["username"]
    conn = open_ads_db(); c = conn.cursor()
    c.execute("SELECT owner, is_active FROM ads WHERE id=?", (ad_id,))
    row = c.fetchone()
    if not row or row[0] != owner:
        conn.close()
        return jsonify({"error": "not found or unauthorized"}), 404
    new_state = 0 if int(row[1] or 1) == 1 else 1
    c.execute("UPDATE ads SET is_active=? WHERE id=?", (new_state, ad_id))
    conn.commit(); conn.close()
    return jsonify({"status": "ok", "is_active": new_state})

@app.route("/ad/delete/<int:ad_id>", methods=["POST"])
def delete_ad(ad_id):
    if "user" not in session:
        return jsonify({"error": "not logged in"}), 403
    owner = session["user"]["username"]
    conn = open_ads_db(); c = conn.cursor()
    c.execute("SELECT owner FROM ads WHERE id=?", (ad_id,))
    row = c.fetchone()
    if not row or row[0] != owner:
        conn.close()
        return jsonify({"error": "not found or unauthorized"}), 404
    c.execute("DELETE FROM ads WHERE id=?", (ad_id,))
    conn.commit(); conn.close()
    return jsonify({"status": "ok"})

# --- Profile (with photo upload saved per user) ---
@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user" not in session:
        return redirect(url_for("login"))
    username = session["user"]["username"]

    if request.method == "POST":
        # Load existing to preserve old photo if none uploaded
        current = load_user_profile(username)
        profile = {
            "full_name": (request.form.get("full_name") or "").strip(),
            "email": (request.form.get("email") or "").strip(),
            "gender": (request.form.get("gender") or "").strip(),
            "dob": (request.form.get("dob") or "").strip(),
            "photo_url": current.get("photo_url", ""),
            "phone": (request.form.get("phone") or "").strip(),
            "address": (request.form.get("address") or "").strip(),
            "updated_at": datetime.utcnow().isoformat()
        }

        photo_file = request.files.get("photo_file")
        if photo_file and photo_file.filename.strip():
            try:
                profile["photo_url"] = save_uploaded_image(photo_file, username, prefix="profile")
            except ValueError as ve:
                flash(str(ve), "danger")
                return redirect(url_for("profile"))

        save_user_profile(username, profile)
        flash("Profile saved.", "success")
        return redirect(url_for("profile"))

    current = load_user_profile(username)
    return render_template("profile.html", profile=current)

# --- Admin (unchanged) ---
@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if username == "admin" and password == "admin123":
            session.clear()
            session["user"] = {"username": "admin", "role": "admin"}
            return redirect(url_for("admin"))
        return render_template("admin-login.html", error="Invalid admin credentials")
    return render_template("admin-login.html")

@app.route("/admin")
def admin():
    if "user" not in session or session["user"].get("role") != "admin":
        return redirect(url_for("admin_login"))

    conn = open_users_db(); c = conn.cursor()
    c.execute("SELECT id, username, password, role FROM users")
    users = c.fetchall()
    conn.close()

    conn = open_ads_db(); c = conn.cursor()
    c.execute("SELECT id, title, category, image_url, ctr, clicks, impressions FROM ads")
    ads = c.fetchall()
    conn.close()

    return render_template("admin.html", users=users, ads=ads)

# --- Startup ---
if __name__ == "__main__":
    os.makedirs(USERS_FOLDER, exist_ok=True)
    os.makedirs(STATIC_UPLOAD_ROOT, exist_ok=True)

    if not os.path.exists(ADS_DB):
        conn = open_ads_db(); c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            category TEXT,
            keywords TEXT,
            target_page TEXT,
            image_url TEXT,
            ctr REAL DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            impressions INTEGER DEFAULT 0,
            details TEXT
        )""")
        conn.commit(); conn.close()
        print("Initialized ads.db")

    if not os.path.exists(USERS_DB):
        conn = open_users_db(); c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT DEFAULT 'user'
        )""")
        conn.commit(); conn.close()
        print("Initialized users.db")

    ensure_links_column_and_populate()
    ensure_publish_columns()
    ensure_csv_header()

    app.run(debug=True)