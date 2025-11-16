1) Copy your old ads.db into the project root (same folder as app.py).
2) Add ad images to static/images/ (filenames referenced in ads.db image_url column).
3) Ensure static folder structure:
   static/css/style.css
   static/css/js/script.js
   static/images/...
4) Create venv:
   python -m venv venv
   venv\Scripts\activate   (Windows)
   source venv/bin/activate (mac/Linux)
5) Install:
   pip install -r requirements.txt
6) Run:
   python app.py
