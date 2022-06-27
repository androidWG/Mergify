from django.db import transaction
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views import generic
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from spotify import SpotifyManager
from spotify.merge import merge
from .models import get_token_from_parent, ParentPlaylist, Playlist


@method_decorator(login_required, name="dispatch")
class IndexView(generic.ListView):
    template_name = "back/index.html"

    def get_queryset(self):
        return ParentPlaylist.objects.filter(user=self.request.user)


@method_decorator(login_required, name="dispatch")
class ParentPlaylistDeleteView(generic.edit.DeleteView):
    model = ParentPlaylist
    success_url = reverse_lazy("index")

    def form_valid(self, form):
        if form.data.keys().__contains__("deletePlaylist"):
            sp = SpotifyManager(get_token_from_parent(self.object.id))
            sp.current_user_unfollow_playlist(self.object.uri)
        return super().form_valid(form)


@method_decorator(login_required, name="dispatch")
class ParentPlaylistEditView(generic.edit.UpdateView):
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
def merge_now(request, parent_id):
    sp = SpotifyManager(get_token_from_parent(parent_id))
    if not sp.check_token():
        return HttpResponseRedirect(reverse("home"))

    merge(parent_id)

    return HttpResponseRedirect(reverse("edit", args=(parent_id,)))


@login_required()
def remove_multiple_playlists(request, parent_id):
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
