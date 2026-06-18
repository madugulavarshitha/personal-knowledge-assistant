import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Gemini setup
genai.configure(api_key="YOUR_API_KEY")

model = genai.GenerativeModel("gemini-1.5-flash")

def ask_gemini(prompt):
    response = model.generate_content(prompt)
    return response.text


# Google Sheets setup
def connect_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_name(
        "credentials.json", scope
    )

    client = gspread.authorize(creds)

    sheet = client.open("KnowledgeAssistant").sheet1

    return sheet


def save_to_sheet(question, answer):
    sheet = connect_sheet()
    sheet.append_row([question, answer])