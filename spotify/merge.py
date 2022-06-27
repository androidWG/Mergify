from django.db import transaction
from django.shortcuts import get_object_or_404

from back.models import get_token_from_parent, Item, ParentPlaylist
from back.utils import remove_duplicates_hashable
from spotify import SpotifyManager


def merge(parent_id):
    parent = get_object_or_404(ParentPlaylist, pk=parent_id)
    sp = SpotifyManager(get_token_from_parent(parent_id))

    if parent.uri == "" or parent.uri is None:
        response = sp.user_playlist_create(parent.spotify_user.uid,
                                           parent.name,
                                           public=False,
                                           description="Playlist merged by Mergify")
        parent.uri = response["uri"]
        parent.save()
    elif parent.name != sp.playlist(parent.uri)["name"]:
        sp.playlist_change_details(parent.uri, name=parent.name)

    changed = False
    updated_items = []

    with transaction.atomic():
        for playlist in parent.playlist_set.all():
            info = sp.playlist(playlist.uri)

            same_size = (info["tracks"]["total"] != len(playlist.item_set.all()))
            same_snapshot = (playlist.snapshot_id != info["snapshot_id"])
            if same_size or same_snapshot:
                changed = True

                tracks = [x["track"]["id"] for x in sp.playlist_all_tracks(playlist.uri)]
                playlist.item_set.all().delete()

                with transaction.atomic():
                    for track in tracks:
                        i = Item.objects.create(uri=track, playlist=playlist)
                        i.save()

                playlist.snapshot_id = sp.playlist(playlist.uri)["snapshot_id"]
                playlist.save()

            updated_items = updated_items + [x.get_id() for x in playlist.item_set.all()]

    if changed or sp.playlist(parent.uri)["snapshot_id"] != parent.snapshot_id:
        if not parent.allow_duplicates:
            updated_items = remove_duplicates_hashable(updated_items)

        sp.playlist_delete_all_tracks(parent.uri)

        if len(updated_items) > 0:
            sp.playlist_add_tracks(parent.uri, updated_items)

        parent.snapshot_id = sp.playlist(parent.uri)["snapshot_id"]
        parent.save()
