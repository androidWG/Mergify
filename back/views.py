from django.db import transaction
from django.urls import reverse, reverse_lazy
from django.views import generic
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from spotify import SpotifyManager
from .models import Item, ParentPlaylist, Playlist
from .utils import remove_duplicates


def home(request):
    return render(request, "back/home.html")


class IndexView(generic.ListView):
    template_name = "back/index.html"

    def get_queryset(self):
        return ParentPlaylist.objects.filter(user=self.request.user)


class DeleteView(generic.edit.DeleteView):
    model = ParentPlaylist
    success_url = reverse_lazy("index")

    def form_valid(self, form):
        if form.data.keys().__contains__("deletePlaylist"):
            sp = SpotifyManager(self.object.id)
            sp.current_user_unfollow_playlist(self.object.uri)
        return super().form_valid(form)


class EditView(generic.edit.UpdateView):
    model = ParentPlaylist
    fields = ["name", "allow_duplicates"]
    template_name = "back/edit.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = ParentPlaylist.objects.get(pk=self.object.id).spotify_user
        sp = SpotifyManager(self.object.id)

        context["user_playlists"] = sp.get_playlists_not_in_parent(self.object.id, user.uid)
        return context


@login_required(login_url="/")
def merge(request, parent_id):
    parent = get_object_or_404(ParentPlaylist, pk=parent_id)
    sp = SpotifyManager(parent_id)
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
            updated_items = remove_duplicates(updated_items)

        sp.playlist_delete_all_tracks(parent.uri)

        if len(updated_items) > 0:
            sp.playlist_add_tracks(parent.uri, updated_items)

        parent.snapshot_id = sp.playlist(parent.uri)["snapshot_id"]
        parent.save()

    return HttpResponseRedirect(reverse("edit", args=(parent.id,)))


@login_required(login_url="/")
def new_parent(request):
    parent = ParentPlaylist.objects.create(
        name="Merged Playlist",
        user=request.user,
        spotify_user=request.user.socialaccount_set.all()[0],
    )
    parent.save()
    return HttpResponseRedirect(reverse("edit", args=(parent.id,)))


@login_required(login_url="/")
def remove_playlists(request, parent_id):
    for p in Playlist.objects.filter(parent=ParentPlaylist.objects.get(id=parent_id)):
        for p_id in request.POST.getlist("playlists"):
            if p.id == int(p_id):
                p.delete()
    return HttpResponseRedirect(reverse("edit", args=(parent_id,)))


@login_required(login_url="/")
def add_playlist(request, parent_id, child_uri):
    parent = get_object_or_404(ParentPlaylist, pk=parent_id)
    sp = SpotifyManager(parent_id)
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
