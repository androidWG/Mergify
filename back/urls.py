from django.urls import path
from . import views

urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('new/', views.new_parent, name='new'),
    path('delete/<int:pk>', views.DeleteView.as_view(), name='delete'),
    path('<int:pk>/', views.EditView.as_view(), name='edit'),
    path('<int:parent_id>/remove/', views.remove_playlists, name='remove_playlists'),
    path('<int:parent_id>/add/<str:child_uri>', views.add_playlist, name='add_playlist'),
    path('<int:parent_id>/merge', views.merge, name='merge'),
]
