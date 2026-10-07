from django.core.files.storage import default_storage
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import IsStaffOrReadOnly
from .models import (
    Bookmark,
    Chapter,
    Note,
    PracticeQuestion,
    SchoolClass,
    ScheduledTest,
    StudyGoal,
    Subject,
    Topic,
)
from .pagination import paginated_response, valid_uuid
from .serializers import (
    ChapterSerializer,
    NoteSerializer,
    SubjectSerializer,
    TopicSerializer,
)
from .services import (
    bookmark_payload,
    collect_formulas,
    import_practice_questions,
    import_structured_note,
    mark_progress,
    objective_options,
    objective_questions,
    outline_for_subject,
    managed_question,
    progress_summary,
    public_objective_question,
    reading_target,
    reorder_blocks,
    search_catalog,
    student_notes,
    student_topics,
    user_bookmarks,
    visible_status,
)


def _bad(message, code=status.HTTP_400_BAD_REQUEST):
    return Response({"message": message}, status=code)


class ClassSubjectsAPIView(APIView):
    permission_classes = [IsStaffOrReadOnly]

    def get(self, request, uuid):
        school_class = get_object_or_404(SchoolClass, uuid=uuid)
        subjects = school_class.subjects.all().order_by("subject_name")
        rows = []
        for subject in subjects:
            data = SubjectSerializer(subject).data
            data["chapter_count"] = subject.chapters.count()
            rows.append(data)
        return Response(
            {"message": "Subjects fetched successfully", "data": rows},
            status=status.HTTP_200_OK,
        )


class SubjectChaptersAPIView(APIView):
    permission_classes = [IsStaffOrReadOnly]

    def get(self, request, uuid):
        subject = get_object_or_404(Subject, uuid=uuid)
        chapters = subject.chapters.all().order_by("chapter_number")
        return paginated_response(
            chapters,
            request,
            ChapterSerializer,
            "Chapters fetched successfully",
        )


class SubjectOutlineAPIView(APIView):
    permission_classes = [IsStaffOrReadOnly]

    def get(self, request, uuid):
        subject = get_object_or_404(Subject.objects.select_related("school_class"), uuid=uuid)
        return Response(
            {
                "message": "Outline fetched successfully",
                "data": {
                    "subject": SubjectSerializer(subject).data,
                    "chapters": outline_for_subject(subject, request.user),
                },
            }
        )


class ChapterTopicsAPIView(APIView):
    permission_classes = [IsStaffOrReadOnly]

    def get(self, request, uuid):
        chapter = get_object_or_404(Chapter, uuid=uuid)
        topics = student_topics(request.user).filter(chapter=chapter).order_by("sort_order", "title")
        data = TopicSerializer(topics, many=True).data
        if not data:
            notes = student_notes(request.user).filter(chapter=chapter, topic__isnull=True)
            data = [
                {
                    "uuid": str(note.uuid),
                    "title": note.title,
                    "description": note.description,
                    "status": note.status,
                    "sort_order": note.sort_order,
                    "kind": "note",
                    "chapter": str(chapter.uuid),
                }
                for note in notes
            ]
        return Response({"message": "Topics fetched successfully", "data": data})


