from django.urls import path

from .views import (
    ChapterBulkAPIView,
    ChapterAPIView,
    NoteBulkAPIView,
    NoteAPIView,
    SchoolClassBulkAPIView,
    SchoolClassAPIView,
    SubjectBulkAPIView,
    SubjectAPIView,
)

urlpatterns = [
    path("classes/bulk/", SchoolClassBulkAPIView.as_view(), name="class-bulk-create"),
    path("classes/", SchoolClassAPIView.as_view(), name="class-list-create"),
    path("classes/<uuid:uuid>/", SchoolClassAPIView.as_view(), name="class-detail"),
    path("subjects/bulk/", SubjectBulkAPIView.as_view(), name="subject-bulk-create"),
    path("subjects/", SubjectAPIView.as_view(), name="subject-list-create"),
    path("subjects/<uuid:uuid>/", SubjectAPIView.as_view(), name="subject-detail"),
    path("chapters/bulk/", ChapterBulkAPIView.as_view(), name="chapter-bulk-create"),
    path("chapters/", ChapterAPIView.as_view(), name="chapter-list"),
    path("chapters/<uuid:uuid>/", ChapterAPIView.as_view(), name="chapter-detail"),
    path("notes/bulk/", NoteBulkAPIView.as_view(), name="note-bulk-create"),
    path("notes/", NoteAPIView.as_view(), name="note-list"),
    path("notes/<uuid:uuid>/", NoteAPIView.as_view(), name="note-detail"),
]
