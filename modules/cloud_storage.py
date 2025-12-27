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

    def upload_media(self, media_input):
        """
        Upload media to Google Drive and make it publicly accessible.
        
        Args:
            media_input: Can be:
                - String: Path to local file
                - Dict: Dictionary containing file path under 'path', 'file_path', 
                        'local_path', or 'filename' keys
        
        Returns:
            str: Public download URL
        """
        folder_id = os.getenv("PROCESSED_FOLDER_ID")
        if not folder_id:
            raise RuntimeError("PROCESSED_FOLDER_ID env var missing")

        # Extract the actual file path from the input
        local_path = self._extract_file_path(media_input)

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

    def _extract_file_path(self, media_input):
        """
        Extract file path from various input types.
        
        Args:
            media_input: String path or dictionary
            
        Returns:
            str: File path
        """
        if isinstance(media_input, str):
            return media_input
        
        elif isinstance(media_input, dict):
            # Try common keys that might contain file paths
            path_keys = ['path', 'file_path', 'local_path', 'filename', 'file', 'video_path']
            
            for key in path_keys:
                if key in media_input and isinstance(media_input[key], str):
                    logger.debug(f"Found file path in key '{key}': {media_input[key]}")
                    return media_input[key]
            
            # If no path found, check if there's a nested structure
            if 'media' in media_input and isinstance(media_input['media'], dict):
                for key in path_keys:
                    if key in media_input['media'] and isinstance(media_input['media'][key], str):
                        logger.debug(f"Found file path in media.{key}: {media_input['media'][key]}")
                        return media_input['media'][key]
            
            # If we get here, log the dictionary structure for debugging
            logger.error(f"Could not find file path in dictionary. Available keys: {list(media_input.keys())}")
            if 'media' in media_input:
                logger.error(f"Media sub-dictionary keys: {list(media_input['media'].keys())}")
            
            raise ValueError(
                f"Dictionary must contain a file path. Available keys: {list(media_input.keys())}"
            )
        
        else:
            raise TypeError(
                f"media_input must be string or dict, got {type(media_input)}: {media_input}"
            )

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

    def upload_string_as_file(self, content, filename, folder_id=None):
        """
        Upload a string content as a text file to Google Drive.
        
        Args:
            content (str): The text content to upload
            filename (str): Name for the file
            folder_id (str, optional): Folder ID. Uses PROCESSED_FOLDER_ID if not provided
            
        Returns:
            str: Public download URL
        """
        if not folder_id:
            folder_id = os.getenv("PROCESSED_FOLDER_ID")
            if not folder_id:
                raise RuntimeError("PROCESSED_FOLDER_ID env var missing")
        
        try:
            # Create a temporary file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
                temp_file.write(content)
                temp_path = temp_file.name
            
            # Upload the temporary file
            result = self.upload_media(temp_path)
            
            # Clean up temporary file
            os.unlink(temp_path)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to upload string as file {filename}: {e}")
            raise RuntimeError(f"Failed to upload string content: {e}")
