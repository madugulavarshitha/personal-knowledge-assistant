import gspread
from oauth2client.service_account import ServiceAccountCredentials

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
gspread_client = gspread.authorize(creds)

try:
    print("Attempting to list files...")
    # List all files shared with this service account
    files = gspread_client.list_spreadsheet_files()
    print("Files found:", files)
    
    # Try to create a new sheet
    print("Creating new spreadsheet...")
    sh = gspread_client.create('KnowledgeBase_BotCreated')
    
    # Share it with the user's personal email? We don't know their email.
    # But we can print the ID and URL
    print(f"Successfully created! ID: {sh.id}")
    print(f"URL: {sh.url}")
except Exception as e:
    print(f"Error: {e}")
