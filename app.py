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

    file = request.files["file"]
    weights = request.form["weights"]
    impacts = request.form["impacts"]
    email = request.form["email"]

    # ✅ TEMP FILE SAFE (LOCAL + RENDER)
    temp_dir = tempfile.gettempdir()
    input_path = os.path.join(temp_dir, file.filename)
    file.save(input_path)

    df = pd.read_csv(input_path)

    weights_list = list(map(float, weights.split(",")))
    impacts_list = impacts.split(",")

    data = df.iloc[:, 1:].astype(float)
    num_criteria = data.shape[1]

    # VALIDATION
    if len(weights_list) != num_criteria:
        return f"Please enter {num_criteria} weights"

    if len(impacts_list) != num_criteria:
        return f"Please enter {num_criteria} impacts"

    for i in impacts_list:
        if i not in ["+", "-"]:
            return "Impacts must be + or -"

    # ⭐ TOPSIS CALCULATION

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

    # Save result CSV
    result_csv = df.to_csv(index=False)

    # Send Email
    try:
        send_email(email, result_csv)
    except Exception as e:
        print("Email Error:", e)

    result_html = df.to_html(
        classes="table table-sm table-bordered table-striped",
        index=False
    )

    return render_template("result.html", table=result_html)


# EMAIL FUNCTION
def send_email(receiver_email, content_csv):

    sender_email = os.environ.get("EMAIL_USER")
    sender_password = os.environ.get("EMAIL_PASS")

    if not sender_email or not sender_password:
        raise Exception("Email credentials not set")

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

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, sender_password)
        server.send_message(msg)


# RUN APP
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