class TopicAPIView(APIView):
    permission_classes = [IsStaffOrReadOnly]

    def get(self, request, uuid=None):
        if uuid:
            topic, note = reading_target(uuid)
            if topic is None and note is None:
                return _bad("Topic not found", status.HTTP_404_NOT_FOUND)
            if topic is not None:
                payload = TopicSerializer(topic).data
                payload["kind"] = "topic"
                payload["chapter_name"] = topic.chapter.chapter_name
                payload["subject_name"] = topic.chapter.subject.subject_name
                payload["subject_uuid"] = str(topic.chapter.subject.uuid)
            else:
                payload = {
                    "uuid": str(note.uuid),
                    "title": note.title,
                    "description": note.description,
                    "status": note.status,
                    "kind": "note",
                    "chapter": str(note.chapter.uuid),
                    "chapter_name": note.chapter.chapter_name,
                    "subject_name": note.chapter.subject.subject_name,
                    "subject_uuid": str(note.chapter.subject.uuid),
                }
            return Response({"message": "Topic fetched successfully", "data": payload})

        chapter = request.query_params.get("chapter")
        topics = student_topics(request.user)
        if chapter:
            if not valid_uuid(chapter):
                return _bad("Invalid chapter UUID")
            topics = topics.filter(chapter__uuid=chapter)
        return paginated_response(topics.order_by("sort_order", "title"), request, TopicSerializer, "Topics fetched successfully")

    def post(self, request):
        serializer = TopicSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"message": "Topic created successfully", "data": serializer.data},
            status=status.HTTP_201_CREATED,
        )

    def put(self, request, uuid):
        topic = get_object_or_404(Topic, uuid=uuid)
        serializer = TopicSerializer(topic, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "Topic updated successfully", "data": serializer.data})

    def delete(self, request, uuid):
        topic = get_object_or_404(Topic, uuid=uuid)
        topic.delete()
        return Response({"message": "Topic deleted successfully", "data": None})


class TopicNotesAPIView(APIView):
    permission_classes = [IsStaffOrReadOnly]

    def get(self, request, uuid):
        topic, note = reading_target(uuid)
        if topic is None and note is None:
            return _bad("Topic not found", status.HTTP_404_NOT_FOUND)
        if topic is not None:
            notes = student_notes(request.user).filter(topic=topic).order_by("sort_order", "created_at")
            if not notes.exists():
                notes = student_notes(request.user).filter(chapter=topic.chapter, title=topic.title)
        else:
            notes = student_notes(request.user).filter(pk=note.pk)
        return paginated_response(notes, request, NoteSerializer, "Notes fetched successfully")


class TopicPracticeAPIView(APIView):
    permission_classes = [IsStaffOrReadOnly]

    def get(self, request, uuid):
        topic, note = reading_target(uuid)
        questions = PracticeQuestion.objects.select_related("chapter", "topic")
        publish = visible_status(request.user)
        if publish:
            questions = questions.filter(status=publish)
        difficulty = request.query_params.get("difficulty")
        if difficulty:
            questions = questions.filter(difficulty=difficulty)
        if topic is not None:
            questions = questions.filter(topic=topic)
        elif note is not None:
            questions = questions.filter(chapter=note.chapter, topic__isnull=True)
        else:
            return _bad("Topic not found", status.HTTP_404_NOT_FOUND)
        return Response(
            {
                "message": "Practice questions fetched successfully",
                "data": [
                    {
                        "uuid": str(item.uuid),
                        "prompt": item.prompt,
                        "answer": item.answer,
                        "explanation": item.explanation,
                        "difficulty": item.difficulty,
                    }
                    for item in questions.order_by("sort_order", "created_at")[:100]
                ],
            }
        )


