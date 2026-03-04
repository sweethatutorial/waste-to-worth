import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
from werkzeug.utils import secure_filename
from collections import Counter
from math import ceil
from datetime import datetime
from flask import send_from_directory
from datetime import datetime
from flask import jsonify, request
import math
from geopy.geocoders import Nominatim
import time

app = Flask(__name__)
app.secret_key = "zero_to_connect_secret_key"


def get_lat_lng(location_name):
    geolocator = Nominatim(user_agent="food_emergency_app")

    try:
        location = geolocator.geocode(location_name)
        time.sleep(1)  # avoid too many fast requests

        if location:
            return location.latitude, location.longitude
        else:
            return None, None
    except:
        return None, None

def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in KM

    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)

    a = (math.sin(dLat/2) ** 2 +
         math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) *
         math.sin(dLon/2) ** 2)

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

ALLOWED_EXTENSIONS={"png","jpg","jpeg","gif"}


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ===== Upload Folders =====
UPLOAD_FOLDER = "static/uploads"
DONATION_FOLDER = os.path.join(UPLOAD_FOLDER, "donations")
PROFILE_FOLDER = os.path.join(UPLOAD_FOLDER, "profiles")
CERT_FOLDER = os.path.join(UPLOAD_FOLDER, "certificates")

for folder in [UPLOAD_FOLDER, DONATION_FOLDER, PROFILE_FOLDER, CERT_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["DONATION_UPLOAD_FOLDER"] = DONATION_FOLDER
app.config["PROFILE_UPLOAD_FOLDER"] = PROFILE_FOLDER
app.config["CERTIFICATE_UPLOAD_FOLDER"] = CERT_FOLDER
app.config['CERT_FOLDER'] = os.path.join('static', 'uploads', 'certificates')


# ===== Database Initialization =====
def init_db():
    db = sqlite3.connect("database.db")
    cur = db.cursor()

    # Users
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        phone TEXT,
        password TEXT,
        role TEXT,
        profile_image TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # NGO
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ngo_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ngo_name TEXT,
        email TEXT UNIQUE,
        phone TEXT,
        location TEXT,
        certificate TEXT,
        password TEXT
    )
    """)

    # Donations
    cur.execute("""
    CREATE TABLE IF NOT EXISTS donations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        title TEXT,
        description TEXT,
        category TEXT,
        condition TEXT,
        city TEXT,
        address TEXT,
        landmark TEXT,
        contact TEXT,
        emergency INTEGER DEFAULT 0,
        image TEXT,
        status TEXT DEFAULT 'Pending',
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        accepted_at TIMESTAMP,
        completed_at TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ngo_applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        volunteer_id INTEGER,
        ngo_id INTEGER,
        message TEXT,
        experience TEXT,
        certificate TEXT,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'Pending',
        FOREIGN KEY(volunteer_id) REFERENCES users(id),
        FOREIGN KEY(ngo_id) REFERENCES users(id)
    )
    """)
    db.commit()
    db.close()


# ===== Database connection =====
def get_db():
    db_path = os.path.join(os.path.dirname(__file__), "database.db")
    conn = sqlite3.connect(db_path, timeout=20, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

#====notification======
def create_notification(user_id, message):
    conn = get_db()
    conn.execute("""
        INSERT INTO notifications (user_id, message, is_read, created_at)
        VALUES (?, ?, 0, CURRENT_TIMESTAMP)
    """, (user_id, message))
    conn.commit()
    conn.close()


# ===== Routes =====
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        role = request.form["role"]

        db = get_db()
        cur = db.cursor()
        cur.execute(
            "SELECT * FROM users WHERE email=? AND password=? AND role=?",
            (email, password, role)
        )
        user = cur.fetchone()
        db.close()

        if user:
            session['user_id'] = user["id"]
            session['role'] = user["role"]

            if role == "donor":
                return redirect(url_for("donor_dashboard"))
            elif role == "ngo":
                return redirect(url_for("ngo_dashboard"))
            elif role == "volunteer":
                return redirect(url_for("volunteer_dashboard"))
        else:
            flash("Account not found", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))



# ===== Donor Dashboard =====
@app.route("/donor_dashboard")
def donor_dashboard():
    if "user_id" not in session or session.get("role") != "donor":
        return redirect(url_for("login"))

    conn = get_db()
    donations = conn.execute(
        "SELECT * FROM donations WHERE user_id=? ORDER BY uploaded_at DESC",
        (session["user_id"],)
    ).fetchall()

    total = len(donations)
    status_counts = Counter((d["status"] or "Pending").title() for d in donations)

    completed = status_counts.get("Completed", 0)
    pending = status_counts.get("Pending", 0)
    accepted = status_counts.get("Accepted", 0)
    rejected = status_counts.get("Rejected", 0)
    in_transit = status_counts.get("In Transit", 0)
    active = pending + accepted + in_transit

    category_counts = Counter((d["category"] or "Other") for d in donations)
    categories = list(category_counts.keys())
    category_values = list(category_counts.values())

    completion_rate = int((completed / total) * 100) if total > 0 else 0
    conn.close()

    return render_template(
        "donor_dashboard.html",
        donations=donations,
        total=total,
        active=active,
        completed=completed,
        pending=pending,
        accepted=accepted,
        rejected=rejected,
        in_transit=in_transit,
        categories=categories,
        category_values=category_values,
        completion_rate=completion_rate
    )

#=======-===signup=======
@app.route("/signup_select", methods=["GET", "POST"])
def signup_select():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        role = request.form["role"]

        db = get_db()
        cur = db.cursor()

        # insert user
        cur.execute(
            "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
            (username, email, password, role)
        )

        db.commit()
        db.close()

        return redirect("/login")

    return render_template("signup_select.html")

@app.route("/signup/ngo", methods=["GET", "POST"])
def signup_ngo():
    error = None

    if request.method == "POST":

        ngo_name = request.form.get("ngo_name")
        contact_person = request.form.get("contact_person")
        email = request.form.get("email")
        phone = request.form.get("phone")
        location = request.form.get("location")
        city = location
        password = request.form.get("password")
        confirm = request.form.get("confirm_password")
        certificate = request.files.get("ngo_certificate")

        if not confirm or password != confirm:
            error = "Passwords do not match"
            return render_template("signup_ngo.html", error=error)

        if not certificate or certificate.filename == "":
            error = "Please upload a certificate"
            return render_template("signup_ngo.html", error=error)

        # ✅ SAVE CERTIFICATE FILE
        filename = secure_filename(certificate.filename)
        certificate_path = os.path.join(
            app.config["CERTIFICATE_UPLOAD_FOLDER"], filename
        )
        certificate.save(certificate_path)

        db = get_db()
        cur = db.cursor()

        try:
            # ✅ SAVE filename in DB
            cur.execute("""
                INSERT INTO ngo_users
                (ngo_name, email, phone, location, city, certificate, password)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (ngo_name, email, phone, location, city, filename, password))

            cur.execute("""
                INSERT INTO users
                (name, email, password, role, status, certificate, city)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (ngo_name, email, password, "ngo", "Pending", filename, city))

            db.commit()
            db.close()

            return redirect("/login")

        except sqlite3.IntegrityError:
            db.close()
            error = "Email already exists"
            return render_template("signup_ngo.html", error=error)

    return render_template("signup_ngo.html")


@app.route("/signup/donor", methods=["GET", "POST"])
def signup_donor():
    error = None

    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        password = request.form.get("password")
        confirm = request.form.get("confirm_password")

        if password != confirm:
            error = "Passwords do not match"
            return render_template("signup_donor.html", error=error)

        db = get_db()
        cur = db.cursor()

        try:
            # Insert into users table
            cur.execute("""
                INSERT INTO users (name, email, password, role)
                VALUES (?, ?, ?, ?)
            """, (name, email, password, "donor"))

            db.commit()
            db.close()

            flash("Registered Successfully. Please Login.")
            return redirect("/login")

        except:
            db.close()
            error = "Email already exists"

    return render_template("signup_donor.html", error=error)


@app.route("/signup/volunteer", methods=["GET", "POST"])
def volunteer_signup():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        phone = request.form["phone"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]
        certificate = request.files.get("certificate")

        # 🔐 Password validation
        if password != confirm_password:
            return "Passwords do not match"

        filename = None

        # 📁 Optional certificate upload
        if certificate and certificate.filename != "":
            filename = secure_filename(certificate.filename)
            certificate.save(os.path.join("static/uploads/volunteers", filename))

        db = get_db()
        cur = db.cursor()

        cur.execute(
            "INSERT INTO users (name, email, phone, password, role, certificate) VALUES (?, ?, ?, ?, ?, ?)",
            (name, email, phone, password, "volunteer", filename)
        )

        db.commit()
        db.close()

        return redirect("/login")

    return render_template("volunteer_signup.html")

# ---------- Dashboard ----------

def donor_dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "donor":
        return "Access Denied"

    conn = get_db()
    cur = conn.cursor()
    
    cur.execute(
        "SELECT * FROM donations WHERE user_id=? ORDER BY uploaded_at DESC",
        (session["user_id"],)
    )
    donations = cur.fetchall()

    # Fetch notifications
    cur.execute("""
        SELECT * FROM notifications
        WHERE user_id=?
        ORDER BY created_at DESC
    """, (session["user_id"],))
    notifications_list = cur.fetchall()

    total = len(donations)

    # Normalize status values
    status_counts = Counter(
        (d["status"] or "Pending").strip().title()
        for d in donations
    )

    completed = status_counts.get("Completed", 0)
    pending = status_counts.get("Pending", 0)
    accepted = status_counts.get("Accepted", 0)
    rejected = status_counts.get("Rejected", 0)
    in_transit = status_counts.get("In Transit", 0)

    # Active = not completed & not rejected
    active = pending + accepted + in_transit

    category_counts = Counter(
        (d["category"] or "Other")
        for d in donations
    )

    categories = list(category_counts.keys())
    category_values = list(category_counts.values())

    completion_rate = int((completed / total) * 100) if total > 0 else 0

    for d in donations:
        cur.execute("""
            SELECT l.*, u.name as updated_by_name
            FROM donation_status_log l
            LEFT JOIN users u ON u.id = l.updated_by
            WHERE donation_id=?
            ORDER BY updated_at ASC
        """, (d["id"],))
        d['status_logs'] = cur.fetchall()
    ### --- END NEW PART --- ###

    conn.close()

    return render_template(
        "donor_dashboard.html",
        donations=donations,
        total=total,
        active=active,
        completed=completed,
        pending=pending,
        accepted=accepted,
        rejected=rejected,
        in_transit=in_transit,
        categories=categories,
        category_values=category_values,
        completion_rate=completion_rate,
        notifications_list=notifications_list
    )

# ===== Profile =====
@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    user = conn.execute(
        "SELECT * FROM users WHERE id=?",
        (session["user_id"],)
    ).fetchone()

    total = conn.execute(
        "SELECT COUNT(*) FROM donations WHERE user_id=?",
        (session["user_id"],)
    ).fetchone()[0]

    completed = conn.execute(
        "SELECT COUNT(*) FROM donations WHERE user_id=? AND LOWER(status)='completed'",
        (session["user_id"],)
    ).fetchone()[0]

    pending = conn.execute(
        "SELECT COUNT(*) FROM donations WHERE user_id=? AND LOWER(status)='pending'",
        (session["user_id"],)
    ).fetchone()[0]

    conn.close()

    return render_template(
        "profile.html",
        user=user,
        total=total,
        completed=completed,
        pending=pending
    )

@app.route("/edit_profile", methods=["GET", "POST"])
def edit_profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    if request.method == "POST":
        name = request.form["name"]
        image = request.files.get("profile_image")

        # Get existing image first
        user = conn.execute(
            "SELECT profile_image FROM users WHERE id=?",
            (session["user_id"],)
        ).fetchone()

        filename = user["profile_image"]  # keep old image

        # If new image uploaded
        if image and image.filename != "":
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config["PROFILE_UPLOAD_FOLDER"], filename))

        # Update name + image
        conn.execute(
            "UPDATE users SET name=?, profile_image=? WHERE id=?",
            (name, filename, session["user_id"])
        )

        conn.commit()
        conn.close()
        return redirect(url_for("profile"))

    user = conn.execute(
        "SELECT * FROM users WHERE id=?",
        (session["user_id"],)
    ).fetchone()

    conn.close()
    return render_template("edit_profile.html", user=user)
# ===== Upload Donation =====
@app.route("/upload_donation", methods=["GET", "POST"])
def upload_donation():
    if "user_id" not in session or session.get("role") != "donor":
        return redirect(url_for("login"))

    if request.method == "POST":
        data = request.form
        donation_image = request.files.get("donation_image")
        image_filename = None
        if donation_image and donation_image.filename != "":
            image_filename = secure_filename(donation_image.filename)
            donation_image.save(
                os.path.join(app.config["DONATION_UPLOAD_FOLDER"], image_filename)
    )
        conn = get_db()
        cur=conn.cursor()
        conn.execute("""
            INSERT INTO donations
            (user_id, title, description, category, condition, city, address, landmark, contact, emergency, image ,status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ? ,?)
        """, (
            session["user_id"], data.get("title"), data.get("description"), data.get("category"),
            data.get("condition"), data.get("city"), data.get("address"), data.get("landmark"),
            data.get("contact"), 1 if data.get("emergency") else 0, image_filename, "Pending"
        ))
        donation_id = cur.lastrowid
        conn.commit()

        # Notify all NGOs + volunteers
        users_to_notify = conn.execute("SELECT id FROM users WHERE role IN ('ngo','volunteer')").fetchall()
        for u in users_to_notify:
            create_notification(u["id"], f"New donation '{data.get('title')}' uploaded by donor!")

        conn.close()
        flash("Donation uploaded successfully!")
        return redirect(url_for("donor_dashboard"))

    return render_template("upload_donation.html")

# ===== Placeholder Dashboards =====

@app.route("/ngo_dashboard")
def ngo_dashboard():
    if "user_id" not in session or session.get("role") != "ngo":
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor()


    total = conn.execute(
        "SELECT COUNT(*) FROM donations WHERE ngo_id=?",
        (session["user_id"],)
    ).fetchone()[0]

    # Pending
    pending = conn.execute(
        "SELECT COUNT(*) FROM donations WHERE ngo_id=? AND status='Pending'",
        (session["user_id"],)
    ).fetchone()[0]

    # Accepted
    accepted = conn.execute(
        "SELECT COUNT(*) FROM donations WHERE ngo_id=? AND status='Accepted'",
        (session["user_id"],)
    ).fetchone()[0]

    # Completed
    completed = conn.execute(
        "SELECT COUNT(*) FROM donations WHERE ngo_id=? AND status='Completed'",
        (session["user_id"],)
    ).fetchone()[0]

    # Accepted but not completed
    in_progress = conn.execute(
        "SELECT COUNT(*) FROM donations WHERE ngo_id=? AND status='Accepted'",
        (session["user_id"],)
    ).fetchone()[0]

    # Fetch notifications for NGO
    cur.execute("""
        SELECT * FROM notifications
        WHERE user_id=?
        ORDER BY created_at DESC
    """, (session["user_id"],))
    notifications_list = cur.fetchall()
    conn.close()

    return render_template(
        "ngo_dashboard.html",
        notifications_list=notifications_list,
        total=total,
        pending=pending,
        accepted=accepted,
        completed=completed,
        in_progress=in_progress
    )


@app.route("/volunteer_dashboard")
def volunteer_dashboard():
    if "user_id" not in session or session.get("role") != "volunteer":
     return redirect(url_for("login"))

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Get volunteer details
    cur.execute("SELECT * FROM  users volunteers WHERE id = ? AND role='volunteer'", 
                (session["user_id"],))
    volunteer = cur.fetchone()

    # Fetch notifications for volunteer
    cur.execute("""
        SELECT * FROM notifications
        WHERE user_id=?
        ORDER BY created_at DESC
    """, (session["user_id"],))
    notifications_list = cur.fetchall()

    conn.close()

    return render_template("volunteer_dashboard.html", volunteer=volunteer,notifications_list=notifications_list)
#=====admin=======
# admin credentials
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "admin123"

@app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    if request.method=="POST":
        email = request.form["email"]
        password = request.form["password"]
        if email==ADMIN_EMAIL and password==ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid credentials", "error")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin_login"))

@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    conn = get_db()
    total_donors = conn.execute("SELECT COUNT(*) FROM users WHERE role='donor'").fetchone()[0]
    total_ngos = conn.execute("SELECT COUNT(*) FROM users WHERE role='ngo'").fetchone()[0]
    total_volunteers = conn.execute("SELECT COUNT(*) FROM users WHERE role='volunteer'").fetchone()[0]
    total_donations = conn.execute("SELECT COUNT(*) FROM donations").fetchone()[0]
    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_donors=total_donors,
        total_ngos=total_ngos,
        total_volunteers=total_volunteers,
        total_donations=total_donations
    )


# Manage Donors Page
@app.route('/admin/manage_donors')
def manage_donors():
    conn = get_db()
    donors = conn.execute("""
    SELECT * FROM users 
    WHERE role='donor'
    ORDER BY 
        CASE 
            WHEN status = 'Pending' THEN 1
            WHEN status = 'Verified' THEN 2
            WHEN status = 'Rejected' THEN 3
        END
""").fetchall()
    conn.close()
    return render_template("manage_donors.html", donors=donors)

# Accept Donor
@app.route('/admin/accept_donor/<int:donor_id>')
def accept_donor(donor_id):
    conn = get_db()
    conn.execute("UPDATE users SET status='Verified' WHERE id=?", (donor_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('manage_donors'))

# Reject Donor
@app.route('/admin/reject_donor/<int:donor_id>')
def reject_donor(donor_id):
    conn = get_db()
    conn.execute("UPDATE users SET status='Rejected' WHERE id=?", (donor_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('manage_donors'))

@app.route("/admin/manage_ngos")
def manage_ngos():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    conn = get_db()  # open connection
    ngos = conn.execute("SELECT * FROM users WHERE role='ngo'").fetchall()
    conn.close()  # close connection after query

    return render_template("manage_ngos.html", ngos=ngos)
@app.route('/admin/accept_ngo/<int:ngo_id>')
def accept_ngo(ngo_id):
    conn = get_db()
    conn.execute(
        "UPDATE users SET status='Verified' WHERE id=? AND role='ngo'",
        (ngo_id,)
    )
    conn.commit()
    conn.close()
    return redirect(url_for('manage_ngos'))


@app.route('/admin/reject_ngo/<int:ngo_id>')
def reject_ngo(ngo_id):
    conn = get_db()
    conn.execute(
        "UPDATE users SET status='Rejected' WHERE id=? AND role='ngo'",
        (ngo_id,)
    )
    conn.commit()
    conn.close()
    return redirect(url_for('manage_ngos'))

@app.route('/manage_volunteers')
def manage_volunteers():
    conn = get_db()
    volunteers = conn.execute(
        "SELECT * FROM users WHERE role='volunteer' ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return render_template('manage_volunteers.html', volunteers=volunteers)

# --- Edit Volunteer (GET + POST) ---
# EDIT VOLUNTEER
@app.route('/edit_volunteer/<int:id>', methods=['GET', 'POST'])
def edit_volunteer(id):
    conn = get_db()
    cur = conn.cursor()

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']

        cur.execute("""
            UPDATE users 
            SET name=?, email=?, phone=? 
            WHERE id=? AND role='volunteer'
        """, (name, email, phone, id))

        conn.commit()
        conn.close()
        return redirect('/manage_volunteers')

    cur.execute("SELECT * FROM users WHERE id=? AND role='volunteer'", (id,))
    volunteer = cur.fetchone()
    conn.close()

    return render_template('edit_volunteer.html', volunteer=volunteer)


# DELETE VOLUNTEER
@app.route('/delete_volunteer/<int:id>')
def delete_volunteer(id):
    conn = get_db()
    conn.execute("DELETE FROM users WHERE id=? AND role='volunteer'", (id,))
    conn.commit()
    conn.close()
    return redirect('/manage_volunteers')

@app.route("/admin/manage_donations")
def manage_donations():
    # Check if admin is logged in
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    conn = get_db()
    donations = conn.execute("SELECT * FROM donations").fetchall()  # Assuming a 'donations' table
    conn.close()

    return render_template("manage_donations.html", donations=donations)

@app.route("/browse_ngos")
def browse_ngos():
    if "user_id" not in session or session.get("role") != "volunteer":
        return redirect(url_for("login"))

    conn = get_db()
    
    # Get verified NGOs with their location from ngo_users table
    ngos = conn.execute("""
        SELECT u.id, u.name, u.email, n.location
        FROM users u
        JOIN ngo_users n ON u.email = n.email
        WHERE u.role='ngo' AND u.status='Verified'
        ORDER BY u.name ASC
    """).fetchall()
    
    conn.close()

    message = None
    if not ngos:
        message = "No NGOs available right now."

    return render_template("browse_ngos.html", ngos=ngos, message=message)

@app.route("/apply/<int:ngo_id>", methods=["GET", "POST"])
def apply_ngo(ngo_id):
    if "user_id" not in session or session.get("role") != "volunteer":
        return redirect(url_for("login"))

    conn = get_db()

    # Fetch NGO details
    ngo = conn.execute(
        "SELECT * FROM users WHERE id=? AND role='ngo' AND status='Verified'",
        (ngo_id,)
    ).fetchone()

    if not ngo:
        conn.close()
        flash("NGO not found or not verified", "error")
        return redirect(url_for("browse_ngos"))

    if request.method == "POST":
        message = request.form.get("message")
        experience = request.form.get("experience")
        certificate_file = request.files.get("certificate")

        # Check if volunteer already applied
        existing_app = conn.execute("""
            SELECT * FROM ngo_applications
            WHERE volunteer_id=? AND ngo_id=?
        """, (session["user_id"], ngo_id)).fetchone()

        if existing_app:
            flash("You have already applied to this NGO", "error")
            conn.close()
            return redirect(url_for("browse_ngos"))

        filename = None
        if experience == "Experienced":
            if not certificate_file or certificate_file.filename == "":
                flash("Certificate required for experienced volunteers", "error")
                conn.close()
                return redirect(url_for("apply_ngo", ngo_id=ngo_id))
            filename = secure_filename(certificate_file.filename)
            certificate_file.save(os.path.join(app.config["CERTIFICATE_UPLOAD_FOLDER"], filename))

        # Insert application
        conn.execute("""
            INSERT INTO ngo_applications
            (volunteer_id, ngo_id, message, experience, certificate)
            VALUES (?, ?, ?, ?, ?)
        """, (session["user_id"], ngo_id, message, experience, filename))
        conn.commit()
        conn.close()

        flash("Application submitted successfully!")
        return redirect(url_for("browse_ngos"))

    conn.close()
    return render_template("apply_form.html", ngo=ngo)

@app.route('/my_application')
def my_application():
    volunteer_id = session.get('user_id')
    conn = get_db()
    application = conn.execute(
        "SELECT a.id, a.message, a.experience, a.status, a.certificate, u.name AS ngo_name "
        "FROM ngo_applications a JOIN users u ON a.ngo_id = u.id "
        "WHERE a.volunteer_id = ?", (volunteer_id,)
    ).fetchone()
    conn.close()
    
    return render_template('my_application.html', application=application)

@app.route('/view_certificate/<filename>')
def view_certificate(filename):
    return send_from_directory(app.config['CERT_FOLDER'], filename)


@app.route('/ngo_applications', methods=['GET', 'POST'])
def ngo_applications():

    # ✅ Protect route
    if 'user_id' not in session:
        return redirect(url_for('login'))

    ngo_id = session['user_id']
    conn = get_db()

    # ✅ Handle status update safely
    if request.method == 'POST':
        app_id = request.form.get('app_id')
        new_status = request.form.get('status')

        if app_id and new_status:
            conn.execute(
                "UPDATE ngo_applications SET status=? WHERE id=? AND ngo_id=?",
                (new_status, app_id, ngo_id)
            )
            conn.commit()
            flash("Status updated successfully!", "success")

        return redirect(url_for('ngo_applications'))

    # ✅ Get filter/search parameters
    status_filter = request.args.get('status', 'All')
    search_query = request.args.get('search', '')

    # ✅ Build query dynamically
    query = """
        SELECT a.id, a.message, a.experience, a.status, a.certificate,
               u.name AS volunteer_name, u.email
        FROM ngo_applications a
        JOIN users u ON a.volunteer_id = u.id
        WHERE a.ngo_id=?
    """
    params = [ngo_id]

    if status_filter != 'All':
        query += " AND a.status=?"
        params.append(status_filter)

    if search_query:
        query += " AND u.name LIKE ?"
        params.append(f"%{search_query}%")

    applications = conn.execute(query, params).fetchall()
    conn.close()

    return render_template(
        'ngo_applications.html',
        applications=applications,
        status_filter=status_filter,
        search_query=search_query
    )

@app.route('/update_application_status/<int:app_id>/<status>')
def update_application_status(app_id, status):
    conn = get_db()
    conn.execute(
        "UPDATE ngo_applications SET status = ? WHERE id = ?", (status, app_id)
    )
    conn.commit()
    conn.close()
    flash(f"Application {status} successfully!")
    return redirect(url_for('ngo_applications'))

@app.route('/delete_application/<int:app_id>', methods=['POST'])
def delete_application(app_id):
    # Ensure volunteer is logged in
    volunteer_id = session.get('user_id')
    if not volunteer_id:
        flash("You need to log in first.", "error")
        return redirect(url_for("login"))

    conn = get_db()

    # Check if the application belongs to this volunteer
    application = conn.execute(
        "SELECT * FROM ngo_applications WHERE id = ? AND volunteer_id = ?",
        (app_id, volunteer_id)
    ).fetchone()

    if application:
        conn.execute("DELETE FROM ngo_applications WHERE id = ?", (app_id,))
        conn.commit()
        flash("Application deleted successfully.", "success")
    else:
        flash("Application not found or access denied.", "error")

    conn.close()
    return redirect(url_for('my_application'))

from datetime import datetime

@app.route("/ngo_donations")
def ngo_donations():

    if "user_id" not in session or session.get("role") != "ngo":
        return redirect(url_for("login"))

    conn = get_db()

    donations = conn.execute("""
        SELECT *
        FROM donations
        WHERE status='Pending'
        ORDER BY uploaded_at DESC
    """).fetchall()

    donation_list = []

    for d in donations:
        created = datetime.strptime(d["uploaded_at"], "%Y-%m-%d %H:%M:%S")
        now = datetime.now()

        if created.date() == now.date():
            formatted = "Today " + created.strftime("%I:%M %p")
        elif (now.date() - created.date()).days == 1:
            formatted = "Yesterday " + created.strftime("%I:%M %p")
        else:
            formatted = created.strftime("%d %b %Y %I:%M %p")

        donation_list.append({
            **dict(d),
            "formatted_date": formatted
        })

    conn.close()

    return render_template("ngo_donations.html", donations=donation_list)


@app.route('/accept_donation/<int:donation_id>', methods=["POST"])
def accept_donation(donation_id):

    if "user_id" not in session or session.get("role") != "ngo":
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor()

    # Fetch donation properly
    cur.execute("SELECT * FROM donations WHERE id=?", (donation_id,))
    donation = cur.fetchone()

    if donation is None:
        flash("Donation not found!")
        conn.close()
        return redirect(url_for("ngo_dashboard"))

    # Update correctly
    conn.execute("""
        UPDATE donations
        SET status=?,
            ngo_id=?,
            accepted_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, ('Accepted', session["user_id"], donation_id))

    conn.commit()

    create_notification(
        donation["user_id"],
        f"Your donation '{donation['title']}' has been accepted by NGO!"
    )

    conn.close()
    flash("Donation accepted!")
    return redirect(url_for("ngo_dashboard"))

