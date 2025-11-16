import sqlite3

DB_PATH = "ads.db"

SQL = """
DELETE FROM ads
WHERE id IN (
  SELECT a1.id
  FROM ads a1
  JOIN ads a2
    ON a1.title = a2.title
   AND a1.category = a2.category
   AND ifnull(a1.image_url, '') = ifnull(a2.image_url, '')
   AND a1.id <> a2.id
  WHERE ifnull(a1.clicks,0) + ifnull(a1.impressions,0) <
        ifnull(a2.clicks,0) + ifnull(a2.impressions,0)
);

DELETE FROM ads
WHERE id IN (
  SELECT a1.id
  FROM ads a1
  JOIN ads a2
    ON a1.title = a2.title
   AND a1.category = a2.category
   AND ifnull(a1.image_url, '') = ifnull(a2.image_url, '')
   AND a1.id > a2.id
);

-- OPTIONAL UNIQUE INDEX (see note below)
-- CREATE UNIQUE INDEX IF NOT EXISTS idx_ads_title_category_image
-- ON ads(title, category, image_url);
"""

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript(SQL)
    conn.commit()
    conn.close()
    print("ads.db cleaned.")
    
if __name__ == "__main__":
    main()