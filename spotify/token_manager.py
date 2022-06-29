import base64
import os
from datetime import datetime, timedelta, timezone

import requests
from allauth.socialaccount.models import SocialToken
from dotenv import load_dotenv

load_dotenv()


def refresh_token(token: SocialToken) -> SocialToken:
    auth = base64.b64encode(f"{os.getenv('SPOTIFY_CLIENT_ID')}:{os.getenv('SPOTIFY_CLIENT_SECRET')}".encode("utf-8"))
    r = requests.post("https://accounts.spotify.com/api/token",
                      headers={"Authorization": f"Basic {str(auth, 'utf-8')}"},
                      data={"grant_type": "refresh_token",
                            "refresh_token": token.token_secret})

    json = r.json()
    token.token = json["access_token"]
    token.expires_at = datetime.now(timezone.utc) + timedelta(seconds=json["expires_in"])
    token.save()

    return token
