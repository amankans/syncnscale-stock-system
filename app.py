from flask import Flask, render_template, request, redirect, jsonify, send_file
import sqlite3
from io import BytesIO
from openpyxl import Workbook
from datetime import datetime

app = Flask(__name__)

def get_db():
    return sqlite3.connect("database.db")

# ---------------- HOME ----------------
@app.route("/")
def index():
    return render_template("index.html")

# ---------------- ADD PURCHASE ----------------
@app.route("/add_purchase", methods=["GET", "POST"])
def add_purchase():
    if request.method == "POST":
        data = [
            request.form["imei"],
            request.form["product"],
            request.form["company"],
            request.form["model"],
            request.form["specification"],
            request.form["purchase_date"],
            request.form["received_from"],
            "In Stock",
            "",
            ""
        ]
        conn = get_db()
        conn.execute("""
            INSERT INTO stock 
            (imei, product, company, model, specification, purchase_date, received_from, status, sold_to, sold_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, data)
        conn.commit()
        conn.close()
        return redirect("/view_stock")
    return render_template("purchase_form.html")

# ---------------- ADD SALE ----------------
@app.route("/add_sale", methods=["GET", "POST"])
def add_sale():
    if request.method == "POST":
        imei = request.form["imei"]
        sold_to = request.form["sold_to"]
        sold_date = request.form["sold_date"]
        conn = get_db()
        conn.execute("""
            UPDATE stock
            SET status='Sold', sold_to=?, sold_date=?
            WHERE imei=?
        """, (sold_to, sold_date, imei))
        conn.commit()
        conn.close()
        return redirect("/view_stock")
    return render_template("sales_form.html")

# ---------------- VIEW STOCK ----------------
@app.route("/view_stock")
def view_stock():
    conn = get_db()
    rows = conn.execute("SELECT * FROM stock").fetchall()
    conn.close()
    return render_template("view_stock.html", data=rows)


# ---------------- EXPORT STOCK TO EXCEL ----------------
@app.route("/export_stock")
def export_stock():
    conn = get_db()
    rows = conn.execute("SELECT * FROM stock").fetchall()
    conn.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "Stock Inventory"

    # Add header
    ws.append([
        "IMEI", "Product", "Company", "Model", "Specification",
        "Purchase Date", "Purchase From", "Purchase Amount",
        "Status", "Sold To", "Sold Date"
    ])

    for row in rows:
        ws.append(list(row))

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f"stock_inventory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    return send_file(
        output,
        download_name=filename,
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# ---------------- AUDIT PAGE ----------------
@app.route("/audit")
def audit():
    conn = get_db()
    rows = conn.execute("SELECT * FROM stock").fetchall()
    conn.close()
    return render_template("audit.html", data=rows)

# ---------------- LOG AUDIT ENTRY ----------------
@app.route("/log_audit", methods=["POST"])
def log_audit():
    data = request.get_json()
    imei = data.get("imei")
    status = data.get("status")   # "Audited" or "Sold-Found"
    model = data.get("model", "")
    audit_date = data.get("audit_date")

    conn = get_db()
    conn.execute("""
        INSERT INTO audit_log (imei, model, status, audit_date)
        VALUES (?, ?, ?, ?)
    """, (imei, model, status, audit_date))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

# ---------------- EXPORT FULL AUDIT ----------------
@app.route("/export_audit")
def export_audit():
    conn = get_db()

    # Full stock
    stock_rows = conn.execute("SELECT * FROM stock").fetchall()
    # Audited entries
    audit_rows = conn.execute("SELECT * FROM audit_log").fetchall()
    conn.close()

    # Prepare dictionaries
    audit_dict = {}
    for row in audit_rows:
        key = f"{row[1]}_{row[2]}_{row[3]}" if len(row) > 3 else row[1]  # optional, just to be safe
        audit_dict.setdefault(row[1], []).append({
            "status": row[3],
            "audit_date": row[4]
        })

    # Excel workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Full Audit Report"

    ws.append([
        "IMEI", "Product", "Company", "Model", "Specification",
        "Purchase Date", "Received From", "Status", "Sold To", "Sold Date",
        "Audit Status", "Audit Timestamp"
    ])

    # Track expected in-stock items
    expected_stock = [r for r in stock_rows if r[8] == "In Stock"]

    scanned_imeis = [r[1] for r in audit_rows]

    for s in stock_rows:
        # Default values
        audit_status = ""
        audit_timestamp = ""

        # Check if this IMEI was scanned
        found_entries = [r for r in audit_rows if r[1] == s[0]]  # IMEI matches
        if found_entries:
            entry = found_entries[-1]  # last scan if multiple
            audit_status = entry[3]    # "Audited" or "Sold-Found"
            audit_timestamp = entry[4]
        else:
            # If expected in stock but not scanned
            if s[8] == "In Stock":
                audit_status = "Missing – Not Scanned"
                audit_timestamp = ""

        ws.append([
            s[0], s[1], s[2], s[3], s[4],
            s[5], s[6], s[8], s[9], s[10],
            audit_status, audit_timestamp
        ])

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f"audit_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    return send_file(
        output,
        download_name=filename,
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )



# ---------------- INVENTORY API ----------------
@app.route("/api/inventory")
def api_inventory():
    conn = get_db()
    rows = conn.execute("SELECT * FROM stock").fetchall()
    conn.close()
    return jsonify([list(row) for row in rows])


if __name__ == "__main__":
    app.run(debug=True)
