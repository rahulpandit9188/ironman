import io
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Chapter, Note, SchoolClass, Subject


class StudyApiTests(APITestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            email="staff@example.com",
            password="test-password",
            is_staff=True,
        )
        self.student = get_user_model().objects.create_user(
            email="student@example.com",
            password="test-password",
        )
        self.client.force_authenticate(self.staff)

    def import_note(self, status_value="published"):
        response = self.client.post(
            reverse("content-import"),
            {
                "subject": "Mathematics",
                "chapter": "Linear Equations",
                "topic": "Solving Equations",
                "description": "Solve equations in one variable.",
                "status": status_value,
                "blocks": [
                    {"type": "paragraph", "content": "A linear equation has one variable."},
                    {"type": "formula", "title": "Key Formula", "content": "x = -b/a"},
                    {"type": "example", "title": "Example 1", "content": "Solve 2x + 4 = 10"},
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return response.data["data"]

    def test_json_import_creates_class_subject_chapter_topic_and_note(self):
        created = self.import_note()

        self.assertEqual(SchoolClass.objects.get().class_name, "Class 9")
        self.assertEqual(Subject.objects.get().subject_name, "Mathematics")
        self.assertEqual(Chapter.objects.get().chapter_name, "Linear Equations")
        note = Note.objects.get()
        self.assertEqual(note.topic.title, "Solving Equations")
        self.assertEqual(note.content_blocks[1]["latex"], "x = -b/a")
        self.assertEqual(created["topic_uuid"], str(note.topic.uuid))

    def test_reimport_updates_the_same_topic(self):
        self.import_note()
        self.import_note()

        self.assertEqual(Note.objects.count(), 1)
        self.assertEqual(len(Note.objects.get().content_blocks), 3)

    def test_students_read_nested_outline_and_notes(self):
        created = self.import_note()
        self.client.force_authenticate(self.student)

        outline = self.client.get(reverse("subject-outline", args=[created["subject_uuid"]]))
        self.assertEqual(outline.status_code, status.HTTP_200_OK)
        topics = outline.data["data"]["chapters"][0]["topics"]
        self.assertEqual(topics[0]["title"], "Solving Equations")

        notes = self.client.get(reverse("topic-notes", args=[created["topic_uuid"]]))
        self.assertEqual(notes.status_code, status.HTTP_200_OK)
        self.assertEqual(notes.data["data"][0]["content_blocks"][0]["type"], "paragraph")

        subjects = self.client.get(reverse("class-subjects", args=[created["class_uuid"]]))
        self.assertEqual(subjects.data["data"][0]["chapter_count"], 1)

    def test_draft_notes_stay_hidden_from_students(self):
        created = self.import_note("draft")
        self.client.force_authenticate(None)

        listing = self.client.get(reverse("note-list"))
        self.assertEqual(listing.data["pagination"]["count"], 0)

        self.client.force_authenticate(self.staff)
        listing = self.client.get(reverse("note-list"))
        self.assertEqual(listing.data["pagination"]["count"], 1)
        self.assertEqual(str(created["note_uuid"]), str(listing.data["data"][0]["uuid"]))

    def test_search_returns_subject_chapter_topic_trail(self):
        self.import_note()
        self.client.force_authenticate(self.student)

        response = self.client.get(reverse("academic-search"), {"q": "linear"})
        titles = [item["trail"] + " " + item["title"] for item in response.data["data"]]
        self.assertTrue(any("Mathematics" in title and "Linear" in title for title in titles))

        formulas = self.client.get(reverse("formula-list"))
        self.assertEqual(formulas.data["data"][0]["latex"], "x = -b/a")

    def test_bookmarks_and_progress_require_login_and_save(self):
        created = self.import_note()
        self.client.force_authenticate(None)
        denied = self.client.get(reverse("study-progress"))
        self.assertEqual(denied.status_code, status.HTTP_401_UNAUTHORIZED)

        self.client.force_authenticate(self.student)
        saved = self.client.post(
            reverse("bookmark-list"),
            {
                "target_type": "formula",
                "target_id": "formula-1",
                "title": "Key Formula",
                "context": {"subject_uuid": created["subject_uuid"], "topic_uuid": created["topic_uuid"]},
            },
            format="json",
        )
        self.assertEqual(saved.status_code, status.HTTP_201_CREATED)
        removed = self.client.delete(reverse("bookmark-detail", args=[saved.data["data"]["uuid"]]))
        self.assertEqual(removed.status_code, status.HTTP_200_OK)

        updated = self.client.post(
            reverse("study-progress-update"),
            {"topic": created["topic_uuid"], "completed": True},
            format="json",
        )
        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        progress = self.client.get(
            reverse("study-progress"),
            {"school_class": created["class_uuid"]},
        )
        self.assertEqual(progress.data["data"]["overall"]["completed"], 1)
        self.assertEqual(progress.data["data"]["overall"]["percent"], 100)

    def test_csv_question_import_and_reorder(self):
        created = self.import_note()
        upload = io.BytesIO(b"question,answer,difficulty,explanation\nSolve x+1=2,1,easy,Subtract 1\n")
        upload.name = "questions.csv"
        response = self.client.post(
            reverse("practice-question-import"),
            {"file": upload, "chapter": created["chapter_uuid"], "topic": created["topic_uuid"]},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.client.force_authenticate(self.student)
        questions = self.client.get(reverse("topic-practice", args=[created["topic_uuid"]]))
        self.assertEqual(questions.data["data"][0]["difficulty"], "easy")

        self.client.force_authenticate(self.staff)
        note = Note.objects.get()
        flipped = list(reversed([block["id"] for block in note.content_blocks]))
        reorder = self.client.patch(
            reverse("note-reorder", args=[note.uuid]),
            {"block_ids": flipped},
            format="json",
        )
        self.assertEqual(reorder.status_code, status.HTTP_200_OK)
        self.assertEqual(reorder.data["data"]["content_blocks"][0]["id"], flipped[0])

    def test_existing_note_create_still_works_without_topic(self):
        school_class = SchoolClass.objects.create(class_name="Class 10", title="Class 10")
        subject = Subject.objects.create(
            school_class=school_class,
            subject_name="Science",
            title="Science",
        )
        chapter = Chapter.objects.create(
            subject=subject,
            chapter_name="Motion",
            chapter_number=1,
            title="Motion",
        )
        response = self.client.post(
            reverse("note-list"),
            {
                "chapter": str(chapter.uuid),
                "title": "Speed",
                "content": "Speed is distance over time.",
                "content_blocks": [{"type": "paragraph", "text": "Speed"}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["data"]["status"], "published")
        self.assertIsNone(response.data["data"]["topic"])

    def test_schedule_test(self):
        created = self.import_note()
        tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
        response = self.client.post(
            reverse("scheduled-test-list"),
            {
                "subject": created["subject_uuid"],
                "title": "Linear equations quiz",
                "scheduled_on": tomorrow,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.client.force_authenticate(self.student)
        listing = self.client.get(reverse("scheduled-test-list"))
        self.assertEqual(listing.data["data"][0]["title"], "Linear equations quiz")

    def test_chapter_objective_test_hides_the_answer_until_submit(self):
        created = self.import_note()
        created_question = self.client.post(
            reverse("practice-question-list"),
            {
                "chapter": created["chapter_uuid"],
                "prompt": "Solve x + 1 = 2",
                "option_a": "0",
                "option_b": "1",
                "option_c": "2",
                "option_d": "3",
                "correct_option": "B",
            },
            format="json",
        )
        self.assertEqual(created_question.status_code, status.HTTP_201_CREATED)
        self.client.force_authenticate(self.student)
        test = self.client.get(reverse("chapter-objective-test", args=[created["chapter_uuid"]]))
        question = test.data["data"]["questions"][0]
        self.assertEqual(len(question["options"]), 4)
        self.assertNotIn("correct", question)
        submitted = self.client.post(
            reverse("chapter-objective-test", args=[created["chapter_uuid"]]),
            {"answers": {question["uuid"]: "B"}},
            format="json",
        )
        self.assertEqual(submitted.data["data"]["score"], 1)
        self.assertEqual(submitted.data["data"]["results"][0]["correct"], "B")

        self.client.force_authenticate(self.staff)
        listing = self.client.get(
            reverse("practice-question-list"),
            {"chapter": created["chapter_uuid"]},
        )
        self.assertEqual(listing.data["data"][0]["correct_option"], "B")
        updated = self.client.put(
            reverse("practice-question-detail", args=[question["uuid"]]),
            {
                "prompt": "Solve x + 1 = 2",
                "option_a": "0",
                "option_b": "1",
                "option_c": "2",
                "option_d": "4",
                "correct_option": "B",
            },
            format="json",
        )
        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        self.assertEqual(updated.data["data"]["option_d"], "4")
        deleted = self.client.delete(reverse("practice-question-detail", args=[question["uuid"]]))
        self.assertEqual(deleted.status_code, status.HTTP_200_OK)
