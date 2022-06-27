from django.db import transaction
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views import generic
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from spotify import SpotifyManager
from .models import get_token_from_parent, Item, ParentPlaylist, Playlist
from .utils import remove_duplicates_hashable


@method_decorator(login_required, name="dispatch")
class IndexView(generic.ListView):
    template_name = "back/index.html"

    def get_queryset(self):
        return ParentPlaylist.objects.filter(user=self.request.user)


@method_decorator(login_required, name="dispatch")
class DeleteView(generic.edit.DeleteView):
    model = ParentPlaylist
    success_url = reverse_lazy("index")

    def form_valid(self, form):
        if form.data.keys().__contains__("deletePlaylist"):
            sp = SpotifyManager(get_token_from_parent(self.object.id))
            sp.current_user_unfollow_playlist(self.object.uri)
        return super().form_valid(form)


@method_decorator(login_required, name="dispatch")
class EditView(generic.edit.UpdateView):
    model = ParentPlaylist
    fields = ["name", "allow_duplicates"]
    template_name = "back/edit.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        parent = ParentPlaylist.objects.get(pk=self.object.id)
        user = parent.spotify_user
        sp = SpotifyManager(get_token_from_parent(self.object.id))

        context["user_playlists"] = sp.playlists_not_in_parent(parent, user.uid)
        return context


@login_required()
def merge(request, parent_id):
    parent = get_object_or_404(ParentPlaylist, pk=parent_id)
    sp = SpotifyManager(get_token_from_parent(parent_id))
    if not sp.check_token():
        return HttpResponseRedirect(reverse("home"))

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

    return HttpResponseRedirect(reverse("edit", args=(parent.id,)))


@method_decorator(login_required, name="dispatch")
class ParentPlaylistCreateView(generic.edit.CreateView):
    model = ParentPlaylist
    fields = ["name", "allow_duplicates"]
    template_name = "back/create.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sp_user = self.request.user.socialaccount_set.all()[0]
        sp = SpotifyManager(sp_user.socialtoken_set.all()[0])

        context["user_playlists"] = sp.user_playlists(sp_user.uid)
        return context

    def form_valid(self, form):
        sp_user = self.request.user.socialaccount_set.all()[0]

        if form.data.keys().__contains__("create_playlist"):
            sp = SpotifyManager(sp_user.socialtoken_set.all()[0])

            response = sp.user_playlist_create(sp_user.uid,
                                               form.data["name"],
                                               public=False,
                                               description="Playlist merged by Mergify")
            form.instance.uri = response["uri"]
        else:
            form.instance.uri = form.data["selected"]

        form.instance.user = self.request.user
        form.instance.spotify_user = sp_user

        return super().form_valid(form)


@login_required()
def remove_playlists(request, parent_id):
    for p in Playlist.objects.filter(parent=ParentPlaylist.objects.get(id=parent_id)):
        for p_id in request.POST.getlist("playlists"):
            if p.id == int(p_id):
                p.delete()
    return HttpResponseRedirect(reverse("edit", args=(parent_id,)))


@login_required()
def add_multiple_playlists(request, parent_id):
    parent = ParentPlaylist.objects.get(pk=parent_id)

    with transaction.atomic():
        for data in request.POST.getlist("playlists"):
            uri, size, name = data.split("|")

            playlist = Playlist.objects.create(
                uri=uri,
                parent_id=parent_id,
                name=name,
                size=size,
                user=parent.user,
                spotify_user=parent.spotify_user)

            playlist.save()

    return HttpResponseRedirect(reverse("edit", args=(parent_id,)))


@login_required()
def add_playlist(request, parent_id, child_uri):
    parent = get_object_or_404(ParentPlaylist, pk=parent_id)
    sp = SpotifyManager(get_token_from_parent(parent_id))
    if not sp.check_token():
        return HttpResponseRedirect(reverse("home"))

    uri = request.POST["playlist_uri"] if child_uri == "0" else child_uri
    response = sp.playlist(uri)

    playlist = Playlist.objects.create(
        uri=uri,
        parent_id=parent_id,
        name=response["name"],
        size=response["tracks"]["total"],
        user=parent.user,
        spotify_user=parent.spotify_user)

    playlist.save()
    return HttpResponseRedirect(reverse("edit", args=(parent_id,)))
