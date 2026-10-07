import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


PUBLISH_STATUS = (
    ("draft", "Draft"),
    ("published", "Published"),
    ("archived", "Archived"),
)


class SchoolClass(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    class_name = models.CharField(max_length=20, unique=True)
    title = models.CharField(max_length=100)
    description = models.CharField(max_length=200, blank=True)
    medium = models.CharField(max_length=50, default="English")

    class Meta:
        verbose_name = "Class"
        verbose_name_plural = "Classes"

    def __str__(self):
        return f"{self.class_name} ({self.medium} Medium)"


class Subject(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    school_class = models.ForeignKey(
        SchoolClass,
        on_delete=models.CASCADE,
        related_name="subjects",
    )
    subject_name = models.CharField(max_length=50)
    title = models.CharField(max_length=100)
    description = models.CharField(max_length=200, blank=True)

    icon = models.CharField(max_length=50, blank=True)

    class Meta:
        unique_together = ("school_class", "subject_name")
        indexes = [
            models.Index(fields=["subject_name"]),
            models.Index(fields=["title"]),
        ]

    def __str__(self):
        return f"{self.school_class.class_name} - {self.subject_name}"


class Chapter(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="chapters",
    )
    chapter_name = models.CharField(max_length=100)
    chapter_number = models.IntegerField(default=1)
    title = models.CharField(max_length=150)
    description = models.CharField(max_length=500, blank=True)

    class Meta:
        unique_together = (
            ("subject", "chapter_name"),
            ("subject", "chapter_number"),
        )
        indexes = [
            models.Index(fields=["chapter_name"]),
            models.Index(fields=["title"]),
        ]

    def __str__(self):
        return (
            f"{self.subject.school_class.class_name} - "
            f"{self.subject.subject_name} - "
            f"Chapter {self.chapter_number}: {self.chapter_name}"
        )


class Topic(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    chapter = models.ForeignKey(
        Chapter,
        on_delete=models.CASCADE,
        related_name="topics",
    )
    title = models.CharField(max_length=255)
    description = models.CharField(max_length=500, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=PUBLISH_STATUS, default="published")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("chapter", "title")
        ordering = ("sort_order", "title")
        indexes = [
            models.Index(fields=["title"]),
            models.Index(fields=["status", "sort_order"]),
        ]

    def __str__(self):
        return f"{self.chapter.chapter_name} - {self.title}"


class Note(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    chapter = models.ForeignKey(
        Chapter,
        on_delete=models.CASCADE,
        related_name="notes",
    )
    topic = models.ForeignKey(
        Topic,
        on_delete=models.SET_NULL,
        related_name="notes",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=255)
    description = models.CharField(max_length=500, blank=True)
    content = models.TextField()
    status = models.CharField(max_length=20, choices=PUBLISH_STATUS, default="published")
    sort_order = models.PositiveIntegerField(default=0)
    content_blocks = models.JSONField(default=list, blank=True)
    important_notes = models.TextField(blank=True)
    vvip_questions = models.TextField(blank=True)
    image = models.ImageField(upload_to="notes/images/", null=True, blank=True)
    source_file = models.FileField(
        upload_to="notes/sources/%Y/%m/",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("sort_order", "created_at")
        indexes = [
            models.Index(fields=["title"]),
            models.Index(fields=["status", "sort_order"]),
        ]

    def __str__(self):
        return (
            f"{self.chapter.subject.school_class.class_name} - "
            f"{self.chapter.subject.subject_name} - "
            f"Chapter {self.chapter.chapter_number} - {self.title}"
        )


class PracticeQuestion(models.Model):
    DIFFICULTY = (
        ("easy", "Easy"),
        ("medium", "Medium"),
        ("hard", "Hard"),
    )

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    chapter = models.ForeignKey(
        Chapter,
        on_delete=models.CASCADE,
        related_name="practice_questions",
    )
    topic = models.ForeignKey(
        Topic,
        on_delete=models.CASCADE,
        related_name="practice_questions",
        null=True,
        blank=True,
    )
    prompt = models.TextField()
    option_a = models.CharField(max_length=300, blank=True)
    option_b = models.CharField(max_length=300, blank=True)
    option_c = models.CharField(max_length=300, blank=True)
    option_d = models.CharField(max_length=300, blank=True)
    correct_option = models.CharField(max_length=1, blank=True)
    answer = models.TextField(blank=True)
    explanation = models.TextField(blank=True)
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY, default="medium")
    sort_order = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=PUBLISH_STATUS, default="published")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("sort_order", "created_at")
        indexes = [
            models.Index(fields=["difficulty"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return self.prompt[:80]


class Bookmark(models.Model):
    TARGETS = (
        ("topic", "Topic"),
        ("note", "Note"),
        ("formula", "Formula"),
        ("example", "Example"),
    )

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="study_bookmarks",
    )
    target_type = models.CharField(max_length=20, choices=TARGETS)
    target_id = models.CharField(max_length=64)
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, blank=True)
    context = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "target_type", "target_id")
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["user", "target_type"]),
        ]

    def __str__(self):
        return f"{self.user_id} {self.target_type} {self.title}"


class UserProgress(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="study_progress",
    )
    topic = models.ForeignKey(
        Topic,
        on_delete=models.CASCADE,
        related_name="progress_rows",
        null=True,
        blank=True,
    )
    note = models.ForeignKey(
        Note,
        on_delete=models.CASCADE,
        related_name="progress_rows",
        null=True,
        blank=True,
    )
    viewed_at = models.DateTimeField(auto_now=True)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(topic__isnull=False) | Q(note__isnull=False),
                name="progress_has_topic_or_note",
            ),
            models.UniqueConstraint(
                fields=["user", "topic"],
                condition=Q(topic__isnull=False),
                name="unique_user_topic_progress",
            ),
            models.UniqueConstraint(
                fields=["user", "note"],
                condition=Q(note__isnull=False),
                name="unique_user_note_progress",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "completed"]),
            models.Index(fields=["viewed_at"]),
        ]

    def __str__(self):
        return f"{self.user_id} progress"


class StudyGoal(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="study_goal",
    )
    daily_target = models.PositiveSmallIntegerField(default=3)

    def __str__(self):
        return f"{self.user_id} goal {self.daily_target}"


class ScheduledTest(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="scheduled_tests",
    )
    title = models.CharField(max_length=150)
    description = models.CharField(max_length=300, blank=True)
    scheduled_on = models.DateField()
    status = models.CharField(max_length=20, choices=PUBLISH_STATUS, default="published")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("scheduled_on", "title")
        indexes = [
            models.Index(fields=["scheduled_on", "status"]),
        ]

    def __str__(self):
        return self.title
