import streamlit as st
import os, smtplib
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from langchain_groq import ChatGroq

# ---------------- LOAD ENV ----------------
load_dotenv()

APP_PASSWORD = os.getenv("APP_PASSWORD")
EMAIL = os.getenv("EMAIL_ADDRESS")
PASSWORD = os.getenv("EMAIL_PASSWORD")

# ---------------- SECURITY GATE ----------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 Private Email App")

    pwd = st.text_input("Enter password", type="password")

    if st.button("Unlock"):
        if pwd == APP_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Wrong password")

    st.stop()

# ---------------- LLM SETUP ----------------
llm = ChatGroq(
    model="llama-3.1-8b-instant",
    temperature=0.2
)

# ---------------- UI ----------------
st.title("AI Email Sender")

receiver = st.text_input("Receiver Email")
subject = st.text_input("Subject")
description = st.text_area("What is this email about?")
attach_resume = st.checkbox("Attach Resume")

# ---------------- FUNCTIONS ----------------
def generate_email(subject, description):
    prompt = f"""
Write a professional email.

Subject: {subject}
Description: {description}

End exactly with:
Regards,
Sujal
"""
    return llm.invoke(prompt).content

def attach_resume_fn(msg):
    path = "resume.pdf"
    if os.path.exists(path):
        with open(path, "rb") as f:
            part = MIMEApplication(f.read(), _subtype="pdf")
            part.add_header(
                "Content-Disposition",
                "attachment",
                filename="Sujal_Resume.pdf"
            )
            msg.attach(part)

# ---------------- GENERATE ----------------
if st.button("Generate Email"):
    st.session_state.subject = subject
    st.session_state.body = generate_email(subject, description)

# ---------------- REVIEW + SEND ----------------
if "body" in st.session_state:
    st.subheader("Review & Edit")

    final_subject = st.text_input(
        "Final Subject",
        value=st.session_state.subject
    )

    final_body = st.text_area(
        "Final Email Body",
        value=st.session_state.body,
        height=300
    )

    confirm = st.checkbox("I confirm this email is correct")

    if st.button("Send Email") and confirm:
        try:
            msg = MIMEMultipart()
            msg["From"] = EMAIL
            msg["To"] = receiver
            msg["Subject"] = final_subject

            msg.attach(MIMEText(final_body, "plain"))

            if attach_resume:
                attach_resume_fn(msg)

            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(EMAIL, PASSWORD)
            server.send_message(msg)
            server.quit()

            st.success("Email sent successfully")

        except Exception as e:
            st.error(str(e))
