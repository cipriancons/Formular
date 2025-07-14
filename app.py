from flask import Flask, request, redirect, render_template, send_file, url_for, session, flash
import json
import pyodbc
from fpdf import FPDF
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'cheie-secreta'  

# Configurare admin
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

# Fișiere
FORM_TEMPLATES_FILE = "form_templates.json"
STATISTICS_FILE = "statistics.json"

def load_form_templates():
    """Load form templates from JSON file"""
    if os.path.exists(FORM_TEMPLATES_FILE):
        with open(FORM_TEMPLATES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return {
            "Formular RCA": "formular_rca.json",
            "Formular Inregistrare": "formular_inregistrare.json",
            "Formular Cerere": "formular_cerere.json",
            "Formular Contact": "formular_contact.json"
        }

def save_form_templates(templates):
    """Save form templates to JSON file"""
    with open(FORM_TEMPLATES_FILE, "w", encoding="utf-8") as f:
        json.dump(templates, f, ensure_ascii=False, indent=4)

def load_statistics():
    """Load statistics from JSON file"""
    if os.path.exists(STATISTICS_FILE):
        with open(STATISTICS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return {}

def save_statistics(stats):
    """Save statistics to JSON file"""
    with open(STATISTICS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=4)

def update_user_statistics(username):
    """Update user statistics"""
    stats = load_statistics()
    if username in stats:
        stats[username]["count"] += 1
    else:
        stats[username] = {
            "count": 1,
            "first_form_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    stats[username]["last_form_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_statistics(stats)

FORM_TEMPLATES = load_form_templates()

def load_form(form_name):
    json_file = FORM_TEMPLATES.get(form_name)
    if not json_file or not os.path.exists(json_file):
        return None
    
    with open(json_file, "r", encoding="utf-8") as f:
        return json.load(f)

def save_to_db(data):
    pass

def export_to_pdf(data, form_title="Formular completat", filename="formular_completat.pdf"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)

    pdf.cell(0, 10, form_title, ln=True, align='C')
    pdf.set_draw_color(0, 0, 0)
    pdf.line(10, 20, 200, 20)

    pdf.ln(15) 
    pdf.set_font("Arial", '', 12)

    for key, value in data.items():
        label = key.replace("_", " ").capitalize()
        if isinstance(value, str) and value.lower() in ['on', 'da', 'yes', 'true']:
            value = 'Da'
        elif isinstance(value, str) and value.lower() in ['off', 'nu', 'no', 'false']:
            value = 'Nu'
        pdf.cell(0, 10, f"{label}: {value}", ln=True)

    pdf.output(filename)

@app.route("/", methods=["GET"])
def main_page():
    if 'username' in session:
        return render_template("main_page_with_auth.html", 
                             form_names=FORM_TEMPLATES.keys(),
                             session=session)
    else:
        return render_template("main_page_with_auth.html", 
                             form_names=FORM_TEMPLATES.keys())
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user_type = request.form.get("user_type")
        username = request.form.get("username")
        
        if user_type == "admin":
            password = request.form.get("password")
            if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
                session['user_type'] = 'admin'
                session['username'] = username
                return redirect("/admin-dashboard")
            else:
                flash("Username sau parolă greșite pentru admin!", "error")
                return render_template("login.html", user_type=user_type)
        else:  # user normal
            if username and username.strip():
                session['user_type'] = 'user'
                session['username'] = username.strip()
                return redirect("/")
            else:
                flash("Username-ul nu poate fi gol!", "error")
                return render_template("login.html", user_type=user_type)
    
    user_type = request.args.get("type", "user")
    return render_template("login.html", user_type=user_type)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/admin-dashboard")
def admin_dashboard():
    if session.get('user_type') != 'admin':
        return redirect("/login?type=admin")
    
    stats = load_statistics()
    return render_template("admin_dashboard.html", 
                         form_names=FORM_TEMPLATES.keys(),
                         statistics=stats)

@app.route("/select-action", methods=["POST"])
def select_action():
    if 'username' not in session:
        return redirect("/login?type=user")
    
    form_name = request.form.get("form_name")
    
    # Doar adminul poate vedea opțiunea de modificare
    if session.get('user_type') == 'admin':
        return render_template("action_selection.html", form_name=form_name, is_admin=True)
    else:
        return render_template("action_selection.html", form_name=form_name, is_admin=False)

@app.route("/modify-form", methods=["GET", "POST"])
def modify_form():
    # Doar adminul poate modifica formulare
    if session.get('user_type') != 'admin':
        flash("Nu aveți permisiuni pentru a modifica formulare!", "error")
        return redirect("/")
    
    if request.method == "POST":
        form_name = request.form.get("form_name")
    else:  # GET
        form_name = request.args.get("form_name")
    
    fields = load_form(form_name)
    
    if not fields:
        return "Formularul nu a fost găsit.", 404
    
    return render_template("modify_form.html", 
                         fields=fields, 
                         form_title=f"Modificare {form_name}",
                         form_name=form_name)

@app.route("/save-modified-form", methods=["POST"])
def save_modified_form():
    # Doar adminul poate salva modificări
    if session.get('user_type') != 'admin':
        flash("Nu aveți permisiuni pentru a modifica formulare!", "error")
        return redirect("/")
    
    form_name = request.form.get("form_name")
    new_form_name = request.form.get("new_form_name")
    new_fields = []

    field_names = request.form.getlist("field_name[]")
    field_labels = request.form.getlist("field_label[]")
    field_types = request.form.getlist("field_type[]")
    field_requireds = request.form.getlist("field_required[]")
    
    for name, label, type_, required in zip(field_names, field_labels, field_types, field_requireds):
        new_fields.append({
            "name": name,
            "label": label,
            "type": type_,
            "required": required == "true"
        })
    
    if new_form_name:
        modified_name = new_form_name.strip()
    else:
        modified_name = f"{form_name}_modified"

    safe_filename = modified_name.lower().replace(' ', '_').replace('/', '_').replace('\\', '_')
    modified_filename = f"{safe_filename}.json"
    
    with open(modified_filename, "w", encoding="utf-8") as f:
        json.dump(new_fields, f, ensure_ascii=False, indent=4)
    
    FORM_TEMPLATES[modified_name] = modified_filename
    
    save_form_templates(FORM_TEMPLATES)
    
    flash(f"Formularul '{modified_name}' a fost salvat cu succes!", "success")
    return redirect("/admin-dashboard")

@app.route("/start-form", methods=["POST", "GET"])
def start_form():
    if 'username' not in session:
        return redirect("/login?type=user")
    
    if request.method == "GET":
        form_name = request.args.get("form_name")
        action = request.args.get("action")
    else:
        form_name = request.form.get("form_name")
        action = request.form.get("action")
    
    if action == "start":
        fields = load_form(form_name)
        if not fields:
            return "Formularul nu a fost găsit.", 404
        
        return render_template("form_template.html", 
                             fields=fields, 
                             form_title=form_name,
                             form_name=form_name)
    elif action == "modify":
        if session.get('user_type') != 'admin':
            flash("Nu aveți permisiuni pentru a modifica formulare!", "error")
            return redirect("/")
        return redirect(url_for("modify_form", form_name=form_name))
    else:
        return "Acțiune invalidă.", 400

@app.route("/submit-form", methods=["POST"])
def submit_form():
    if 'username' not in session:
        return redirect("/login?type=user")
    
    form_name = request.form.get("form_name")
    fields = load_form(form_name)
    
    if not fields:
        return "Formularul nu a fost găsit.", 404
    
    data = {}
    for field in fields:
        if field["type"] == "checkbox":
            data[field["name"]] = "Da" if request.form.get(field["name"]) else "Nu"
        else:
            data[field["name"]] = request.form.get(field["name"])

    save_to_db(data)
    
    # Actualizează statisticile pentru user
    update_user_statistics(session['username'])
    
    export_to_pdf(data, form_title=form_name)
    
    return render_template("success.html")

@app.route("/download")
def download_pdf():
    if 'username' not in session:
        return redirect("/login?type=user")
    
    pdf_path = os.path.join(os.getcwd(), "formular_completat.pdf")
    if os.path.exists(pdf_path):
        return send_file(pdf_path, as_attachment=True)
    else:
        return "Fișierul nu există.", 404

@app.route("/download-success")
def download_success():
    if 'username' not in session:
        return redirect("/login?type=user")
    return render_template("download_success.html")

@app.route("/statistics")
def view_statistics():
    if session.get('user_type') != 'admin':
        flash("Nu aveți permisiuni pentru a vedea statisticile!", "error")
        return redirect("/")
    
    stats = load_statistics()
    return render_template("statistics.html", statistics=stats)

def create_sample_forms():
    sample_forms = {
        "formular_rca.json": [
            {"name": "nume", "label": "Nume deținător", "type": "text", "required": True},
            {"name": "nr_inmatriculare", "label": "Număr de înmatriculare", "type": "text", "required": True},
            {"name": "marca", "label": "Marcă vehicul", "type": "text", "required": True},
            {"name": "data_start", "label": "Data începere asigurare", "type": "date", "required": True}
        ],
        "formular_inregistrare.json": [
            {"name": "nume_complet", "label": "Nume complet", "type": "text", "required": True},
            {"name": "cnp", "label": "CNP", "type": "text", "required": True},
            {"name": "adresa", "label": "Adresă", "type": "textarea", "required": True},
            {"name": "telefon", "label": "Telefon", "type": "tel", "required": False}
        ],
        "formular_cerere.json": [
            {"name": "tip_cerere", "label": "Tip cerere", "type": "text", "required": True},
            {"name": "descriere", "label": "Descriere cerere", "type": "textarea", "required": True},
            {"name": "data_cerere", "label": "Data cererii", "type": "date", "required": True}
        ],
        "formular_contact.json": [
            {"name": "email", "label": "Adresă email", "type": "email", "required": True},
            {"name": "mesaj", "label": "Mesaj", "type": "textarea", "required": True},
            {"name": "acord_gdpr", "label": "Sunt de acord cu prelucrarea datelor", "type": "checkbox", "required": True}
        ]
    }
    
    for filename, fields in sample_forms.items():
        if not os.path.exists(filename):
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(fields, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    if not os.path.exists("templates"):
        os.makedirs("templates")
    
    create_sample_forms()
    
    if not os.path.exists(FORM_TEMPLATES_FILE):
        save_form_templates(FORM_TEMPLATES)
    
    if not os.path.exists(STATISTICS_FILE):
        save_statistics({})
    
    app.run(debug=True)