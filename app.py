from flask import Flask, render_template, request
import pandas as pd
import numpy as np
import os
import tempfile
from dotenv import load_dotenv
import resend

load_dotenv()

app = Flask(__name__)

# ---------------- HOME ----------------
@app.route("/")
def home():
    return render_template("index.html")


# ---------------- PROCESS ----------------
@app.route("/process", methods=["POST"])
def process():
    try:
        file = request.files.get("file")
        weights = request.form.get("weights", "").strip()
        impacts = request.form.get("impacts", "").strip()
        email = request.form.get("email", "").strip()

        # ---------- VALIDATION ----------
        if not file or file.filename == "":
            return render_template("result.html", table="❌ No file uploaded")

        if not file.filename.endswith(".csv"):
            return render_template("result.html", table="❌ Upload CSV file only")

        if not weights or not impacts or not email:
            return render_template("result.html", table="❌ All fields are required")

        # ---------- SAVE CSV SAFELY ----------
        temp_path = os.path.join(tempfile.gettempdir(), file.filename)
        file.save(temp_path)
        df = pd.read_csv(temp_path)
        os.remove(temp_path)

        # ---------- PARSE INPUT ----------
        weights_list = list(map(float, weights.split(",")))
        impacts_list = [i.strip() for i in impacts.split(",")]

        data = df.iloc[:, 1:].astype(float)
        n = data.shape[1]

        if len(weights_list) != n or len(impacts_list) != n:
            return render_template("result.html", table="❌ Weights/Impacts count mismatch")

        for i in impacts_list:
            if i not in ["+", "-"]:
                return render_template("result.html", table="❌ Impacts must be + or -")

        # ---------- TOPSIS ----------
        norm = data / np.sqrt((data ** 2).sum())
        weighted = norm * np.array(weights_list)

        ideal_best = []
        ideal_worst = []

        for i in range(n):
            if impacts_list[i] == "+":
                ideal_best.append(weighted.iloc[:, i].max())
                ideal_worst.append(weighted.iloc[:, i].min())
            else:
                ideal_best.append(weighted.iloc[:, i].min())
                ideal_worst.append(weighted.iloc[:, i].max())

        ideal_best = np.array(ideal_best)
        ideal_worst = np.array(ideal_worst)

        d_best = np.sqrt(((weighted - ideal_best) ** 2).sum(axis=1))
        d_worst = np.sqrt(((weighted - ideal_worst) ** 2).sum(axis=1))

        score = d_worst / (d_best + d_worst)

        df["Topsis Score"] = score.round(6)
        df["Rank"] = df["Topsis Score"].rank(ascending=False).astype(int)
        df = df.sort_values("Rank")

        result_csv = df.to_csv(index=False)

        # ---------- SEND EMAIL (RESEND) ----------
        send_email(email, result_csv)

        table_html = df.to_html(classes="table table-bordered table-striped", index=False)

        return render_template(
            "result.html",
            table="<p style='color:green;'>✅ Result sent to email</p>" + table_html
        )

    except Exception as e:
        return render_template("result.html", table=f"❌ Error: {str(e)}")


# ---------------- EMAIL (RESEND ONLY) ----------------
def send_email(receiver, csv_content):
    resend.api_key = os.environ.get("RESEND_API_KEY")

    if not resend.api_key:
        raise Exception("RESEND_API_KEY not set")

    resend.Emails.send({
        "from": "onboarding@resend.dev",
        "to": receiver,
        "subject": "TOPSIS Result",
        "html": "<h3>Your TOPSIS result is attached</h3>",
        "attachments": [
            {
                "filename": "result.csv",
                "content": csv_content
            }
        ]
    })


# ---------------- RUN ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
