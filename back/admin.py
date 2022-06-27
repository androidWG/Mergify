from django.contrib import admin
from back.models import BasePlaylist, ParentPlaylist, Playlist

# Register your models here.
admin.site.register(BasePlaylist)
admin.site.register(Playlist)
admin.site.register(ParentPlaylist)
