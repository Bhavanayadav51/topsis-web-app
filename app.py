from flask import Flask, render_template, request
import pandas as pd
import smtplib
from email.message import EmailMessage
import os
import numpy as np
from dotenv import load_dotenv
import tempfile

load_dotenv()

app = Flask(__name__)


# HOME PAGE
@app.route("/")
def home():
    return render_template("index.html")


# PROCESS FORM DATA
@app.route("/process", methods=["POST"])
def process():

    file = request.files.get("file")
    weights = request.form.get("weights", "").strip()
    impacts = request.form.get("impacts", "").strip()
    email = request.form.get("email", "").strip()

    # --- INPUT VALIDATION ---
    if file is None or file.filename == "":
        return render_template("result.html", table="<p style='color:red;'>No file uploaded.</p>")

    if not file.filename.endswith(".csv"):
        return render_template("result.html", table="<p style='color:red;'>Please upload a valid CSV file.</p>")

    if not weights:
        return render_template("result.html", table="<p style='color:red;'>Weights field is empty.</p>")

    if not impacts:
        return render_template("result.html", table="<p style='color:red;'>Impacts field is empty.</p>")

    if not email:
        return render_template("result.html", table="<p style='color:red;'>Email field is empty.</p>")

    # --- SAVE TO TEMP FILE ---
    temp_dir = tempfile.gettempdir()
    input_path = os.path.join(temp_dir, file.filename)

    try:
        file.save(input_path)
        df = pd.read_csv(input_path)
    except Exception as e:
        return render_template("result.html", table=f"<p style='color:red;'>Error reading CSV: {str(e)}</p>")
    finally:
        # Clean up temp file after reading
        if os.path.exists(input_path):
            os.remove(input_path)

    # --- PARSE WEIGHTS AND IMPACTS ---
    try:
        weights_list = list(map(float, weights.split(",")))
    except ValueError:
        return render_template("result.html", table="<p style='color:red;'>Weights must be numeric values separated by commas.</p>")

    impacts_list = [i.strip() for i in impacts.split(",")]

    # Need at least 2 columns (1 name + 1 criteria)
    if df.shape[1] < 2:
        return render_template("result.html", table="<p style='color:red;'>CSV must have at least one name column and one criteria column.</p>")

    try:
        data = df.iloc[:, 1:].astype(float)
    except ValueError:
        return render_template("result.html", table="<p style='color:red;'>All criteria columns must contain numeric values.</p>")

    num_criteria = data.shape[1]

    # --- VALIDATION ---
    if len(weights_list) != num_criteria:
        return render_template("result.html", table=f"<p style='color:red;'>Please enter exactly {num_criteria} weights (you entered {len(weights_list)}).</p>")

    if len(impacts_list) != num_criteria:
        return render_template("result.html", table=f"<p style='color:red;'>Please enter exactly {num_criteria} impacts (you entered {len(impacts_list)}).</p>")

    for i in impacts_list:
        if i not in ["+", "-"]:
            return render_template("result.html", table="<p style='color:red;'>Impacts must be + or - only (comma separated).</p>")

    # --- TOPSIS CALCULATION ---
    norm = data / np.sqrt((data**2).sum())
    weighted = norm * np.array(weights_list)

    ideal_best = []
    ideal_worst = []

    for i in range(num_criteria):
        if impacts_list[i] == "+":
            ideal_best.append(weighted.iloc[:, i].max())
            ideal_worst.append(weighted.iloc[:, i].min())
        else:
            ideal_best.append(weighted.iloc[:, i].min())
            ideal_worst.append(weighted.iloc[:, i].max())

    ideal_best = np.array(ideal_best)
    ideal_worst = np.array(ideal_worst)

    dist_best = np.sqrt(((weighted - ideal_best) ** 2).sum(axis=1))
    dist_worst = np.sqrt(((weighted - ideal_worst) ** 2).sum(axis=1))

    score = dist_worst / (dist_best + dist_worst)

    df["Topsis Score"] = score.round(6)
    df["Rank"] = df["Topsis Score"].rank(ascending=False).astype(int)
    df = df.sort_values("Rank")

    # --- SEND EMAIL ---
    result_csv = df.to_csv(index=False)

    try:
        send_email(email, result_csv)
        email_status = "<p style='color:green;'>✅ Result has been sent to your email.</p>"
    except Exception as e:
        print("Email Error:", e)
        email_status = "<p style='color:orange;'>⚠️ Email could not be sent, but your result is below.</p>"

    # --- RENDER RESULT ---
    result_html = df.to_html(
        classes="table table-sm table-bordered table-striped",
        index=False
    )

    return render_template("result.html", table=email_status + result_html)


# EMAIL FUNCTION
def send_email(receiver_email, content_csv):

    sender_email = os.environ.get("EMAIL_USER")
    sender_password = os.environ.get("EMAIL_PASS")

    if not sender_email or not sender_password:
        raise Exception("Email credentials not set in environment variables")

    msg = EmailMessage()
    msg["Subject"] = "TOPSIS Result"
    msg["From"] = sender_email
    msg["To"] = receiver_email

    msg.set_content("Please find the TOPSIS result attached.")

    msg.add_attachment(
        content_csv.encode(),
        maintype="text",
        subtype="csv",
        filename="result.csv"
    )

    # Try port 587 with STARTTLS (more reliable on most hosting)
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender_email, sender_password)
            server.send_message(msg)
    except Exception:
        # Fallback to port 465 with SSL
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)


# RUN APP
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)