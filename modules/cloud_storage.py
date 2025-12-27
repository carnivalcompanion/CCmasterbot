import os
import json
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from oauth2client.service_account import ServiceAccountCredentials
import logging

logger = logging.getLogger(__name__)


class CloudStorage:
    def __init__(self):
        self.drive = self._authenticate()

    def _authenticate(self):
        """Authenticate with Google Drive using multiple methods"""
        scopes = ["https://www.googleapis.com/auth/drive"]
        
        # Method 1: Try to read from Render Secret Files
        secret_file_path = '/etc/secrets/google-service-account.json'
        credentials_dict = None
        
        if os.path.exists(secret_file_path):
            try:
                logger.info("Found Google service account in secret file")
                with open(secret_file_path, 'r') as f:
                    credentials_dict = json.load(f)
            except Exception as e:
                logger.error(f"Failed to read secret file: {e}")
        
        # Method 2: Fallback to environment variable
        if not credentials_dict:
            service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT")
            if not service_account_json:
                raise RuntimeError(
                    "Google Service Account credentials not found. "
                    "Either set GOOGLE_SERVICE_ACCOUNT environment variable "
                    "or upload google-service-account.json as a Secret File."
                )
            
            try:
                # Try to parse as JSON string
                credentials_dict = json.loads(service_account_json)
                logger.info("Loaded credentials from environment variable")
            except json.JSONDecodeError as e:
                # If JSON parsing fails, it might be a path to a file
                if os.path.exists(service_account_json):
                    try:
                        with open(service_account_json, 'r') as f:
                            credentials_dict = json.load(f)
                        logger.info(f"Loaded credentials from file: {service_account_json}")
                    except Exception as file_error:
                        raise RuntimeError(
                            f"Failed to read credentials from file {service_account_json}: {file_error}"
                        )
                else:
                    raise RuntimeError(
                        f"Failed to parse GOOGLE_SERVICE_ACCOUNT as JSON: {e}. "
                        "It should be either a JSON string or a path to a JSON file."
                    )
        
        try:
            credentials = ServiceAccountCredentials.from_json_keyfile_dict(
                credentials_dict, scopes
            )
            
            gauth = GoogleAuth()
            gauth.credentials = credentials
            logger.info("Successfully authenticated with Google Drive")
            return GoogleDrive(gauth)
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise RuntimeError(f"Failed to authenticate with Google Drive: {e}")

    def upload_media(self, local_path):
        """Upload media to Google Drive and make it publicly accessible"""
        folder_id = os.getenv("PROCESSED_FOLDER_ID")
        if not folder_id:
            raise RuntimeError("PROCESSED_FOLDER_ID env var missing")

        if not os.path.exists(local_path):
            raise RuntimeError(f"Local file not found: {local_path}")

        filename = os.path.basename(local_path)
        
        try:
            file = self.drive.CreateFile({
                "title": filename,
                "parents": [{"id": folder_id}]
            })

            logger.info(f"Uploading {filename} to Google Drive...")
            file.SetContentFile(local_path)
            file.Upload()
            
            # Make the file publicly accessible
            file.InsertPermission({
                "type": "anyone",
                "value": "anyone",
                "role": "reader"
            })

            file_url = f"https://drive.google.com/uc?export=download&id={file['id']}"
            logger.info(f"Upload successful: {file_url}")
            
            return file_url
            
        except Exception as e:
            logger.error(f"Failed to upload {filename}: {e}")
            raise RuntimeError(f"Upload failed: {e}")

    def list_files(self, folder_id=None):
        """List files in a Google Drive folder"""
        if not folder_id:
            folder_id = os.getenv("SOURCE_FOLDER_ID")
            if not folder_id:
                raise RuntimeError("SOURCE_FOLDER_ID env var missing")

        query = f"'{folder_id}' in parents and trashed=false"
        file_list = self.drive.ListFile({'q': query}).GetList()
        
        return [
            {
                'id': file['id'],
                'title': file['title'],
                'mimeType': file['mimeType'],
                'createdDate': file['createdDate'],
                'modifiedDate': file['modifiedDate'],
                'downloadUrl': file['downloadUrl'] if 'downloadUrl' in file else None
            }
            for file in file_list
        ]

    def download_file(self, file_id, destination_path):
        """Download a file from Google Drive"""
        try:
            file = self.drive.CreateFile({'id': file_id})
            file.GetContentFile(destination_path)
            logger.info(f"Downloaded file to: {destination_path}")
            return destination_path
        except Exception as e:
            logger.error(f"Failed to download file {file_id}: {e}")
            raise RuntimeError(f"Download failed: {e}")
