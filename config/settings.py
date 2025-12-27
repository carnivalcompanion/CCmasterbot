import os

BOT_CONFIG = {
    "auto_post": True,

    "logging": {
        "level": os.getenv("LOG_LEVEL", "INFO")
    },

    "scheduler": {
        "interval_minutes": int(os.getenv("BOT_INTERVAL", 20))
    },

    "instagram": {
        "access_token": os.getenv("INSTA_ACCESS_TOKEN"),
        "business_account_id": os.getenv("IG_BUSINESS_ACCOUNT_ID")
    },

    "google_drive": {
        "public_folder_id": os.getenv("PUBLIC_DRIVE_FOLDER_ID"),
        "client_secrets": os.getenv("GOOGLE_CLIENT_SECRETS", "client_secrets.json")
    }
}
