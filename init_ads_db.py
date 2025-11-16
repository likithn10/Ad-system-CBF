import sqlite3
import csv
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ADS_DB = str(BASE_DIR / "ads.db")
CSV_PATH = str(BASE_DIR / "data" / "ad_inventory.csv")

# Connect to ads.db
conn = sqlite3.connect(ADS_DB)
c = conn.cursor()

# Create ads table if it doesn't exist
c.execute("""
CREATE TABLE IF NOT EXISTS ads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ad_id TEXT,
    title TEXT,
    category TEXT,
    keywords TEXT,
    target_page TEXT,
    image_url TEXT,
    ctr REAL DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    details TEXT,
    link TEXT
)
""")

# Load data from CSV
if os.path.exists(CSV_PATH):
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            c.execute("""
                INSERT INTO ads (ad_id, title, category, keywords, target_page, image_url, ctr, clicks, impressions, details, link)
                VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0, ?, ?)
            """, (
                row.get("ad_id"),
                row.get("title"),
                row.get("category"),
                row.get("keywords"),
                row.get("target_page"),
                row.get("image_url"),
                row.get("details", ""),
                row.get("link", "")
            ))
    conn.commit()
    print("✅ Ads imported successfully into ads.db")
else:
    print("❌ CSV file not found:", CSV_PATH)

conn.close()
