from django.urls import path

from .views import (
    ChapterAPIView,
    NoteAPIView,
    SchoolClassAPIView,
    SubjectAPIView,
)

urlpatterns = [
    path("classes/", SchoolClassAPIView.as_view(), name="class-list-create"),
    path("classes/<uuid:uuid>/", SchoolClassAPIView.as_view(), name="class-detail"),
    path("subjects/", SubjectAPIView.as_view(), name="subject-list-create"),
    path("subjects/<uuid:uuid>/", SubjectAPIView.as_view(), name="subject-detail"),
    path("chapters/", ChapterAPIView.as_view(), name="chapter-list"),
    path("chapters/<uuid:uuid>/", ChapterAPIView.as_view(), name="chapter-detail"),
    path("notes/", NoteAPIView.as_view(), name="note-list"),
    path("notes/<uuid:uuid>/", NoteAPIView.as_view(), name="note-detail"),
]
