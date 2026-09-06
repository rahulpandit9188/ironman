import uuid

from django.db import models


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

    class Meta:
        unique_together = ("school_class", "subject_name")

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
        unique_together = ("subject", "chapter_name")

    def __str__(self):
        return (
            f"{self.subject.school_class.class_name} - "
            f"{self.subject.subject_name} - "
            f"Chapter {self.chapter_number}: {self.chapter_name}"
        )


class Note(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    chapter = models.ForeignKey(
        Chapter,
        on_delete=models.CASCADE,
        related_name="notes",
    )
    title = models.CharField(max_length=255)
    content = models.TextField()
    important_notes = models.TextField(blank=True)
    vvip_questions = models.TextField(blank=True)
    image = models.ImageField(upload_to="notes/images/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return (
            f"{self.chapter.subject.school_class.class_name} - "
            f"{self.chapter.subject.subject_name} - "
            f"Chapter {self.chapter.chapter_number} - {self.title}"
        )
