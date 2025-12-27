from flask import Flask, render_template, request, redirect, url_for, session, jsonify,send_file
import sqlite3
from pathlib import Path
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Image
)
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from flask import send_file
import io
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, PageBreak, Image
from reportlab.lib.units import cm
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Font


from translations.en import translations as EN
from translations.hu import translations as HU
from translations.ar import translations as AR


app = Flask(__name__)
app.secret_key = "change_this_secret_key"

BASE_DIR = Path(__file__).parent
DB_FILE = BASE_DIR / "data" / "games.db"








ROLES = [ "editor", "admin"]

def is_editor():
    return session.get("role") in ["editor", "admin"]

def is_admin():
    return session.get("role") == "admin"







# ---------- helpers ----------
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


# ---------- translations helpers ----------

def get_translations():
    lang = session.get("lang", "en")

    if lang == "hu":
        return HU
    elif lang == "ar":
        return AR
    else:
        return EN

# ---------- inject_translations----------
@app.context_processor
def inject_globals():
    lang = session.get("lang", "en")

    direction = "rtl" if lang == "ar" else "ltr"

    return {
        "t": get_translations(),
        "lang": lang,
        "dir": direction
    }


#------------set-language-----------

@app.route("/set-language/<lang>")
def set_language(lang):
    if lang in ["en", "hu", "ar"]:
        session["lang"] = lang
    return redirect(request.referrer or "/")




















# ---------- login ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    message = None

    if request.method == "POST":
        role = request.form.get("role")
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        # -------- ADMIN LOGIN --------

        

        if role == "admin":
                        
            ADMIN_PASSWORD = "ayoub"
            if password == ADMIN_PASSWORD:
 
                session.clear()
                session["logged_in"] = True
                session["role"] = "admin"
                session["username"] = username
                session["just_logged_in"] = True

                return redirect(url_for("index"))
            else:
                message = "Invalid admin username or password"

        # -------- EDITOR LOGIN --------
        elif role == "editor":
            expected_password = username + "ayoub"

            if password == expected_password:
                session.clear()
                session["logged_in"] = True
                session["role"] = "editor"
                session["username"] = username
                session["just_logged_in"] = True
                
                return redirect(url_for("index"))
            else:
                message = "Incorect. Try again !"

        else:
            message = "Please select a role"

    return render_template("login.html", message=message)





#------------/logout------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))
















# ---------- main ----------
@app.route("/")
def index():
    return render_template("index.html", admin=is_admin())









@app.route("/stats/age")
def stats_age():
    conn = get_db()

    # Age distribution
    rows = conn.execute("""
        SELECT age, COUNT(*) as count
        FROM games
        WHERE age IS NOT NULL
        GROUP BY age
        ORDER BY age
    """).fetchall()

    # Summary stats
    total_games = conn.execute(
        "SELECT COUNT(*) FROM games"
    ).fetchone()[0]

    avg_age = conn.execute(
        "SELECT ROUND(AVG(age), 1) FROM games WHERE age IS NOT NULL"
    ).fetchone()[0]

    most_common = conn.execute("""
        SELECT age
        FROM games
        GROUP BY age
        ORDER BY COUNT(*) DESC
        LIMIT 1
    """).fetchone()

    conn.close()

    ages = [f"{r['age']}+" for r in rows]
    counts = [r["count"] for r in rows]

    return render_template(
        "stats_age.html",
        ages=ages,
        counts=counts,
        total_games=total_games,
        avg_age=avg_age,
        most_common=most_common[0] if most_common else "—"
    )




