class PracticeQuestionListAPIView(APIView):
    permission_classes = [IsStaffOrReadOnly]

    def get(self, request):
        questions = PracticeQuestion.objects.select_related("chapter__subject", "topic")
        publish = visible_status(request.user)
        if publish:
            questions = questions.filter(status=publish)
        subject = request.query_params.get("subject")
        difficulty = request.query_params.get("difficulty")
        if subject:
            if not valid_uuid(subject):
                return _bad("Invalid subject UUID")
            questions = questions.filter(chapter__subject__uuid=subject)
        if difficulty:
            questions = questions.filter(difficulty=difficulty)
        school_class = request.query_params.get("school_class")
        if school_class:
            if not valid_uuid(school_class):
                return _bad("Invalid school_class UUID")
            questions = questions.filter(chapter__subject__school_class__uuid=school_class)
        page = questions.order_by("sort_order", "created_at")
        chapter = request.query_params.get("chapter")
        if chapter:
            if not valid_uuid(chapter):
                return _bad("Invalid chapter UUID")
            page = page.filter(chapter__uuid=chapter)[:100]
        else:
            page = page[:20]
        staff = request.user.is_authenticated and request.user.is_staff
        return Response(
            {
                "message": "Practice questions fetched successfully",
                "data": [managed_question(item, include_answer=staff or not chapter) for item in page],
            }
        )

    def post(self, request):
        chapter = get_object_or_404(Chapter, uuid=request.data.get("chapter"))
        topic = None
        topic_uuid = request.data.get("topic")
        if topic_uuid:
            topic = get_object_or_404(Topic, uuid=topic_uuid)
        prompt = (request.data.get("prompt") or request.data.get("question") or "").strip()
        if not prompt:
            return _bad("prompt is required")
        difficulty = request.data.get("difficulty") or "medium"
        if difficulty not in {"easy", "medium", "hard"}:
            return _bad("difficulty must be easy, medium, or hard")
        question = PracticeQuestion.objects.create(
            chapter=chapter,
            topic=topic,
            prompt=prompt,
            option_a=request.data.get("option_a") or "",
            option_b=request.data.get("option_b") or "",
            option_c=request.data.get("option_c") or "",
            option_d=request.data.get("option_d") or "",
            correct_option=objective_options({
                "correct": request.data.get("correct_option") or request.data.get("correct") or "",
            })[1],
            answer=request.data.get("answer") or "",
            explanation=request.data.get("explanation") or "",
            difficulty=difficulty,
            status=request.data.get("status") or "published",
        )
        return Response(
            {"message": "Practice question created", "data": {"uuid": str(question.uuid)}},
            status=status.HTTP_201_CREATED,
        )


class PracticeQuestionDetailAPIView(APIView):
    permission_classes = [IsStaffOrReadOnly]

    def put(self, request, uuid):
        question = get_object_or_404(PracticeQuestion, uuid=uuid)
        prompt = (request.data.get("prompt") or request.data.get("question") or "").strip()
        if not prompt:
            return _bad("prompt is required")
        options, correct = objective_options(request.data)
        question.prompt = prompt
        question.option_a = options["A"]
        question.option_b = options["B"]
        question.option_c = options["C"]
        question.option_d = options["D"]
        question.correct_option = correct
        question.explanation = request.data.get("explanation", question.explanation) or ""
        question.save()
        return Response(
            {
                "message": "Question updated",
                "data": managed_question(question, include_answer=True),
            }
        )

    def delete(self, request, uuid):
        question = get_object_or_404(PracticeQuestion, uuid=uuid)
        question.delete()
        return Response({"message": "Question deleted", "data": None})


class SearchAPIView(APIView):
    permission_classes = [IsStaffOrReadOnly]

    def get(self, request):
        try:
            results = search_catalog(request.query_params.get("q", ""), request.user)
        except ValueError as exc:
            return _bad(str(exc))
        return Response({"message": "Search completed", "data": results})


class FormulaAPIView(APIView):
    permission_classes = [IsStaffOrReadOnly]

    def get(self, request):
        subject = request.query_params.get("subject")
        school_class = request.query_params.get("school_class")
        if subject and not valid_uuid(subject):
            return _bad("Invalid subject UUID")
        if school_class and not valid_uuid(school_class):
            return _bad("Invalid school_class UUID")
        try:
            limit = min(int(request.query_params.get("limit", 12)), 50)
        except ValueError:
            limit = 12
        return Response(
            {
                "message": "Formulas fetched successfully",
                "data": collect_formulas(request.user, subject, school_class, limit),
            }
        )


class BookmarkAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"message": "Bookmarks fetched successfully", "data": user_bookmarks(request.user)})

    def post(self, request):
        target_type = request.data.get("target_type")
        target_id = str(request.data.get("target_id") or "").strip()
        title = str(request.data.get("title") or "").strip()
        if target_type not in {"topic", "note", "formula", "example"}:
            return _bad("target_type must be topic, note, formula, or example")
        if not target_id or not title:
            return _bad("target_id and title are required")
        bookmark, created = Bookmark.objects.get_or_create(
            user=request.user,
            target_type=target_type,
            target_id=target_id,
            defaults={
                "title": title,
                "subtitle": request.data.get("subtitle") or "",
                "context": request.data.get("context") or {},
            },
        )
        if not created:
            bookmark.delete()
            return Response({"message": "Bookmark removed", "data": None, "added": False})
        return Response(
            {"message": "Bookmark saved", "data": bookmark_payload(bookmark), "added": True},
            status=status.HTTP_201_CREATED,
        )


class BookmarkDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, uuid):
        bookmark = get_object_or_404(Bookmark, uuid=uuid, user=request.user)
        bookmark.delete()
        return Response({"message": "Bookmark removed", "data": None})


class ProgressAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school_class = None
        class_uuid = request.query_params.get("school_class")
        if class_uuid:
            if not valid_uuid(class_uuid):
                return _bad("Invalid school_class UUID")
            school_class = get_object_or_404(SchoolClass, uuid=class_uuid)
        return Response(
            {
                "message": "Progress fetched successfully",
                "data": progress_summary(request.user, school_class),
            }
        )


class ProgressUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        topic = None
        note = None
        topic_uuid = request.data.get("topic")
        note_uuid = request.data.get("note")
        if topic_uuid:
            topic = get_object_or_404(Topic, uuid=topic_uuid)
        elif note_uuid:
            note = get_object_or_404(Note, uuid=note_uuid)
        else:
            return _bad("topic or note is required")
        completed = request.data.get("completed") if "completed" in request.data else None
        row = mark_progress(request.user, topic=topic, note=note, completed=completed)
        return Response({"message": "Progress updated", "data": {"completed": row.completed}})


class StudyGoalAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            target = int(request.data.get("daily_target"))
        except (TypeError, ValueError):
            return _bad("daily_target must be a number")
        if target < 1 or target > 20:
            return _bad("daily_target must be between 1 and 20")
        goal, _created = StudyGoal.objects.get_or_create(user=request.user)
        goal.daily_target = target
        goal.save(update_fields=["daily_target"])
        return Response({"message": "Daily goal updated", "data": {"daily_target": target}})


