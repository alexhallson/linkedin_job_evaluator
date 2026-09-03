from unittest.mock import patch, MagicMock
from services.sheets import get_google_sheet

@patch("services.sheets.Credentials")
@patch("services.sheets.gspread")
def test_get_google_sheet(mock_gspread, mock_creds_cls):
    mock_creds = MagicMock()
    mock_creds.service_account_email = "test@service.com"
    mock_creds_cls.from_service_account_file.return_value = mock_creds
    
    mock_client = MagicMock()
    mock_spreadsheet = MagicMock()
    mock_worksheet = MagicMock()
    
    mock_gspread.authorize.return_value = mock_client
    mock_client.open.return_value = mock_spreadsheet
    mock_spreadsheet.get_worksheet.return_value = mock_worksheet
    
    sheet = get_google_sheet()
    assert sheet == mock_worksheet
    mock_client.open.assert_called_once()
    mock_spreadsheet.get_worksheet.assert_called_with(0)