@app.route('/ngo_accepted_donations')
def ngo_accepted_donations():

    if session.get('role') != 'ngo':
        return redirect(url_for('login'))

    conn = get_db()

    donations = conn.execute("""
        SELECT * FROM donations
        WHERE ngo_id=? AND status IN('Accepted','Collected','Completed')
                             ORDER BY accepted_at Desc
    """,(session["user_id"],)).fetchall()

    conn.close()

    return render_template('ngo_accepted_donations.html', donations=donations)


UPLOAD_FOLDER = "static/proofs"


@app.route("/save_location", methods=["POST"])
def save_location():

    if "user_id" not in session:
        return jsonify({"status": "not_logged_in"})

    data = request.get_json()

    lat = data.get("lat")
    lng = data.get("lng")

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute(
        "UPDATE users SET lat=?, lng=? WHERE id=?",
        (lat, lng, session["user_id"])
    )

    conn.commit()
    conn.close()

    return jsonify({"status": "success"})

@app.route("/upload_proof/<int:donation_id>", methods=["POST"])
def upload_proof(donation_id):

    file = request.files["proof"]

    if file:
        filename = file.filename

        filepath = os.path.join("static/proofs", filename)
        file.save(filepath)

        conn = sqlite3.connect("database.db")
        cur = conn.cursor()

        cur.execute(
        "UPDATE donations SET proof=? WHERE id=?",
        (filename, donation_id)
        )

        conn.commit()
        flash("Proof uploaded successfully!")
        conn.close()

    return redirect(url_for("ngo_accepted_donations"))


