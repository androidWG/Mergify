from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('app/', views.IndexView.as_view(), name='index'),
    path('app/new/', views.new_parent, name='new'),
    path('app/delete/<int:pk>', views.DeleteView.as_view(), name='delete'),
    path('app/<int:pk>/', views.EditView.as_view(), name='edit'),
    path('app/<int:parent_id>/remove/', views.remove_playlists, name='remove_playlists'),
    path('app/<int:parent_id>/add/<str:child_uri>', views.add_playlist, name='add_playlist'),
    path('app/<int:parent_id>/merge', views.merge, name='merge'),
]