import os
import json
from oauth2client.service_account import ServiceAccountCredentials
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

class CloudStorage:
    def __init__(self):
        self.drive = self._authenticate()

    def _authenticate(self):
        scopes = ["https://www.googleapis.com/auth/drive"]

        sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT")
        if not sa_json:
            raise RuntimeError("❌ GOOGLE_SERVICE_ACCOUNT env var missing")

        credentials_dict = json.loads(sa_json)

        credentials = ServiceAccountCredentials.from_json_keyfile_dict(
            credentials_dict,
            scopes
        )

        gauth = GoogleAuth()
        gauth.credentials = credentials

        return GoogleDrive(gauth)
