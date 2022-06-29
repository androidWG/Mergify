# Mergify

[![GitHub license](https://img.shields.io/github/license/androidWG/Mergify?style=flat-square)](https://github.com/androidWG/Mergify/blob/main/LICENSE)
![Python version](https://img.shields.io/badge/python-v3.10-blue?style=flat-square&logo=python)

Merge spotify playlists easily and automatically. Mergify will look for updates on your playlists and automatically
update your Merged Playlist.

### Dev Setup

Clone the repo using `git clone`. Create a `.env` file inside the `mergify` and `spotify` folders.

Inside `mergify/.env`:

```dotenv
SECRET_KEY="<insert the Django secret key>"
```

Inside `spotify/.env`:

```dotenv
SPOTIFY_CLIENT_ID="<client ID created at https://developer.spotify.com/dashboard/>"
SPOTIFY_CLIENT_SECRET="<client secret created at the link above>"
```

The Django-Q cluster has to be run separetely using:

```
python manage.py qcluster
```