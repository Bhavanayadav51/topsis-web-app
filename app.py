from flask import Flask, render_template, request
import pandas as pd
import smtplib
from email.message import EmailMessage
import os
import numpy as np
import threading



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

    df = pd.read_csv(file)

    weights_list = list(map(float, weights.split(",")))
    impacts_list = impacts.split(",")

    # Save first column (Name column)
    names = df.iloc[:, 0]

    # Numeric data
    data = df.iloc[:, 1:].astype(float)

    num_criteria = data.shape[1]

    # ---------- GENERIC VALIDATION ----------
    if len(weights_list) != num_criteria:
        return f"Please enter {num_criteria} weights"

    if len(impacts_list) != num_criteria:
        return f"Please enter {num_criteria} impacts"

    for i in impacts_list:
        if i not in ["+", "-"]:
            return "Impacts must be + or -"

    # ---------- TOPSIS START ----------

    # Normalize
    norm = data / np.sqrt((data**2).sum())

    # Apply Weights (Generic Safe)
    weighted = norm * np.array(weights_list)

    # Ideal Best & Worst
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

    # Distance
    dist_best = np.sqrt(((weighted - ideal_best) ** 2).sum(axis=1))
    dist_worst = np.sqrt(((weighted - ideal_worst) ** 2).sum(axis=1))

    # Score
    score = dist_worst / (dist_best + dist_worst)

    # Add results
    df["Topsis Score"] = score.round(6)
    df["Rank"] = df["Topsis Score"].rank(ascending=False).astype(int)

    df = df.sort_values("Rank")

    # TEMP: Just save file (Replace later with TOPSIS logic)
    df.to_csv("result.csv", index=False)

    threading.Thread(target=send_email, args=(email,), daemon=True).start()


    result_html = df.to_html(classes="table table-sm table-bordered table-striped", index=False)


    return render_template("result.html", table=result_html)
 

# EMAIL FUNCTION
def send_email(receiver):
    try:
        print("EMAIL FUNCTION STARTED")

        msg = EmailMessage()
        msg["Subject"] = "TOPSIS Result"
        msg["From"] = "bhavanayadav5100@gmail.com"
        msg["To"] = receiver

        msg.set_content("Please find attached TOPSIS result")

        with open("result.csv", "rb") as f:
            msg.add_attachment(
                f.read(),
                maintype="application",
                subtype="octet-stream",
                filename="result.csv"
            )

        print("CONNECTING SMTP")

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            print("LOGIN ATTEMPT")
            smtp.login(
                "bhavanayadav5100@gmail.com",
                os.environ.get("EMAIL_PASSWORD")
            )
            print("LOGIN SUCCESS")

            smtp.send_message(msg)
            print("EMAIL SENT SUCCESSFULLY")

    except Exception as e:
        print("EMAIL ERROR:", e)

# RUN APP
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
