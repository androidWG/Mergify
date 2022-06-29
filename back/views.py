from functools import wraps
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, resolve_url
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views import generic
from django_q.models import Schedule
from django_q.tasks import async_task

from spotify import SpotifyManager
from spotify.merge import create_schedule, merge
from .models import get_token_from_parent, ParentPlaylist, Playlist


def check_user_permission(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            path = request.build_absolute_uri()
            resolved_login_url = resolve_url(settings.LOGIN_URL)
            # If the login url is the same scheme and net location then just
            # use the path as the "next" url.
            login_scheme, login_netloc = urlparse(resolved_login_url)[:2]
            current_scheme, current_netloc = urlparse(path)[:2]
            if (not login_scheme or login_scheme == current_scheme) and (
                    not login_netloc or login_netloc == current_netloc
            ):
                path = request.get_full_path()
            from django.contrib.auth.views import redirect_to_login

            return redirect_to_login(path, reverse("spotify_login"), "next")

        if request.user == ParentPlaylist.objects.filter(pk=kwargs["pk"])[0].user:
            return view_func(request, *args, **kwargs)

        raise Http404("Object not found")

    return _wrapped_view


class IndexView(generic.ListView):
    template_name = "back/index.html"

    def get_queryset(self):
        if self.request.user.is_authenticated:
            return ParentPlaylist.objects.filter(user=self.request.user)
        else:
            return None


@method_decorator(check_user_permission, name="dispatch")
class ParentPlaylistDeleteView(generic.edit.DeleteView):
    model = ParentPlaylist
    success_url = reverse_lazy("index")

    def form_valid(self, form):
        if form.data.keys().__contains__("deletePlaylist"):
            sp = SpotifyManager(get_token_from_parent(self.object.id))
            sp.current_user_unfollow_playlist(self.object.uri)
        return super().form_valid(form)


@method_decorator(check_user_permission, name="dispatch")
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


@check_user_permission
def merge_now(request, parent_id):
    task_id = async_task(merge, parent_id)
    print(f"Running task with id {task_id}")

    if Schedule.objects.filter(name=parent_id).count() == 0:
        create_schedule(parent_id)

    return HttpResponseRedirect(reverse("edit", args=(parent_id,)))


@check_user_permission
def setup_merge_task(request, parent_id):
    create_schedule(parent_id)

    return HttpResponseRedirect(reverse("edit", args=(parent_id,)))


@check_user_permission
def remove_multiple_playlists(request, parent_id):
    for p in Playlist.objects.filter(parent=ParentPlaylist.objects.get(id=parent_id)):
        for p_id in request.POST.getlist("playlists"):
            if p.id == int(p_id):
                p.delete()
    return HttpResponseRedirect(reverse("edit", args=(parent_id,)))


@check_user_permission
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


@check_user_permission
def add_playlist(request, parent_id, child_uri):
    parent = get_object_or_404(ParentPlaylist, pk=parent_id)
    sp = SpotifyManager(get_token_from_parent(parent_id))

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