@app.route("/donor_my_donations")
def donor_my_donations():

    donor_id = session.get("user_id")

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM donations
        WHERE user_id = ?
        ORDER BY id DESC
    """, (donor_id,))

    donations = cur.fetchall()
    conn.close()

    return render_template("donor_my_donations.html", donations=donations)

@app.route("/donation/<int:id>")
def donation_detail(id):

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    donation = conn.execute("""
        SELECT *
        FROM donations
        WHERE id=?
    """, (id,)).fetchone()

    conn.close()

    return render_template("donation_detail.html", donation=donation)

@app.route("/notifications")
def notifications():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    notifications = conn.execute("""
        SELECT * FROM notifications
        WHERE user_id=?
        ORDER BY created_at DESC
    """, (session["user_id"],)).fetchall()

    # mark all as read
    conn.execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (session["user_id"],))
    conn.commit()
    conn.close()

    return render_template("notifications.html", notifications=notifications)


@app.route('/mark_notification_read/<int:notification_id>', methods=['POST'])
def mark_notification_read(notification_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401

    conn = get_db()
    cursor = conn.cursor()

    # Update is_read = 1 for that notification, only for the logged in user
    cursor.execute("""
        UPDATE notifications
        SET is_read = 1
        WHERE id = ? AND user_id = ?
    """, (notification_id, session['user_id']))

    conn.commit()
    conn.close()

    return jsonify({'success': True})

def get_notifications_for_user():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM notifications
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 20
    """, (session['user_id'],))
    notifications = cur.fetchall()
    conn.close()
    return notifications