# ---------- list ----------
@app.route("/list")
def list_all_games():
    conn = get_db()

    # ---- totals ----
    totals = conn.execute("""
        SELECT 
            COUNT(*) AS total_games,
            SUM(copies) AS total_copies
        FROM games
    """).fetchone()

    # ---- ordered games (cabinet → shelf → name) ----
    games = conn.execute("""
        SELECT *
        FROM games
        ORDER BY 
            CAST(cabinet AS INTEGER),
            CAST(shelf AS INTEGER),
            name
    """).fetchall()

    conn.close()

    return render_template(
        "list_all_games.html",
        games=games,
        total_games=totals["total_games"],
        total_copies=totals["total_copies"] or 0,
        now=datetime.now()
    )









#------------export_excel-------------

@app.route("/export_excel")
def export_excel():
    conn = get_db()

    games = conn.execute("""
        SELECT
            name,
            cabinet,
            shelf,
            copies,
            age,
            updated_at,
            editor_name,
            rules
        FROM games
        ORDER BY
            CAST(cabinet AS INTEGER),
            CAST(shelf AS INTEGER),
            name
    """).fetchall()

    conn.close()

    # ---------- CREATE EXCEL ----------
    wb = Workbook()
    ws = wb.active
    ws.title = "Games"

    headers = [
        "Name",
        "Cabinet",
        "Shelf",
        "Copies",
        "Age",
        "Last edited",
        "Editor",
        "Rules"
    ]

    ws.append(headers)

    # Bold header row
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for g in games:
        updated_value = "—"
        if g["updated_at"]:
            updated_value = g["updated_at"][:16].replace("T", " ")

        ws.append([
            g["name"],
            g["cabinet"],
            g["shelf"],
            g["copies"],
            g["age"],
            updated_value,
            g["editor_name"] if g["editor_name"] else "—",
            g["rules"] if g["rules"] else ""
        ])

    # ---------- SAVE TO MEMORY ----------
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="games.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )






















# ---------- helpers ----------
def pdf_header_footer(canvas, doc):
    canvas.saveState()

    width, height = A4

    # ---------- LOGO ----------
    logo_path = Path(app.root_path) / "static" / "logo" / "logo.png"
    if logo_path.exists():
        canvas.drawImage(
            str(logo_path),
            x=2 * cm,
            y=height - 2.5 * cm,
            width=3.5 * cm,
            height=2 * cm,
            preserveAspectRatio=True,
            mask="auto"
        )

    # ---------- HEADER TITLE ----------
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(
        6 * cm,
        height - 2 * cm,
        "GameStore Community Report"
    )

    # ---------- FOOTER ----------
    canvas.setFont("Helvetica", 8)

    # Date / time
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    canvas.drawString(
        2 * cm,
        1.5 * cm,
        f"Generated on: {now}"
    )

    # Page number
    canvas.drawRightString(
        width - 2 * cm,
        1.5 * cm,
        f"Page {doc.page}"
    )

    canvas.restoreState()
#---------datetime----------

@app.template_filter("to_datetime")
def to_datetime(value):
    return datetime.fromisoformat(value)





