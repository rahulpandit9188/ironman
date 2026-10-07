from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import IsStaffOrReadOnly
from .models import Chapter, Note, SchoolClass, Subject
from .pagination import apply_ordering, paginated_response, valid_date, valid_uuid
from .serializers import (
    ChapterSerializer,
    NoteSerializer,
    SchoolClassSerializer,
    SubjectSerializer,
)


def retrieve_response(model, uuid, serializer_class, message):
    obj = get_object_or_404(model, uuid=uuid)
    return Response(
        {
            "message": message,
            "data": serializer_class(obj).data,
        },
        status=status.HTTP_200_OK,
    )


class BulkCreateAPIView(APIView):
    permission_classes = [IsStaffOrReadOnly]
    serializer_class = None
    item_name = "items"
    max_items = 100

    def post(self, request):
        if not isinstance(request.data, list):
            return Response(
                {"message": "Request body must be a JSON array."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not request.data:
            return Response(
                {"message": "At least one item is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(request.data) > self.max_items:
            return Response(
                {"message": f"A maximum of {self.max_items} items is allowed per request."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.serializer_class(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                serializer.save()
        except IntegrityError:
            return Response(
                {"message": "Duplicate or conflicting data found. Nothing was saved."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "message": f"{len(serializer.data)} {self.item_name} created successfully",
                "count": len(serializer.data),
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )


class SchoolClassBulkAPIView(BulkCreateAPIView):
    serializer_class = SchoolClassSerializer
    item_name = "classes"


class SubjectBulkAPIView(BulkCreateAPIView):
    serializer_class = SubjectSerializer
    item_name = "subjects"


class ChapterBulkAPIView(BulkCreateAPIView):
    serializer_class = ChapterSerializer
    item_name = "chapters"


class NoteBulkAPIView(BulkCreateAPIView):
    serializer_class = NoteSerializer
    item_name = "notes"


class SchoolClassAPIView(APIView):
    permission_classes = [IsStaffOrReadOnly]

    def get(self, request, uuid=None):
        if uuid:
            return retrieve_response(
                SchoolClass,
                uuid,
                SchoolClassSerializer,
                "Class fetched successfully",
            )

        school_classes = SchoolClass.objects.all()
        class_name = request.query_params.get("class_name")
        medium = request.query_params.get("medium")
        title = request.query_params.get("title")
        search = request.query_params.get("search")

        if class_name:
            school_classes = school_classes.filter(class_name__icontains=class_name)
        if medium:
            school_classes = school_classes.filter(medium__iexact=medium)
        if title:
            school_classes = school_classes.filter(title__icontains=title)
        if search:
            school_classes = school_classes.filter(
                Q(class_name__icontains=search)
                | Q(title__icontains=search)
                | Q(description__icontains=search)
                | Q(medium__icontains=search)
            )

        school_classes = apply_ordering(
            school_classes,
            request.query_params.get("ordering"),
            {"uuid", "class_name", "title", "medium"},
            "uuid",
        )
        return paginated_response(
            school_classes,
            request,
            SchoolClassSerializer,
            "Classes fetched successfully",
        )

    def post(self, request):
        serializer = SchoolClassSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"message": "Class created successfully", "data": serializer.data},
            status=status.HTTP_201_CREATED,
        )

    def put(self, request, uuid):
        school_class = get_object_or_404(SchoolClass, uuid=uuid)
        serializer = SchoolClassSerializer(school_class, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"message": "Class updated successfully", "data": serializer.data},
            status=status.HTTP_200_OK,
        )

    def delete(self, request, uuid):
        school_class = get_object_or_404(SchoolClass, uuid=uuid)
        school_class.delete()
        return Response(
            {"message": "Class deleted successfully", "data": None},
            status=status.HTTP_200_OK,
        )


class SubjectAPIView(APIView):
    permission_classes = [IsStaffOrReadOnly]

    def get(self, request, uuid=None):
        if uuid:
            return retrieve_response(
                Subject,
                uuid,
                SubjectSerializer,
                "Subject fetched successfully",
            )

        subjects = Subject.objects.select_related("school_class").all()
        school_class = request.query_params.get("school_class")
        subject_name = request.query_params.get("subject_name")
        title = request.query_params.get("title")
        search = request.query_params.get("search")

        if school_class:
            if not valid_uuid(school_class):
                return Response(
                    {"message": "Invalid school_class UUID"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            subjects = subjects.filter(school_class__uuid=school_class)
        if subject_name:
            subjects = subjects.filter(subject_name__icontains=subject_name)
        if title:
            subjects = subjects.filter(title__icontains=title)
        if search:
            subjects = subjects.filter(
                Q(subject_name__icontains=search)
                | Q(title__icontains=search)
                | Q(description__icontains=search)
                | Q(school_class__class_name__icontains=search)
            )

        subjects = apply_ordering(
            subjects,
            request.query_params.get("ordering"),
            {"uuid", "subject_name", "title"},
            "uuid",
        )
        return paginated_response(
            subjects,
            request,
            SubjectSerializer,
            "Subjects fetched successfully",
        )

    def post(self, request):
        serializer = SubjectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"message": "Subject created successfully", "data": serializer.data},
            status=status.HTTP_201_CREATED,
        )

    def put(self, request, uuid):
        subject = get_object_or_404(Subject, uuid=uuid)
        serializer = SubjectSerializer(subject, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"message": "Subject updated successfully", "data": serializer.data},
            status=status.HTTP_200_OK,
        )

    def patch(self, request, uuid):
        subject = get_object_or_404(Subject, uuid=uuid)
        serializer = SubjectSerializer(subject, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"message": "Subject updated successfully", "data": serializer.data},
            status=status.HTTP_200_OK,
        )

    def delete(self, request, uuid):
        subject = get_object_or_404(Subject, uuid=uuid)
        subject.delete()
        return Response(
            {"message": "Subject deleted successfully", "data": None},
            status=status.HTTP_200_OK,
        )


class ChapterAPIView(APIView):
    permission_classes = [IsStaffOrReadOnly]

    def get(self, request, uuid=None):
        if uuid:
            return retrieve_response(
                Chapter,
                uuid,
                ChapterSerializer,
                "Chapter fetched successfully",
            )

        chapters = Chapter.objects.select_related("subject").all()
        subject = request.query_params.get("subject")
        chapter_name = request.query_params.get("chapter_name")
        chapter_number = request.query_params.get("chapter_number")
        search = request.query_params.get("search")

        if subject:
            if not valid_uuid(subject):
                return Response(
                    {"message": "Invalid subject UUID"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            chapters = chapters.filter(subject__uuid=subject)
        if chapter_name:
            chapters = chapters.filter(chapter_name__icontains=chapter_name)
        if chapter_number:
            try:
                chapters = chapters.filter(chapter_number=int(chapter_number))
            except ValueError:
                return Response(
                    {"message": "chapter_number must be an integer"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        if search:
            chapters = chapters.filter(
                Q(chapter_name__icontains=search)
                | Q(title__icontains=search)
                | Q(description__icontains=search)
                | Q(subject__subject_name__icontains=search)
            )

        chapters = apply_ordering(
            chapters,
            request.query_params.get("ordering"),
            {"uuid", "chapter_name", "chapter_number", "title"},
            "uuid",
        )
        return paginated_response(
            chapters,
            request,
            ChapterSerializer,
            "Chapters fetched successfully",
        )

    def post(self, request):
        serializer = ChapterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"message": "Chapter created successfully", "data": serializer.data},
            status=status.HTTP_201_CREATED,
        )

    def put(self, request, uuid):
        chapter = get_object_or_404(Chapter, uuid=uuid)
        serializer = ChapterSerializer(chapter, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"message": "Chapter updated successfully", "data": serializer.data},
            status=status.HTTP_200_OK,
        )

    def patch(self, request, uuid):
        chapter = get_object_or_404(Chapter, uuid=uuid)
        serializer = ChapterSerializer(chapter, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"message": "Chapter updated successfully", "data": serializer.data},
            status=status.HTTP_200_OK,
        )

    def delete(self, request, uuid):
        chapter = get_object_or_404(Chapter, uuid=uuid)
        chapter.delete()
        return Response(
            {"message": "Chapter deleted successfully", "data": None},
            status=status.HTTP_200_OK,
        )


class NoteAPIView(APIView):
    permission_classes = [IsStaffOrReadOnly]

    def get(self, request, uuid=None):
        if uuid:
            return retrieve_response(
                Note,
                uuid,
                NoteSerializer,
                "Note fetched successfully",
            )

        notes = Note.objects.select_related(
            "chapter",
            "chapter__subject",
            "chapter__subject__school_class",
            "topic",
        ).all()

        school_class = request.query_params.get("school_class")
        subject = request.query_params.get("subject")
        chapter = request.query_params.get("chapter")
        title = request.query_params.get("title")
        created_after = request.query_params.get("created_after")
        created_before = request.query_params.get("created_before")
        search = request.query_params.get("search")

        if school_class:
            if not valid_uuid(school_class):
                return Response(
                    {"message": "Invalid school_class UUID"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            notes = notes.filter(chapter__subject__school_class__uuid=school_class)
        if subject:
            if not valid_uuid(subject):
                return Response(
                    {"message": "Invalid subject UUID"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            notes = notes.filter(chapter__subject__uuid=subject)
        if chapter:
            if not valid_uuid(chapter):
                return Response(
                    {"message": "Invalid chapter UUID"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            notes = notes.filter(chapter__uuid=chapter)
        if title:
            notes = notes.filter(title__icontains=title)
        if created_after:
            if not valid_date(created_after):
                return Response(
                    {"message": "created_after must use YYYY-MM-DD format"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            notes = notes.filter(created_at__date__gte=created_after)
        if created_before:
            if not valid_date(created_before):
                return Response(
                    {"message": "created_before must use YYYY-MM-DD format"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            notes = notes.filter(created_at__date__lte=created_before)
        if search:
            notes = notes.filter(
                Q(title__icontains=search)
                | Q(content__icontains=search)
                | Q(important_notes__icontains=search)
                | Q(vvip_questions__icontains=search)
                | Q(chapter__chapter_name__icontains=search)
            )
        status_filter = request.query_params.get("status")
        if status_filter:
            notes = notes.filter(status=status_filter)
        elif not (request.user.is_authenticated and request.user.is_staff):
            notes = notes.filter(status="published")

        notes = apply_ordering(
            notes,
            request.query_params.get("ordering"),
            {"uuid", "title", "created_at", "updated_at"},
            "uuid",
        )
        return paginated_response(
            notes,
            request,
            NoteSerializer,
            "Notes fetched successfully",
        )

    def post(self, request):
        serializer = NoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"message": "Note created successfully", "data": serializer.data},
            status=status.HTTP_201_CREATED,
        )

    def put(self, request, uuid):
        note = get_object_or_404(Note, uuid=uuid)
        serializer = NoteSerializer(note, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"message": "Note updated successfully", "data": serializer.data},
            status=status.HTTP_200_OK,
        )

    def patch(self, request, uuid):
        note = get_object_or_404(Note, uuid=uuid)
        serializer = NoteSerializer(note, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"message": "Note updated successfully", "data": serializer.data},
            status=status.HTTP_200_OK,
        )

    def delete(self, request, uuid):
        note = get_object_or_404(Note, uuid=uuid)
        note.delete()
        return Response(
            {"message": "Note deleted successfully", "data": None},
            status=status.HTTP_200_OK,
        )
