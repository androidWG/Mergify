from typing import List
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse
from back.utils import get_id


# Create your models here.
class BasePlaylist(models.Model):
    uri = models.CharField(max_length=96, null=True)
    name = models.CharField(max_length=512, null=True, default="Merged Playlist")
    size = models.IntegerField(default=0)
    snapshot_id = models.CharField(max_length=128, null=True)

    user = models.ForeignKey(User, on_delete=models.RESTRICT)
    spotify_user = models.ForeignKey(SocialAccount, on_delete=models.RESTRICT)

    def get_id(self) -> str:
        if self.uri is None:
            return ""
        else:
            return get_id(str(self.uri))

    def __str__(self):
        return f"{self.name}"


class ParentPlaylist(BasePlaylist):
    allow_duplicates = models.BooleanField(default=False)

    def get_total_tracks(self):
        counter = 0
        for p in self.playlist_set.all():
            counter += p.size

        return counter

    def get_local_items(self) -> List:
        items = []
        for playlist in self.playlist_set.all():
            items = items + playlist.item_set.all()

        return items

    def get_absolute_url(self):
        return reverse('edit', args=(self.id,))

    def __str__(self):
        return f"{self.uri} | Owner: {self.user.username} | Allow Duplicates: {self.allow_duplicates}"


class Playlist(BasePlaylist):
    parent = models.ForeignKey(ParentPlaylist, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.name} | Parent: {self.parent.name}"


class Item(models.Model):
    uri = models.CharField(max_length=96, null=True)
    playlist = models.ForeignKey(BasePlaylist, on_delete=models.CASCADE)

    def get_id(self):
        return get_id(str(self.uri))

    def __str__(self):
        return f"{self.uri} | Playlist: {self.playlist.name}"

    def __hash__(self):
        return int(self.get_id() + self.playlist.get_id(), base=36)

    def __eq__(self, other):
        if self.get_id() == other.get_id() and self.playlist.get_id() == other.playlist.get_id():
            return True
        else:
            return False


def get_token_from_parent(value):
    parent = ""
    if type(value) == int:
        parent = ParentPlaylist.objects.get(pk=value)
    elif type(value) == ParentPlaylist:
        parent = value

    return parent.spotify_user.socialtoken_set.all()[0]