# ------------- export_all_games_pdf ----------
@app.route("/export_ordered_pdf", methods=["GET", "POST"])
def export_ordered_pdf():
    # ---------- FILTER INPUT ----------
    if request.method == "GET":
        return render_template("export_ordered_pdf.html")

    cabinet_filter = request.form.get("cabinet", "").strip()
    shelf_filter = request.form.get("shelf", "").strip()

    conn = get_db()

    # ✅ include updated_at
    query = """
        SELECT name, cabinet, shelf, copies, age, rules, updated_at, editor_name
        FROM games
        WHERE 1 = 1
    """
    params = []

    if cabinet_filter:
        query += " AND cabinet = ?"
        params.append(cabinet_filter)

    if shelf_filter:
        query += " AND shelf = ?"
        params.append(shelf_filter)

    query += """
        ORDER BY
            CAST(cabinet AS INTEGER),
            CAST(shelf AS INTEGER),
            name
    """

    games = conn.execute(query, params).fetchall()
    conn.close()

    if not games:
        return redirect(url_for("list_all_games"))

    # ---------- PDF SETUP ----------
    buffer = io.BytesIO()
    pdf = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=90,
        bottomMargin=60
    )

    styles = getSampleStyleSheet()

    wrap_style = styles["Normal"]
    wrap_style.fontSize = 8
    wrap_style.wordWrap = "CJK"  # breaks long URLs

    elements = []

    current_cabinet = None
    current_shelf = None
    table_data = []

    # ---------- TABLE FLUSH ----------
    def flush_table():
        if len(table_data) > 1:
            table = Table(
                table_data,
                colWidths=[100, 40, 45, 40, 65, 60, 150],
                repeatRows=1
            )
            table.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
            ]))
            elements.append(table)
            elements.append(Paragraph("<br/>", styles["Normal"]))

    # ---------- BUILD CONTENT ----------
    for g in games:

        # ---- CABINET HEADER ----
        if g["cabinet"] != current_cabinet:
            flush_table()
            elements.append(
                Paragraph(f"Cabinet {g['cabinet']}", styles["Heading2"])
            )
            current_cabinet = g["cabinet"]
            current_shelf = None
            table_data = [["Name", "Shelf", "Copies", "Age", "Updated", "Rules"]]

        # ---- SHELF HEADER ----
        if g["shelf"] != current_shelf:
            flush_table()
            elements.append(
                Paragraph(f"Shelf {g['shelf']}", styles["Heading3"])
            )
            current_shelf = g["shelf"]
            table_data = [["Name", "Shelf", "Copies", "Age", "Updated", "Editor", "Rules"]]

        # ---- UPDATED VALUE ----
        updated_value = "—"
        if g["updated_at"]:
            updated_value = g["updated_at"][:10]  # YYYY-MM-DD

        editor_value = g["editor_name"] if g["editor_name"] else "—"

        table_data.append([
            g["name"],
            g["shelf"],
            g["copies"],
            g["age"],
            updated_value,
            editor_value,
            Paragraph(g["rules"] if g["rules"] else "-", wrap_style)
        ])

    flush_table()

    # ---------- BUILD PDF ----------
    pdf.build(
        elements,
        onFirstPage=pdf_header_footer,
        onLaterPages=pdf_header_footer
    )

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="games.pdf",
        mimetype="application/pdf"
    )



















#-----------autocomplete------
@app.route("/api/autocomplete")
def autocomplete():
    term = request.args.get("q", "").strip().lower()

    if not term:
        return jsonify([])

    conn = get_db()
    results = conn.execute("""
        SELECT DISTINCT name
        FROM games
        WHERE LOWER(name) LIKE ?
        ORDER BY name
        LIMIT 10
    """, (f"%{term}%",)).fetchall()
    conn.close()

    return jsonify([r["name"] for r in results])



# ---------- search ----------
@app.route("/research", methods=["GET", "POST"])
def research():
    results = []
    conn = get_db()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        cabinet = request.form.get("cabinet", "").strip()
        shelf = request.form.get("shelf", "").strip()
        age = request.form.get("age", "").strip()
        editor = request.form.get("editor", "").strip()


        query = """
            SELECT *
            FROM games
            WHERE 1 = 1
        """
        params = []

        if name:
            query += " AND LOWER(name) LIKE ?"
            params.append(f"%{name.lower()}%")

        if cabinet:
            query += " AND cabinet = ?"
            params.append(cabinet)

        if shelf:
            query += " AND shelf = ?"
            params.append(shelf)

        if age:
            query += " AND age <= ?"
            params.append(age)

        if editor:
            query += " AND LOWER(editor_name) LIKE ?"
            params.append(f"%{editor.lower()}%")


        query += """
            ORDER BY
                CAST(cabinet AS INTEGER),
                CAST(shelf AS INTEGER),
                name
        """

        results = conn.execute(query, params).fetchall()

    conn.close()
    return render_template("research.html", results=results)






















 #-------duplicate name warning---------

