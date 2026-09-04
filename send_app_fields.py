#!/usr/bin/env python3
"""Send CLAUDE_APPLICATION_FIELDS.txt content to Youcef via Gmail."""
import os
import sys
import smtplib
import email.mime.text
import email.mime.base
import email.mime.multipart
import mimetypes
from pathlib import Path

# === CONFIG (edit these before running) ===
FROM_EMAIL = os.environ.get("GMAIL_SENDER", "motivational.lens.quotes@gmail.com")
# App Password or OAuth2 token required — SEE README below
APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

TO_EMAILS = [
    "motivational.lens.quotes@gmail.com",
]

REPO_DIR = Path(r"C:\Users\Student\Desktop\github repos\official-gisto-AI-assistant")
FIELDS_FILE = REPO_DIR / "CLAUDE_APPLICATION_FIELDS.txt"

SUBJECT = "[Gisto] Claude for Open Source Program — application field values"
BODY_HTML = """\
<p>Here are the Claude for Open Source Program application field values, ready to copy into the form.</p>
<p><strong>Repo URL:</strong> https://github.com/NIXXIOnCrac/official-gisto-AI-assistant<br>
<strong>Name:</strong> Youcef Salemtedj<br>
<strong>Email:</strong> motivational.lens.quotes@gmail.com</p>
<hr>
<p>Below is the raw field text from <code>CLAUDE_APPLICATION_FIELDS.txt</code> in the repo.</p>
<p>I've also attached the file itself so you can copy from the attachment if that's easier.</p>
"""
ATTACHMENT_PATH = str(FIELDS_FILE)


def build_message():
    outer = email.mime.multipart.MIMEMultipart("alternative")
    outer["Subject"] = SUBJECT
    outer["From"] = FROM_EMAIL
    outer["To"] = ", ".join(TO_EMAILS)
    outer["Reply-To"] = FROM_EMAIL

    # Plain text body — quick copy-paste safe
    plain = (
        "Claude for Open Source Program — application field values\n"
        "============================================================\n"
        f"Repo URL: https://github.com/NIXXIOnCrac/official-gisto-AI-assistant\n"
        f"Name: Youcef Salemtedj\n"
        f"Email: motivational.lens.quotes@gmail.com\n"
        "\n"
        "The file CLAUDE_APPLICATION_FIELDS.txt is attached.\n"
        "Copy its contents into the Claude for Open Source Program form fields.\n"
        "\n"
        "Fields covered in the file:\n"
        "  - Tell us about the project's reach and impact\n"
        "  - How will you use the subscription for your project\n"
        "  - Other info\n"
    )
    outer.attach(email.mime.text.MIMEText(plain, "plain", "utf-8"))
    outer.attach(email.mime.text.MIMEText(BODY_HTML, "html", "utf-8"))

    # Attach the fields file itself
    if FIELDS_FILE.exists():
        with FIELDS_FILE.open("rb") as f:
            payload = f.read()
        ctype, _ = mimetypes.guess_type(str(FIELDS_FILE))
        if ctype is None:
            ctype = "text/plain"
        maintype, subtype = ctype.split("/", 1)
        part = email.mime.base.MIMEBase(maintype, subtype)
        part.set_payload(payload)
        email.encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            "attachment",
            filename=FIELDS_FILE.name,
        )
        outer.attach(part)
        print(f"Attached: {FIELDS_FILE.name} ({len(payload)} bytes)")
    else:
        print(f"WARNING: fields file not found at {FIELDS_FILE}", file=sys.stderr)

    return outer


def send():
    if not APP_PASSWORD:
        print("ERROR: GMAIL_APP_PASSWORD env var is not set.", file=sys.stderr)
        print(
            "Set it and re-run, e.g.:",
            file=sys.stderr,
        )
        print(
            '  $ set GMAIL_APP_PASSWORD=<your Gmail app password> && python send_app_fields.py',
            file=sys.stderr,
        )
        print(
            "You need an APP password (not your Google account password) from:",
            file=sys.stderr,
        )
        print("  https://myaccount.google.com/apppasswords", file=sys.stderr)
        sys.exit(1)

    msg = build_message()
    msg_str = msg.as_string()
    print(f"Sending to: {', '.join(TO_EMAILS)}")
    print(f"Subject: {SUBJECT}")
    print(f"From: {FROM_EMAIL}")
    print(f"Attachment: {FIELDS_FILE.name}")

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(FROM_EMAIL, APP_PASSWORD)
            server.sendmail(FROM_EMAIL, TO_EMAILS, msg_str)
        print("SENT OK")
    except Exception as e:
        print(f"SEND FAILED: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    send()