class ContentImportAPIView(APIView):
    permission_classes = [IsStaffOrReadOnly]

    def post(self, request):
        try:
            created = import_structured_note(request.data)
        except ValueError as exc:
            return _bad(str(exc))
        return Response(
            {
                "message": "Study content saved",
                "data": {
                    "class_uuid": str(created["school_class"].uuid),
                    "subject_uuid": str(created["subject"].uuid),
                    "chapter_uuid": str(created["chapter"].uuid),
                    "topic_uuid": str(created["topic"].uuid),
                    "note_uuid": str(created["note"].uuid),
                    "status": created["note"].status,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class QuestionImportAPIView(APIView):
    permission_classes = [IsStaffOrReadOnly]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        upload = request.FILES.get("file")
        if upload is None:
            return _bad("file is required")
        if upload.size > 5 * 1024 * 1024:
            return _bad("File must be 5 MB or smaller.")
        chapter = get_object_or_404(Chapter, uuid=request.data.get("chapter"))
        topic = None
        if request.data.get("topic"):
            topic = get_object_or_404(Topic, uuid=request.data.get("topic"))
        try:
            created = import_practice_questions(
                upload,
                chapter,
                topic,
                request.data.get("status") or "published",
            )
        except ValueError as exc:
            return _bad(str(exc))
        return Response(
            {
                "message": f"{len(created)} questions imported",
                "count": len(created),
                "data": [{"uuid": str(item.uuid), "prompt": item.prompt} for item in created],
            },
            status=status.HTTP_201_CREATED,
        )


class ImageUploadAPIView(APIView):
    permission_classes = [IsStaffOrReadOnly]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        image = request.FILES.get("image")
        if image is None:
            return _bad("image is required")
        if image.size > 8 * 1024 * 1024:
            return _bad("Image must be 8 MB or smaller.")
        extension = image.name.rsplit(".", 1)[-1].lower() if "." in image.name else ""
        if extension not in {"png", "jpg", "jpeg", "webp", "gif"}:
            return _bad("Use a PNG, JPG, WEBP, or GIF image.")
        filename = f"notes/images/{timezone.now():%Y/%m}/diagram-{timezone.now().strftime('%H%M%S%f')}.{extension}"
        saved = default_storage.save(filename, image)
        return Response(
            {
                "message": "Image uploaded",
                "data": {"url": request.build_absolute_uri(default_storage.url(saved))},
            },
            status=status.HTTP_201_CREATED,
        )


class NoteReorderAPIView(APIView):
    permission_classes = [IsStaffOrReadOnly]

    def patch(self, request, uuid):
        note = get_object_or_404(Note, uuid=uuid)
        block_ids = request.data.get("block_ids")
        if not isinstance(block_ids, list):
            return _bad("block_ids must be a list")
        try:
            reorder_blocks(note, block_ids)
        except ValueError as exc:
            return _bad(str(exc))
        return Response({"message": "Blocks reordered", "data": NoteSerializer(note).data})


class ScheduledTestAPIView(APIView):
    permission_classes = [IsStaffOrReadOnly]

    def get(self, request):
        today = timezone.localdate()
        tests = ScheduledTest.objects.select_related("subject").filter(status="published", scheduled_on__gte=today)
        school_class = request.query_params.get("school_class")
        if school_class:
            if not valid_uuid(school_class):
                return _bad("Invalid school_class UUID")
            tests = tests.filter(subject__school_class__uuid=school_class)
        if request.user.is_authenticated and request.user.is_staff and request.query_params.get("all") == "1":
            tests = ScheduledTest.objects.select_related("subject").all()
        return Response(
            {
                "message": "Tests fetched successfully",
                "data": [
                    {
                        "uuid": str(item.uuid),
                        "title": item.title,
                        "description": item.description,
                        "scheduled_on": item.scheduled_on.isoformat(),
                        "subject_name": item.subject.subject_name,
                        "subject_uuid": str(item.subject.uuid),
                        "status": item.status,
                    }
                    for item in tests.order_by("scheduled_on")[:20]
                ],
            }
        )

    def post(self, request):
        subject = get_object_or_404(Subject, uuid=request.data.get("subject"))
        title = (request.data.get("title") or "").strip()
        if not title or not request.data.get("scheduled_on"):
            return _bad("title and scheduled_on are required")
        item = ScheduledTest.objects.create(
            subject=subject,
            title=title,
            description=request.data.get("description") or "",
            scheduled_on=request.data.get("scheduled_on"),
            status=request.data.get("status") or "published",
        )
        return Response(
            {"message": "Test scheduled", "data": {"uuid": str(item.uuid)}},
            status=status.HTTP_201_CREATED,
        )


class ChapterObjectiveTestAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, uuid):
        chapter = get_object_or_404(Chapter.objects.select_related("subject"), uuid=uuid)
        questions = objective_questions(chapter, request.user)
        return Response(
            {
                "message": "Objective test fetched",
                "data": {
                    "chapter_uuid": str(chapter.uuid),
                    "title": chapter.title or chapter.chapter_name,
                    "subject_name": chapter.subject.subject_name,
                    "questions": [public_objective_question(item) for item in questions],
                },
            }
        )

    def post(self, request, uuid):
        chapter = get_object_or_404(Chapter, uuid=uuid)
        answers = request.data.get("answers") or {}
        if not isinstance(answers, dict):
            return _bad("answers must map each question to one option")
        questions = list(objective_questions(chapter, request.user))
        results = []
        correct_count = 0
        for question in questions:
            selected = str(answers.get(str(question.uuid)) or "").strip().upper()
            is_correct = bool(question.correct_option) and selected == question.correct_option
            if is_correct:
                correct_count += 1
            results.append(
                {
                    "uuid": str(question.uuid),
                    "selected": selected,
                    "correct": question.correct_option,
                    "is_correct": is_correct,
                    "explanation": question.explanation,
                }
            )
        return Response(
            {
                "message": "Test submitted",
                "data": {
                    "score": correct_count,
                    "total": len(questions),
                    "results": results,
                },
            }
        )