@app.route("/api/check_game_name")
def check_game_name():
    name = request.args.get("name", "").strip().lower()

    if not name:
        return jsonify({"exists": False})

    conn = get_db()
    game = conn.execute("""
        SELECT 1 FROM games
        WHERE LOWER(name) = ?
        LIMIT 1
    """, (name,)).fetchone()
    conn.close()

    return jsonify({"exists": bool(game)})








# ---------- add ----------
@app.route("/add", methods=["GET", "POST"])
def add_game():
    if not is_admin():
        return redirect(url_for("login"))

    if request.method == "POST":
        # 1️⃣ GET FORM DATA
        name = request.form["name"].strip()
        cabinet = request.form["cabinet"]
        shelf = request.form["shelf"]
        copies = request.form["copies"]
        age = request.form["age"]
        rules = request.form["rules"]

        conn = get_db()

        # 2️⃣ 🔴 PUT THE DUPLICATE CHECK HERE 🔴
        existing = conn.execute("""
            SELECT 1 FROM games
            WHERE LOWER(name) = ?
        """, (name.lower(),)).fetchone()

        if existing:
            conn.close()
            return render_template(
                "add.html",
                message="⚠ A game with this name already exists."
            )

        # 3️⃣ INSERT (ONLY IF NO DUPLICATE)
        now = datetime.now().isoformat()

        conn.execute("""
            INSERT INTO games (name, cabinet, shelf, copies, age, rules, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, cabinet, shelf, copies, age, rules, now))
        conn.commit()
        conn.close()
        return redirect(url_for("list_all_games"))

    return render_template("add.html")










# ---------- edit  ----------
@app.route("/edit", methods=["GET", "POST"])
def edit_game():
    if not is_editor():
        return redirect(url_for("login"))

    conn = get_db()
    matches = None
    game = None
    message = None

    if request.method == "POST":

        # ---------- SEARCH ----------
        if "search" in request.form:
            name = request.form["name"].lower()
            matches = conn.execute(
                "SELECT * FROM games WHERE LOWER(name) LIKE ?",
                (f"%{name}%",)
            ).fetchall()

            if not matches:
                message = "No similar games found."

        # ---------- SELECT ----------
        elif "select" in request.form:
            game = conn.execute(
                "SELECT * FROM games WHERE id=?",
                (request.form["id"],)
            ).fetchone()

        # ---------- SAVE ----------
        elif "save" in request.form:

            now = datetime.now().isoformat()

            editor = session.get("username")

            conn.execute("""
                UPDATE games
                SET cabinet=?,
                    shelf=?,
                    copies=?,
                    age=?,
                    rules=?,
                    updated_at=?,
                    editor_name=?
                WHERE id=?
            """, (
                request.form["cabinet"],
                request.form["shelf"],
                request.form["copies"],
                request.form["age"],
                request.form["rules"],
                now,                     # ✅ Python value
                editor,
                request.form["id"]
            ))

            conn.commit()
            conn.close()
            return redirect(url_for("index"))

    conn.close()
    return render_template(
        "edit.html",
        matches=matches,
        game=game,
        message=message
    )














# ---------- delete ----------
@app.route("/delete", methods=["GET", "POST"])
def delete_game():
    if not is_admin():
        return redirect(url_for("login"))

    game = None
    message = None
    conn = get_db()

    if request.method == "POST":

        if "search" in request.form:
            name = request.form["name"].lower()
            game = conn.execute(
                "SELECT * FROM games WHERE LOWER(name) LIKE ?",
                (f"%{name}%",)
            ).fetchone()
            if not game:
                message = "Game not found."

        elif "confirm" in request.form:
            conn.execute("DELETE FROM games WHERE id=?", (request.form["id"],))
            conn.commit()
            conn.close()
            return redirect(url_for("index"))

    conn.close()
    return render_template("delete.html", game=game, message=message)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
