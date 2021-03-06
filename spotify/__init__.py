from datetime import datetime
from typing import Any, List, Optional

import spotipy

from back.models import ParentPlaylist
from back.utils import remove_duplicates
from spotify.token_manager import refresh_token


class SpotifyManager(spotipy.Spotify):
    def __init__(self, social_token):
        if social_token.expires_at.timestamp() < datetime.now().timestamp():
            refresh_token(social_token)
        self._social_token = social_token
        super().__init__(self._social_token.token)

    @property
    def auth(self):
        if self._social_token.expires_at.timestamp() < datetime.now().timestamp():
            refresh_token(self._social_token)

        self._auth = self._social_token.token
        return self._social_token.token

    def playlists_not_in_parent(self, parent, user_uid) -> List[Any]:
        playlists = self.user_playlists(user_uid)
        parent_ids = [x.get_id() for x in ParentPlaylist.objects.all()]

        playlists["items"] = remove_duplicates(playlists["items"], "id")
        items_list = playlists["items"].copy()

        for o in items_list:
            if o["id"] == parent.get_id():
                playlists["items"].remove(o)
            elif parent_ids.__contains__(o["id"]):
                playlists["items"].remove(o)
            else:
                for p in parent.playlist_set.all():
                    if o["id"] == p.get_id():
                        playlists["items"].remove(o)

        return playlists

    def playlist_all_tracks(self, playlist_id: str) -> Optional[Any]:
        offset = 0
        tracks = []

        while offset is not None:
            results = self.playlist_items(playlist_id, offset=offset, limit=100)
            tracks = tracks + results["items"]
            offset = offset + 100 if results["next"] is not None else None

        return tracks

    def playlist_delete_tracks(self, playlist_id: str, tracks: list[str]):
        to_delete = []

        for i, item in enumerate(tracks):
            to_delete.append(item)
            if (i % 90 == 0 and i != 0) or i == len(tracks) - 1:
                self.playlist_remove_all_occurrences_of_items(playlist_id, to_delete)
                to_delete.clear()

    def playlist_delete_all_tracks(self, playlist_id: str):
        tracks = self.playlist_all_tracks(playlist_id)
        self.playlist_delete_tracks(playlist_id, [x["track"]["uri"] for x in tracks])

    def playlist_add_tracks(self, playlist_id: str, tracks: list[str]):
        to_add = []

        for i, item in enumerate(tracks):
            to_add.append(item)
            if (i % 90 == 0 and i != 0) or i == len(tracks) - 1:
                self.playlist_add_items(playlist_id, to_add)
                to_add.clear()
