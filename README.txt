Ad-system-CBF

A machine-learning powered advertising system that uses Content-Based Filtering (CBF) and Click-Through Rate (CTR) analysis to recommend and display the most relevant ads to users.
This system helps small businesses and startups upload, manage, and display ads efficiently.
To attract users to the website i have created a Iframe where i have added a daily use website which is a Cloud Blood Bank system so people come to use it and ads will be recomended to them

🚀 Features

* Content-Based Filtering for personalized recommendations
* CTR-based ranking for better ad performance
* Upload and manage ads easily
* Supports images (stored in static/images/)
* SQLite database for ads and users
* Web interface built using Flask
* Lightweight and beginner-friendly project

📂 Project Structure
Ad-system-CBF/
│── app.py
│── models.py
│── requirements.txt
│── README.md
│── templates/       # HTML templates (Flask)
│── static/          # CSS, JS, Images
│── data/            # Additional datasets
│── users/           # User data folder
│── backup_db/       # Backup database files
│── ads.db           # Ads database (Adds added by Owner)
│── users.db         # Users database (Seperate Floders for all)

🛠️ Installation & Setup
1️⃣ Install dependencies
pip install -r requirements.txt

2️⃣ Place your .db files
Put these files in the project root:

ads.db
users.db

3️⃣ Ensure images folder exists

Add your ad images to:
static/images/

4️⃣ Run the application
python app.py

-> Application runs at:
http://127.0.0.1:5000/

📸 Screenshots 
You can include screenshots here:


📊 How the Recommendation Works

* Ads are processed based on keywords, tags, and features
* User preferences + ad metadata → similarity score
* CTR is used to boost high-performing ads
* Final ranked ads are displayed to the user


📄 License

This project is licensed under the MIT License.

👤 Author

Likith N
GitHub: https://github.com/likithn10
