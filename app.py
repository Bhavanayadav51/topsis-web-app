from flask import Flask, render_template, request
import pandas as pd
import numpy as np
import os
import smtplib
import tempfile
import threading
from email.message import EmailMessage
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates")
)




def run_topsis(input_file, weights, impacts):
    df = pd.read_csv(input_file)
    data = df.iloc[:, 1:].astype(float)

    normalized = data / np.sqrt((data ** 2).sum())
    weighted = normalized * weights

    ideal_best = []
    ideal_worst = []

    for i in range(len(impacts)):
        if impacts[i] == '+':
            ideal_best.append(weighted.iloc[:, i].max())
            ideal_worst.append(weighted.iloc[:, i].min())
        else:
            ideal_best.append(weighted.iloc[:, i].min())
            ideal_worst.append(weighted.iloc[:, i].max())

    dist_best = np.sqrt(((weighted - ideal_best) ** 2).sum(axis=1))
    dist_worst = np.sqrt(((weighted - ideal_worst) ** 2).sum(axis=1))

    score = dist_worst / (dist_best + dist_worst)

    df["Topsis Score"] = score
    df["Rank"] = df["Topsis Score"].rank(ascending=False).astype(int)

    return df


def send_email(receiver_email, content_csv):
    try:
        sender_email = os.environ.get("EMAIL_USER")
        sender_password = os.environ.get("EMAIL_PASS")

        if not sender_email or not sender_password:
            print("Email credentials not configured")
            return False

        msg = EmailMessage()
        msg["Subject"] = "TOPSIS Result"
        msg["From"] = sender_email
        msg["To"] = receiver_email
        msg.set_content("Please find the TOPSIS results attached.")

        msg.add_attachment(
            content_csv.encode(),
            maintype="text",
            subtype="csv",
            filename="result.csv"
        )

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
        
        print(f"Email sent successfully to {receiver_email}")
        return True
    except Exception as e:
        print(f"Email error: {str(e)}")
        return False


def send_email_async(receiver_email, content_csv):
    """Send email in background thread"""
    thread = threading.Thread(target=send_email, args=(receiver_email, content_csv))
    thread.daemon = True
    thread.start()


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            file = request.files["file"]
            weights = list(map(float, request.form["weights"].split(",")))
            impacts = request.form["impacts"].split(",")

            send_email_flag = request.form.get("send_email")
            email = request.form.get("email")

            if file.filename == "":
                return "No file selected", 400

            # Use temporary directory for Vercel compatibility
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.csv', delete=False) as tmp_file:
                file.save(tmp_file.name)
                input_path = tmp_file.name

            result_df = run_topsis(input_path, weights, impacts)
            
            # Clean up temp file
            os.unlink(input_path)

            # Send email asynchronously if requested
            if send_email_flag == "on" and email:
                send_email_async(email, result_df.to_csv(index=False))

            return render_template(
                "result.html",
                tables=[result_df.to_html(classes="table table-striped", index=False)]
            )

        except Exception as e:
            return f"Error occurred: {str(e)}", 500

    return render_template("index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)