from pathlib import Path

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
    school_class = serializers.SlugRelatedField(
        slug_field="uuid",
        queryset=SchoolClass.objects.all(),
    )

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
    subject = serializers.SlugRelatedField(
        slug_field="uuid",
        queryset=Subject.objects.all(),
    )

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
    allowed_block_types = {
        "heading",
        "paragraph",
        "formula",
        "example",
        "diagram",
        "list",
        "numbered",
        "table",
        "tip",
        "html",
    }

    chapter = serializers.SlugRelatedField(
        slug_field="uuid",
        queryset=Chapter.objects.all(),
    )

    class Meta:
        model = Note
        fields = [
            "id",
            "uuid",
            "chapter",
            "title",
            "content",
            "content_blocks",
            "important_notes",
            "vvip_questions",
            "image",
            "source_file",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "uuid", "created_at", "updated_at"]

    def validate_source_file(self, source_file):
        allowed_extensions = {".txt", ".md", ".png", ".jpg", ".jpeg", ".webp"}
        extension = Path(source_file.name).suffix.lower()
        if extension not in allowed_extensions:
            raise serializers.ValidationError(
                "Only TXT, MD, PNG, JPG, JPEG, or WEBP files are allowed."
            )
        if source_file.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("Source file must be 10 MB or smaller.")
        return source_file

    def validate_content_blocks(self, blocks):
        if isinstance(blocks, dict):
            if blocks.get("type") != "doc" or not isinstance(blocks.get("content", []), list):
                raise serializers.ValidationError("Invalid editor document.")
            return blocks
        if not isinstance(blocks, list):
            raise serializers.ValidationError(
                "Content blocks must be an editor document or a legacy block list."
            )
        if len(blocks) > 200:
            raise serializers.ValidationError("A note can contain at most 200 blocks.")
        for block in blocks:
            if not isinstance(block, dict):
                raise serializers.ValidationError("Every content block must be an object.")
            if block.get("type") not in self.allowed_block_types:
                raise serializers.ValidationError("Unknown content block type.")
        return blocks
