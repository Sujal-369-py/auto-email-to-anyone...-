import streamlit as st
import os, smtplib
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from langchain_groq import ChatGroq
from PyPDF2 import PdfReader
import io

# ---------------- LOAD ENV ----------------
load_dotenv()

APP_PASSWORD = os.getenv("APP_PASSWORD")
EMAIL = os.getenv("EMAIL_ADDRESS")
PASSWORD = os.getenv("EMAIL_PASSWORD")

# ---------------- SECURITY GATE ----------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("Private Email App")

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

# ---------------- RESUME PARSER ----------------
def extract_resume_text(source):
    """
    Extract text from a PDF resume.
    'source' can be a file path (str) or an UploadedFile object.
    """
    try:
        if isinstance(source, str):
            reader = PdfReader(source)
        else:
            reader = PdfReader(io.BytesIO(source.read()))
            source.seek(0)  # reset pointer so it can be re-read for attachment

        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip()
    except Exception as e:
        st.error(f"Failed to read resume: {e}")
        return ""

# ---------------- UI ----------------
st.title("AI Email Sender")
st.caption("Every email is crafted based on your resume — making it personal and relevant.")

st.divider()

# --- Resume Section ---
st.subheader("Step 1: Load Your Resume")

resume_source = st.radio(
    "Choose resume source:",
    ["Use default resume (Sujal.pdf)", "Upload my own resume"],
    horizontal=True
)

resume_file = None
resume_text = ""

if resume_source == "Upload my own resume":
    resume_file = st.file_uploader("Upload your resume (PDF)", type=["pdf"])
    if resume_file:
        resume_text = extract_resume_text(resume_file)
else:
    default_path = "Sujal.pdf"
    if os.path.exists(default_path):
        resume_text = extract_resume_text(default_path)
    else:
        st.warning("Default resume (Sujal.pdf) not found in the project directory.")

# Show extracted resume info
if resume_text:
    with st.expander("Resume loaded — click to preview extracted text"):
        st.text(resume_text[:2000] + ("..." if len(resume_text) > 2000 else ""))
    st.session_state.resume_text = resume_text
elif "resume_text" in st.session_state:
    resume_text = st.session_state.resume_text

st.divider()

# --- Email Details Section ---
st.subheader("Step 2: Compose Email")

receiver = st.text_input("Receiver Email")
subject = st.text_input("Subject")
description = st.text_area("What is this email about?", 
    placeholder="e.g. Applying for the Full Stack Developer role at Google...")
attach_resume = st.checkbox("Attach Resume to Email")

# ---------------- FUNCTIONS ----------------
def generate_email(subject, description, resume_text):
    """
    Generate a professional email using the LLM.
    The resume content is fed into the prompt so the AI can tailor
    the email based on the sender's skills, experience, and background.
    """
    prompt = f"""
You are an expert professional email writer.

I will provide you a resume. Your job is to extract ONLY the following from it:
- Technical skills and technologies
- Projects (name + what they do)
- Work experience and roles
- Education background

Then use ONLY those extracted details to write a professional email.

=== RESUME (extract skills, projects, experience only) ===
{resume_text}
=== END RESUME ===

Email context:
Subject: {subject}
Purpose: {description}
Sender Name: Sujal

STRICT RULES — FOLLOW ALL OF THESE:
1. ONLY mention relevant skills, projects, and experience from the resume.
2. NEVER include phone numbers, email addresses, portfolio URLs, GitHub links, 
   LinkedIn URLs, or ANY personal contact information in the email body.
3. NEVER include lines like "Please find my contact info" or "You can reach me at".
4. Do NOT include the subject line in the body.
5. Keep it concise — 3 to 5 short paragraphs max.
6. Start with "Dear Hiring Manager," or appropriate greeting.
7. End EXACTLY with:
   Regards,
   Sujal
8. Write ONLY the email body. No extra commentary.
"""
    return llm.invoke(prompt).content

def get_resume_bytes_for_attachment():
    """Get the resume file bytes for email attachment."""
    if resume_source == "Upload my own resume" and resume_file:
        resume_file.seek(0)
        return resume_file.read(), resume_file.name
    else:
        path = "Sujal.pdf"
        if os.path.exists(path):
            with open(path, "rb") as f:
                return f.read(), "Sujal_Resume.pdf"
    return None, None

# ---------------- GENERATE ----------------
if st.button("Generate Email", type="primary"):
    if not resume_text:
        st.error("Please load a resume first! The AI needs your resume to write a personalized email.")
    elif not subject or not description:
        st.warning("Please fill in both Subject and Description.")
    else:
        with st.spinner("Reading your resume & crafting the perfect email..."):
            st.session_state.subject = subject
            st.session_state.body = generate_email(subject, description, resume_text)

# ---------------- REVIEW + SEND ----------------
if "body" in st.session_state:
    st.divider()
    st.subheader("Step 3: Review & Send")

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
                resume_bytes, filename = get_resume_bytes_for_attachment()
                if resume_bytes:
                    part = MIMEApplication(resume_bytes, _subtype="pdf")
                    part.add_header(
                        "Content-Disposition",
                        "attachment",
                        filename=filename
                    )
                    msg.attach(part)

            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(EMAIL, PASSWORD)
            server.send_message(msg)
            server.quit()

            st.success("Email sent successfully!")

        except Exception as e:
            st.error(str(e))
