from rest_framework import serializers

from .models import Chapter, Note, SchoolClass, Subject


class SchoolClassSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchoolClass
        fields = [
            "id",
            "uuid",
            "class_name",
            "title",
            "description",
            "medium",
        ]
        read_only_fields = ["id", "uuid"]


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = [
            "id",
            "uuid",
            "school_class",
            "subject_name",
            "title",
            "description",
        ]
        read_only_fields = ["id", "uuid"]


class ChapterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chapter
        fields = [
            "id",
            "uuid",
            "subject",
            "chapter_name",
            "chapter_number",
            "title",
            "description",
        ]
        read_only_fields = ["id", "uuid"]


class NoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note
        fields = [
            "id",
            "uuid",
            "chapter",
            "title",
            "content",
            "important_notes",
            "vvip_questions",
            "image",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "uuid", "created_at", "updated_at"]
