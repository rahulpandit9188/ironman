from django.contrib import admin

from .models import Chapter, Note, SchoolClass, Subject


@admin.register(SchoolClass)
class SchoolClassAdmin(admin.ModelAdmin):
    list_display = ("class_name", "title", "medium")
    search_fields = ("class_name", "title", "medium")
    list_filter = ("medium",)
    ordering = ("class_name",)
    readonly_fields = ("uuid",)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("subject_name", "school_class", "title")
    search_fields = (
        "subject_name",
        "title",
        "school_class__class_name",
    )
    list_filter = ("school_class",)
    autocomplete_fields = ("school_class",)
    list_select_related = ("school_class",)
    readonly_fields = ("uuid",)


@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ("chapter_number", "chapter_name", "subject", "school_class")
    search_fields = (
        "chapter_name",
        "title",
        "subject__subject_name",
        "subject__school_class__class_name",
    )
    list_filter = ("subject__school_class", "subject")
    autocomplete_fields = ("subject",)
    list_select_related = ("subject", "subject__school_class")
    readonly_fields = ("uuid",)
    ordering = ("subject", "chapter_number")

    @admin.display(description="Class", ordering="subject__school_class__class_name")
    def school_class(self, obj):
        return obj.subject.school_class


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("title", "chapter", "subject", "school_class", "updated_at")
    search_fields = (
        "title",
        "content",
        "chapter__chapter_name",
        "chapter__subject__subject_name",
        "chapter__subject__school_class__class_name",
    )
    list_filter = ("chapter__subject__school_class", "chapter__subject")
    autocomplete_fields = ("chapter",)
    list_select_related = (
        "chapter",
        "chapter__subject",
        "chapter__subject__school_class",
    )
    readonly_fields = ("uuid", "created_at", "updated_at")

    @admin.display(description="Subject", ordering="chapter__subject__subject_name")
    def subject(self, obj):
        return obj.chapter.subject

    @admin.display(
        description="Class",
        ordering="chapter__subject__school_class__class_name",
    )
    def school_class(self, obj):
        return obj.chapter.subject.school_class
