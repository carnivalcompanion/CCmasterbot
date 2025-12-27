import os
import json
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from oauth2client.service_account import ServiceAccountCredentials

class CloudStorage:
    def __init__(self):
        self.drive = self._authenticate()

    def _authenticate(self):
        scopes = ["https://www.googleapis.com/auth/drive"]

        # Load JSON from environment variable
        service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT")
        if not service_account_json:
            raise RuntimeError("GOOGLE_SERVICE_ACCOUNT env var is missing")

        credentials_dict = json.loads(service_account_json)

        credentials = ServiceAccountCredentials.from_json_keyfile_dict(
            credentials_dict,
            scopes
        )

        gauth = GoogleAuth()
        gauth.credentials = credentials
        return GoogleDrive(gauth)

    def upload_media(self, local_path):
        folder_id = os.getenv("PROCESSED_FOLDER_ID")
        filename = os.path.basename(local_path)

        file = self.drive.CreateFile({
            "title": filename,
            "parents": [{"id": folder_id}]
        })

        file.SetContentFile(local_path)
        file.Upload()

        file.InsertPermission({
            "type": "anyone",
            "value": "anyone",
            "role": "reader"
        })

        return f"https://drive.google.com/uc?export=download&id={file['id']}"