@app.route("/complete_donation/<int:donation_id>", methods=["POST"])
def complete_donation(donation_id):
    if "user_id" not in session or session.get("role") != "ngo":
        return redirect(url_for("login"))

    conn = get_db()
    donation = conn.execute("SELECT * FROM donations WHERE id=?", (donation_id,)).fetchone()
    if donation:
        conn.execute("UPDATE donations SET status='Completed', completed_at=CURRENT_TIMESTAMP WHERE id=?", (donation_id,))
        conn.commit()

        # Notify donor + NGO
        create_notification(donation["user_id"], f"Your donation '{donation['title']}' has been marked completed!")
        create_notification(session["user_id"], f"Donation '{donation['title']}' marked completed!")

    conn.close()
    flash("Donation completed!")
    return redirect(url_for("ngo_dashboard"))

@app.route("/volunteer_go/<int:donation_id>", methods=["POST"])
def volunteer_go(donation_id):

    if "user_id" not in session or session.get("role") != "volunteer":
        return redirect(url_for("login"))

    volunteer_id = session["user_id"]

    conn = get_db()

    donation = conn.execute(
        "SELECT * FROM emergency_requests WHERE id=?",
        (donation_id,)
    ).fetchone()

    if donation:
        conn.execute("""
            UPDATE emergency_requests
            SET volunteer_id=?, status='Volunteer Accepted'
            WHERE id=?
        """, (volunteer_id, donation_id))

        conn.commit()

    conn.close()

    flash("Task accepted successfully!")
    return redirect(url_for("my_tasks"))



