from django.urls import path
from . import views

urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('new/', views.ParentPlaylistCreateView.as_view(), name='new'),
    path('delete/<int:pk>', views.ParentPlaylistDeleteView.as_view(), name='delete'),
    path('<int:pk>/', views.ParentPlaylistEditView.as_view(), name='edit'),
    path('<int:pk>/remove/', views.remove_multiple_playlists, name='remove_playlists'),
    path('<int:pk>/add/<str:child_uri>', views.add_playlist, name='add_playlist'),
    path('<int:pk>/add_multi/', views.add_multiple_playlists, name='add_multiple_playlists'),
    path('<int:pk>/merge', views.merge_now, name='merge'),
]
