import gspread
from google.oauth2.service_account import Credentials
from config import CREDENTIALS_FILE, SHEET_NAME

def get_google_sheet():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scope)
    client = gspread.authorize(creds)
    
    print(f"DEBUG: Authenticated as {creds.service_account_email}")
    
    spreadsheet = client.open(SHEET_NAME)
    return spreadsheet.get_worksheet(0)