# Allowed proof file types
PROOF_ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "mp4", "mov"}

def allowed_proof(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in PROOF_ALLOWED_EXTENSIONS

@app.route("/update_donation_status/<int:donation_id>", methods=["GET", "POST"])
def update_donation_status(donation_id):
    if "user_id" not in session or session.get("role") != "ngo":
        return redirect(url_for("login"))

    status = request.args.get("status")  # Pending / Accepted / Collected / Completed

    proof_file = None
    if request.method == "POST":
        file = request.files.get("proof_file")
        if file and allowed_proof(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["DONATION_UPLOAD_FOLDER"], filename))
            proof_file = filename

    conn = get_db()

    # Update donations table if status changes
    if status in ["Accepted", "Collected", "Completed"]:
        timestamp_field = None
        if status == "Accepted":
            timestamp_field = "accepted_at"
        elif status == "Completed":
            timestamp_field = "completed_at"

        if timestamp_field:
            conn.execute(f"""
                UPDATE donations SET status=?, {timestamp_field}=CURRENT_TIMESTAMP
                WHERE id=?
            """, (status, donation_id))
        else:
            conn.execute("UPDATE donations SET status=? WHERE id=?", (status, donation_id))
        conn.commit()

    # Insert into donation_status_log for tracking
    conn.execute("""
        INSERT INTO donation_status_log (donation_id, updated_by, status, proof_file)
        VALUES (?, ?, ?, ?)
    """, (donation_id, session["user_id"], status, proof_file))
    conn.commit()

    # Notify donor
    donor_id = conn.execute("SELECT user_id FROM donations WHERE id=?", (donation_id,)).fetchone()["user_id"]
    create_notification(donor_id, f"Donation ID {donation_id} status updated to {status} by NGO.")

    flash(f"Donation status updated to {status}!", "success")
    conn.close()
    return redirect(url_for("ngo_dashboard"))

