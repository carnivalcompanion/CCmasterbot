import os
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from oauth2client.service_account import ServiceAccountCredentials

class CloudStorage:
    def __init__(self):
        self.drive = self._authenticate()

    def _authenticate(self):
        scopes = ["https://www.googleapis.com/auth/drive"]
        key_file = os.getenv("GOOGLE_SERVICE_ACCOUNT", "service_account.json")
        credentials = ServiceAccountCredentials.from_json_keyfile_name(key_file, scopes)
        gauth = GoogleAuth()
        gauth.credentials = credentials
        return GoogleDrive(gauth)

    def upload_media(self, local_path):
        folder_id = os.getenv("PUBLIC_DRIVE_FOLDER_ID")
        filename = os.path.basename(local_path)
        file = self.drive.CreateFile({
            "title": filename,
            "parents": [{"id": folder_id}]
        })
        file.SetContentFile(local_path)
        file.Upload()
        file.InsertPermission({"type": "anyone", "value": "anyone", "role": "reader"})
        return f"https://drive.google.com/uc?export=download&id={file['id']}"
