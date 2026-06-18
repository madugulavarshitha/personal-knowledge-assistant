import os
import json
import datetime
import re
import webbrowser
import tempfile
import shutil

from threading import Timer
from flask import Flask, request, jsonify,render_template
from flask_cors import CORS
from dotenv import load_dotenv

import gspread
from oauth2client.service_account import ServiceAccountCredentials

import fitz  # PDF
import whisper
from moviepy.editor import VideoFileClip

import google.generativeai as genai

import pytesseract
from PIL import Image


# =========================
# CONFIG
# =========================
load_dotenv()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024
CORS(app)
UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "personal_knowledge_assistant_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

print("SERVER STARTED")


# =========================
# GEMINI SETUP
# =========================
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-flash-lite-latest")


def configure_ffmpeg():
    try:
        import imageio_ffmpeg

        source = imageio_ffmpeg.get_ffmpeg_exe()
        target = os.path.join(UPLOAD_DIR, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")

        if not os.path.exists(target):
            shutil.copyfile(source, target)

        os.environ["IMAGEIO_FFMPEG_EXE"] = target
        os.environ["PATH"] = UPLOAD_DIR + os.pathsep + os.environ.get("PATH", "")
        print("FFMPEG READY:", target)
    except Exception as e:
        print("FFMPEG SETUP WARNING:", e)


# =========================
# WHISPER
# =========================
configure_ffmpeg()
whisper_model = whisper.load_model("base")


# =========================
# GOOGLE SHEETS
# =========================
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_name(
    "credentials.json",
    scope
)

gclient = gspread.authorize(creds)
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")


def get_sheet():
    sheet = gclient.open_by_key(SHEET_ID).sheet1

    if not sheet.row_values(1):
        sheet.append_row([
            "User ID",
            "Timestamp",
            "Type",
            "Content",
            "Summary",
            "Tags",
            "Insights",
            "Related Notes"
        ])

    return sheet


print("CONNECTED:", get_sheet().title)


# =========================
# SAFE JSON
# =========================
def safe_json(text):
    try:
        text = re.sub(r"```json|```", "", text).strip()
        return json.loads(text)
    except:
        return {
            "summary": "",
            "tags": [],
            "insights": [],
            "related_notes": []
        }


# =========================
# GEMINI ANALYSIS
# =========================
def analyze_content(content):

    prompt = f"""
You are an AI assistant.

Return ONLY valid JSON:

{{
  "summary": "short summary",
  "tags": ["tag1", "tag2"],
  "insights": ["insight1", "insight2"],
  "related_notes": ["related idea"]
}}

Content:
{content}
"""

    response = model.generate_content(prompt)
    return safe_json(response.text)


# =========================
# PDF
# =========================
def extract_pdf(file):
    doc = fitz.open(stream=file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text


# =========================
# AUDIO
# =========================
def transcribe_audio(path):
    result = whisper_model.transcribe(path)
    return result["text"]


# =========================
# VIDEO
# =========================
def extract_audio(video_path, audio_path):
    video = VideoFileClip(video_path)
    if video.audio is None:
        raise Exception("No audio found")
    video.audio.write_audiofile(audio_path, codec="mp3")
    video.close()


def require_uploaded_file():
    if "file" not in request.files:
        raise Exception("No file uploaded")

    file = request.files["file"]
    if not file or file.filename == "":
        raise Exception("No file selected")

    return file


def save_temp_upload(file):
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
    safe_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", file.filename or "upload")
    path = os.path.join(UPLOAD_DIR, f"{timestamp}_{safe_name}")
    file.save(path)
    return path


def content_for_sheet(filename, text):
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    return f"{filename}: {cleaned[:4000]}"


# =========================
# HOME
# =========================
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/test")
def test():
    return "OK"


@app.route("/limit")
def limit():
    return str(app.config["MAX_CONTENT_LENGTH"])


# =========================
# ADD NOTE
# =========================
@app.route("/api/add_note", methods=["POST"])
def add_note():
    try:
        print("ADD NOTE HIT")

        data = request.json
        user_id = data.get("user_id", "default")
        note = data.get("note", "")

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        result = model.generate_content(f"""
Return JSON only:

{{
"summary": "...",
"tags": [],
"insights": [],
"related_notes": []
}}

Note:
{note}
""")

        ai = safe_json(result.text)

        sheet = get_sheet()

        sheet.append_row([
            user_id,
            timestamp,
            "NOTE",
            note,
            ai["summary"],
            ", ".join(ai["tags"]),
            ", ".join(ai["insights"]),
            ", ".join(ai["related_notes"])
        ])

        return jsonify({"status": "saved", "data": ai})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =========================
# PDF UPLOAD
# =========================
@app.route("/api/upload_pdf", methods=["POST"])
def upload_pdf():
    try:
        file = require_uploaded_file()
        text = extract_pdf(file)

        if not text.strip():
            raise Exception("No readable text found in this PDF")

        ai = analyze_content(text)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        sheet = get_sheet()

        sheet.append_row([
            "global",
            timestamp,
            "PDF",
            content_for_sheet(file.filename, text),
            ai["summary"],
            ", ".join(ai["tags"]),
            ", ".join(ai["insights"]),
            ", ".join(ai["related_notes"])
        ])

        return jsonify({"data": ai})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =========================
# AUDIO UPLOAD
# =========================
@app.route("/api/upload_audio", methods=["POST"])
def upload_audio():
    path = None
    try:
        file = require_uploaded_file()
        path = save_temp_upload(file)

        text = transcribe_audio(path)

        if not text.strip():
            raise Exception("No speech detected in this audio")

        ai = analyze_content(text)

        sheet = get_sheet()

        sheet.append_row([
            "global",
            str(datetime.datetime.now()),
            "AUDIO",
            content_for_sheet(file.filename, text),
            ai["summary"],
            ", ".join(ai["tags"]),
            ", ".join(ai["insights"]),
            ", ".join(ai["related_notes"])
        ])

        return jsonify({"transcript": text, "data": ai})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if path and os.path.exists(path):
            os.remove(path)


# =========================
# VIDEO UPLOAD
# =========================
@app.route("/api/upload_video", methods=["POST"])
def upload_video():
    video_path = None
    audio_path = None
    try:
        file = require_uploaded_file()
        video_path = save_temp_upload(file)
        audio_path = os.path.join(
            UPLOAD_DIR,
            datetime.datetime.now().strftime("%Y%m%d%H%M%S%f") + "_video_audio.mp3"
        )

        extract_audio(video_path, audio_path)

        text = transcribe_audio(audio_path)

        if not text.strip():
            raise Exception("No speech detected in this video")

        ai = analyze_content(text)

        sheet = get_sheet()

        sheet.append_row([
            "global",
            str(datetime.datetime.now()),
            "VIDEO",
            content_for_sheet(file.filename, text),
            ai["summary"],
            ", ".join(ai["tags"]),
            ", ".join(ai["insights"]),
            ", ".join(ai["related_notes"])
        ])

        return jsonify({"transcript": text, "data": ai})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        for path in [video_path, audio_path]:
            if path and os.path.exists(path):
                os.remove(path)


# =========================
# SEARCH
# =========================
@app.route("/api/search", methods=["POST"])
def search():
    try:
        query = request.json.get("query")

        sheet = get_sheet()
        data = sheet.get_all_records()

        context = "\n".join([
            f"{r.get('Content','')} | {r.get('Summary','')}"
            for r in data
        ])

        response = model.generate_content(f"""
Answer based on notes:

{context}

Question: {query}
""")

        return jsonify({"answer": response.text})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =========================
# AUTO OPEN BROWSER
# =========================
def open_browser():
    webbrowser.open("http://127.0.0.1:5000")


# =========================
# RUN
# =========================
if __name__ == "__main__":
    Timer(1, open_browser).start()

    app.run(
        debug=True,
        use_reloader=False,
        host="127.0.0.1",
        port=5000
    )