@app.route("/emergency_food", methods=["GET", "POST"])
def emergency_food():

    if request.method == "POST":

        name = request.form.get("name")
        phone = request.form.get("phone")
        location_text = request.form.get("location")
        members = request.form.get("members")

        # Convert location
        lat, lng = get_lat_lng(location_text)

        if lat is None:
            flash("Location not found. Please enter valid area.")
            return redirect("/emergency_food")

        conn = sqlite3.connect("database.db")
        cur = conn.cursor()

        cur.execute("""
        INSERT INTO emergency_requests
        (name, phone, location, members, lat, lng, status)
        VALUES (?, ?, ?, ?, ?, ?, 'Pending')
        """, (name, phone, location_text, members, lat, lng))

        conn.commit()
        flash("Emergency request submitted successfully!")
        conn.close()

        
        return redirect("/")

    return render_template("emergency_food.html")

@app.route("/ngo_emergency_list")
def ngo_emergency_list():

    if session.get("role") != "ngo":
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute("""
    SELECT * FROM emergency_requests
    WHERE status='Pending'
    ORDER BY created_at DESC
    """)

    data = cur.fetchall()
    conn.close()

    return render_template("ngo_emergency_list.html", data=data)

@app.route("/accept_emergency/<int:id>")
def accept_emergency(id):

    if session.get("role") != "ngo":
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute("""
    UPDATE emergency_requests
    SET status='Accepted',
        ngo_id=?
    WHERE id=? AND status='Pending'
    """, (session["user_id"], id))

    conn.commit()
    conn.close()

    flash("Emergency request accepted!")
    return redirect("/ngo_emergency_list")

