from flask import Flask, render_template, request, redirect, url_for, session
import os
import sqlite3
from werkzeug.utils import secure_filename
import boto3

app = Flask(__name__)
app.secret_key = 'supersecretkey'
ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'png', 'txt'}

# إعدادات AWS S3
S3_BUCKET = "wizz-files-bucket"
S3_REGION = "us-east-1"

# استخدام IAM Role بدون مفاتيح
s3_client = boto3.client('s3', region_name=S3_REGION)


# قاعدة البيانات
def init_db():
    with sqlite3.connect('wizz.db') as conn:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS users (
                        username TEXT PRIMARY KEY,
                        password TEXT,
                        is_admin INTEGER,
                        uploads INTEGER DEFAULT 0,
                        downloads INTEGER DEFAULT 0)""")
        c.execute("SELECT * FROM users WHERE username='Youssef Ehab'")
        if not c.fetchone():
            c.execute("INSERT INTO users (username, password, is_admin) VALUES ('Youssef Ehab', '2468', 1)")
            c.execute("INSERT INTO users (username, password, is_admin) VALUES ('Ibrahim Mohamed', '2233', 0)")
            c.execute("INSERT INTO users (username, password, is_admin) VALUES ('Eslam Ibrahim', '3322', 0)")
            c.execute("INSERT INTO users (username, password, is_admin) VALUES ('Ahmed saaed', '88899', 0)")
        conn.commit()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with sqlite3.connect('wizz.db') as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
            user = c.fetchone()
            if user:
                session['username'] = user[0]
                session['is_admin'] = user[2]
                return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    username = session['username']
    is_admin = session['is_admin']

    with sqlite3.connect('wizz.db') as conn:
        c = conn.cursor()
        c.execute("SELECT uploads, downloads FROM users WHERE username=?", (username,))
        stats = c.fetchone()

        if is_admin:
            c.execute("SELECT username, uploads, downloads FROM users WHERE username != ?", (username,))
            users = c.fetchall()
        else:
            users = []

    
    # عرض ملفات S3
    files = []
    try:
        response = s3_client.list_objects_v2(Bucket=S3_BUCKET)
        for obj in response.get('Contents', []):
            files.append(obj['Key'])
    except Exception as e:
        print(f"Error fetching S3 files: {e}")
    
    return render_template('admin.html' if is_admin else 'user.html', username=username, stats=stats, users=users, files=files)

@app.route('/upload', methods=['POST'])
def upload():
    if 'username' not in session:
        return redirect(url_for('login'))
    file = request.files['file']
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        try:
            s3_client.upload_fileobj(file, S3_BUCKET, filename)
            with sqlite3.connect('wizz.db') as conn:
                c = conn.cursor()
                c.execute("UPDATE users SET uploads = uploads + 1 WHERE username=?", (session['username'],))
                conn.commit()
        except Exception as e:
            return f"Error uploading to S3: {e}"
    return redirect(url_for('dashboard'))

@app.route('/download/<filename>')
def download(filename):
    if 'username' not in session:
        return redirect(url_for('login'))
    with sqlite3.connect('wizz.db') as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET downloads = downloads + 1 WHERE username=?", (session['username'],))
        conn.commit()
    url = s3_client.generate_presigned_url('get_object', Params={'Bucket': S3_BUCKET, 'Key': filename}, ExpiresIn=300)
    return redirect(url)

@app.route('/delete_user/<username>')
def delete_user(username):
    if 'username' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))
    with sqlite3.connect('wizz.db') as conn:
        c = conn.cursor()
        c.execute("DELETE FROM users WHERE username=?", (username,))
        conn.commit()
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)