@app.route("/volunteer_accept/<int:id>")
def volunteer_accept(id):

    if "volunteer_id" not in session:
        return redirect(url_for("volunteer_login"))

    volunteer_id = session["volunteer_id"]

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute("""
        UPDATE emergency_requests
        SET status=' Accepted', volunteer_id=?
        WHERE id=? AND status='Waiting Volunteer'
    """, (volunteer_id, id))

    conn.commit()
    conn.close()

    flash("Task Accepted Successfully 💚")
    return redirect(url_for("my_tasks"))

@app.route("/my_tasks")
def my_tasks():

    if "user_id" not in session or session.get("role") != "volunteer":
        return redirect(url_for("login"))   # go to main login

    volunteer_id = session["user_id"]

    conn = get_db()
    data = conn.execute("""
        SELECT * FROM emergency_requests
        WHERE volunteer_id=? AND status='Volunteer Accepted'
        ORDER BY created_at DESC
    """, (volunteer_id,)).fetchall()

    conn.close()

    return render_template("my_tasks.html", data=data)

@app.route("/mark_delivered/<int:id>")
def mark_delivered(id):

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute("""
        UPDATE emergency_requests
        SET status='Delivered'
        WHERE id=?
    """, (id,))

    conn.commit()
    conn.close()

    flash("Marked as Delivered ✅")
    return redirect(url_for("my_tasks"))

@app.route("/confirm_delivery/<int:id>")
def confirm_delivery(id):

    if session.get("role") != "ngo":
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute("""
    UPDATE emergency_requests
    SET status='Completed'
    WHERE id=? AND ngo_id=?
    """, (id, session["user_id"]))

    conn.commit()
    conn.close()

    flash("Delivery confirmed successfully!")
    return redirect("/ngo_emergency_list")


@app.route("/send_to_volunteers/<int:id>")
def send_to_volunteers(id):

    if session.get("role") != "ngo":
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute("""
    UPDATE emergency_requests
    SET status='Waiting Volunteer'
    WHERE id=? AND ngo_id=?
    """, (id, session["user_id"]))

    conn.commit()
    conn.close()

    flash("Request sent to volunteers!")
    return redirect("/ngo_emergency_list")

@app.route("/volunteer_emergency_list")
def volunteer_emergency_list():

    if session.get("role") != "volunteer":
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
    SELECT * FROM emergency_requests
    WHERE status='Waiting Volunteer'
    """)

    data = cur.fetchall()
    conn.close()

    return render_template(
        "volunteer_emergency_list.html",
        data=data
    )

@app.route("/nearby_requests")
def nearby_requests():

    if session.get("role") != "ngo":
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 🔹 Get NGO location
    cur.execute("SELECT lat, lng FROM users WHERE id=?",
                (session["user_id"],))
    ngo = cur.fetchone()

    if not ngo or not ngo["lat"] or not ngo["lng"]:
        flash("Your NGO location is not set.")
        return redirect("/ngo_dashboard")

    ngo_lat = float(ngo["lat"])
    ngo_lng = float(ngo["lng"])

    # 🔹 Get all pending emergency requests
    cur.execute("SELECT * FROM emergency_requests WHERE status='Pending'")
    requests = cur.fetchall()

    nearby_list = []

    for req in requests:

        if req["lat"] and req["lng"]:

            distance = haversine(
                ngo_lat,
                ngo_lng,
                float(req["lat"]),
                float(req["lng"])
            )

            if distance <= 5:
                req_dict = dict(req)
                req_dict["distance"] = round(distance, 2)
                nearby_list.append(req_dict)

    conn.close()

    return render_template("nearby_requests.html", data=nearby_list)

@app.route("/accepted_requests")
def accepted_requests():

    if session.get("role") != "ngo":
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
    SELECT * FROM emergency_requests
    WHERE ngo_id=? AND status='Accepted'
    """, (session["user_id"],))

    data = cur.fetchall()
    conn.close()

    return render_template("accepted_requests.html", data=data)

@app.route("/complete_emergency/<int:id>")
def complete_emergency(id):

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute("""
    UPDATE emergency_requests
    SET status='Completed'
    WHERE id=?
    """,(id,))

    conn.commit()
    conn.close()

    return redirect("/accepted_requests")

@app.route("/forgot_password", methods=["GET","POST"])
def forgot_password():

    if request.method == "POST":
        email = request.form["email"]

        conn = sqlite3.connect("database.db")
        cur = conn.cursor()

        cur.execute("SELECT * FROM users WHERE email=?", (email,))
        user = cur.fetchone()

        if user:
            session["reset_email"] = email
            return redirect("/reset_password")
        else:
            return "Email not found"

    return render_template("forgot_password.html")

@app.route("/reset_password", methods=["GET","POST"])
def reset_password():

    if request.method == "POST":
        new_password = request.form["password"]
        email = session.get("reset_email")

        conn = sqlite3.connect("database.db")
        cur = conn.cursor()

        cur.execute("UPDATE users SET password=? WHERE email=?",
                    (new_password, email))

        conn.commit()
        conn.close()

        return redirect("/login")

    return render_template("reset_password.html")

# ===== Run App =====
if __name__ == "__main__":
    init_db()
    app.run(debug=True)