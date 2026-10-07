import csv
import io
import uuid

from django.db import transaction
from django.db.models import Prefetch, Q, TextField
from django.db.models.functions import Cast
from django.utils import timezone

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
    UserProgress,
)

BLOCK_TYPES = {
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
    "bullet",
    "concept",
    "definition",
    "note",
    "question",
    "try",
    "summary",
    "image",
}


def visible_status(user):
    if user and user.is_authenticated and user.is_staff:
        return None
    return "published"


def student_notes(user):
    notes = Note.objects.select_related(
        "chapter",
        "chapter__subject",
        "chapter__subject__school_class",
        "topic",
    )
    status = visible_status(user)
    if status:
        notes = notes.filter(status=status)
    return notes


def student_topics(user):
    topics = Topic.objects.select_related(
        "chapter",
        "chapter__subject",
        "chapter__subject__school_class",
    )
    status = visible_status(user)
    if status:
        topics = topics.filter(status=status)
    return topics


def normalize_block(block, index):
    if not isinstance(block, dict):
        raise ValueError("Every content block must be an object.")
    block_type = str(block.get("type") or "paragraph").strip().lower()
    if block_type not in BLOCK_TYPES:
        raise ValueError(f"Unknown content block type: {block_type}")

    content = block.get("content") or block.get("text") or block.get("body") or ""
    title = block.get("title") or ""
    normalized = {
        "id": str(block.get("id") or uuid.uuid4()),
        "type": block_type,
        "order": block.get("order", index),
    }
    if title:
        normalized["title"] = title

    if block_type == "formula":
        normalized["latex"] = block.get("latex") or content
        normalized["secondaryLatex"] = block.get("secondaryLatex") or block.get("secondary") or ""
    elif block_type == "example":
        normalized["title"] = title or "Example"
        normalized["body"] = block.get("body") or content
        normalized["formula"] = block.get("formula") or ""
    elif block_type in {"list", "bullet", "numbered"}:
        items = block.get("items")
        if not items and content:
            items = [line.strip("- ").strip() for line in str(content).splitlines() if line.strip()]
        normalized["items"] = items or [""]
    elif block_type == "table":
        normalized["headers"] = block.get("headers") or ["Column 1", "Column 2"]
        normalized["rows"] = block.get("rows") or [["", ""]]
    elif block_type in {"image", "diagram"}:
        normalized["text"] = block.get("text") or block.get("caption") or ""
        normalized["url"] = block.get("url") or block.get("src") or ""
        if content and not normalized["text"]:
            normalized["text"] = content
    elif block_type == "html":
        normalized["html"] = block.get("html") or content
    else:
        normalized["text"] = block.get("text") or content
        if block.get("answer"):
            normalized["answer"] = block.get("answer")
        if block.get("difficulty"):
            normalized["difficulty"] = block.get("difficulty")
    return normalized


def _next_chapter_number(subject):
    last = subject.chapters.order_by("-chapter_number").values_list("chapter_number", flat=True).first()
    return (last or 0) + 1


@transaction.atomic
def import_structured_note(payload):
    class_name = (payload.get("class_name") or payload.get("class") or "Class 9").strip()
    medium = (payload.get("medium") or "English").strip() or "English"
    subject_name = (payload.get("subject") or "").strip()
    chapter_name = (payload.get("chapter") or "").strip()
    topic_title = (payload.get("topic") or "").strip()
    status = payload.get("status") or "published"
    if status not in {"draft", "published", "archived"}:
        raise ValueError("Status must be draft, published, or archived.")
    if not subject_name or not chapter_name or not topic_title:
        raise ValueError("subject, chapter, and topic are required.")

    school_class, _created = SchoolClass.objects.get_or_create(
        class_name=class_name,
        defaults={"title": class_name, "medium": medium, "description": ""},
    )
    subject, _created = Subject.objects.get_or_create(
        school_class=school_class,
        subject_name=subject_name,
        defaults={"title": subject_name, "description": payload.get("subject_description") or ""},
    )
    chapter = subject.chapters.filter(chapter_name__iexact=chapter_name).first()
    if chapter is None:
        chapter = Chapter.objects.create(
            subject=subject,
            chapter_name=chapter_name,
            chapter_number=_next_chapter_number(subject),
            title=chapter_name,
            description=payload.get("chapter_description") or "",
        )

    topic, _created = Topic.objects.get_or_create(
        chapter=chapter,
        title=topic_title,
        defaults={
            "description": payload.get("description") or payload.get("topic_description") or "",
            "status": status,
            "sort_order": chapter.topics.count(),
        },
    )
    if topic.status != status or (payload.get("description") and topic.description != payload.get("description")):
        topic.status = status
        if payload.get("description"):
            topic.description = payload.get("description")
        topic.save(update_fields=["status", "description", "updated_at"])

    raw_blocks = payload.get("blocks") or payload.get("content_blocks") or []
    if not isinstance(raw_blocks, list):
        raise ValueError("blocks must be a list.")
    blocks = [normalize_block(block, index) for index, block in enumerate(raw_blocks)]
    blocks.sort(key=lambda block: block.get("order", 0))

    note = topic.notes.order_by("sort_order", "created_at").first()
    description = payload.get("description") or ""
    if note is None:
        note = Note.objects.create(
            chapter=chapter,
            topic=topic,
            title=topic_title,
            description=description,
            content=payload.get("content") or description or topic_title,
            content_blocks=blocks,
            status=status,
            sort_order=0,
        )
    else:
        note.title = topic_title
        note.description = description or note.description
        note.content_blocks = blocks
        note.status = status
        note.chapter = chapter
        if payload.get("content"):
            note.content = payload.get("content")
        note.save()

    return {
        "school_class": school_class,
        "subject": subject,
        "chapter": chapter,
        "topic": topic,
        "note": note,
    }


def question_rows_from_upload(upload):
    name = (upload.name or "").lower()
    raw = upload.read()
    if name.endswith(".xlsx"):
        try:
            import openpyxl
        except ImportError as exc:
            raise ValueError("Excel upload needs openpyxl. Use CSV or install openpyxl.") from exc
        workbook = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        sheet = workbook.active
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            return []
        headers = [str(cell or "").strip().lower() for cell in rows[0]]
        parsed = []
        for row in rows[1:]:
            parsed.append({headers[index]: row[index] for index in range(min(len(headers), len(row)))})
        return parsed

    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    return list(reader)


@transaction.atomic
def import_practice_questions(upload, chapter, topic=None, status="published"):
    created = []
    for index, row in enumerate(question_rows_from_upload(upload)):
        normalized = {str(key or "").strip().lower(): value for key, value in row.items()}
        prompt = normalized.get("question") or normalized.get("prompt") or ""
        prompt = str(prompt or "").strip()
        if not prompt:
            continue
        difficulty = str(normalized.get("difficulty") or "medium").strip().lower()
        if difficulty not in {"easy", "medium", "hard"}:
            difficulty = "medium"
        options, correct = objective_options(normalized)
        created.append(
            PracticeQuestion.objects.create(
                chapter=chapter,
                topic=topic,
                prompt=prompt,
                option_a=options["A"],
                option_b=options["B"],
                option_c=options["C"],
                option_d=options["D"],
                correct_option=correct,
                answer=str(normalized.get("answer") or "").strip(),
                explanation=str(normalized.get("explanation") or "").strip(),
                difficulty=difficulty,
                sort_order=index,
                status=status if status in {"draft", "published", "archived"} else "published",
            )
        )
    if not created:
        raise ValueError(
            "No questions were found. Use columns question, option_a, option_b, option_c, option_d, correct."
        )
    return created


def objective_options(row):
    options = {
        "A": str(row.get("option_a") or row.get("a") or "").strip(),
        "B": str(row.get("option_b") or row.get("b") or "").strip(),
        "C": str(row.get("option_c") or row.get("c") or "").strip(),
        "D": str(row.get("option_d") or row.get("d") or "").strip(),
    }
    correct = str(row.get("correct") or row.get("correct_option") or "").strip().upper()
    if correct in {"1", "2", "3", "4"}:
        correct = "ABCD"[int(correct) - 1]
    if correct not in options:
        correct = ""
    return options, correct


def objective_questions(chapter, user):
    questions = chapter.practice_questions.exclude(option_a="").exclude(option_b="").exclude(
        option_c=""
    ).exclude(option_d="")
    status = visible_status(user)
    if status:
        questions = questions.filter(status=status)
    return questions.order_by("sort_order", "created_at")


def public_objective_question(question):
    return {
        "uuid": str(question.uuid),
        "prompt": question.prompt,
        "options": [
            {"key": "A", "text": question.option_a},
            {"key": "B", "text": question.option_b},
            {"key": "C", "text": question.option_c},
            {"key": "D", "text": question.option_d},
        ],
    }


def managed_question(question, include_answer=False):
    payload = {
        "uuid": str(question.uuid),
        "prompt": question.prompt,
        "option_a": question.option_a,
        "option_b": question.option_b,
        "option_c": question.option_c,
        "option_d": question.option_d,
        "difficulty": question.difficulty,
        "subject_name": question.chapter.subject.subject_name,
        "subject_uuid": str(question.chapter.subject.uuid),
        "chapter_uuid": str(question.chapter.uuid),
        "topic_uuid": str(question.topic.uuid) if question.topic_id else None,
        "topic_title": question.topic.title if question.topic_id else question.chapter.chapter_name,
    }
    if include_answer:
        payload["correct_option"] = question.correct_option
        payload["answer"] = question.answer
        payload["explanation"] = question.explanation
    return payload


def outline_for_subject(subject, user):
    status = visible_status(user)
    topics = Topic.objects.all().order_by("sort_order", "title")
    loose_notes = Note.objects.filter(topic__isnull=True).order_by("sort_order", "created_at")
    if status:
        topics = topics.filter(status=status)
        loose_notes = loose_notes.filter(status=status)
    chapters = (
        subject.chapters.all()
        .order_by("chapter_number")
        .prefetch_related(
            Prefetch("topics", queryset=topics),
            Prefetch("notes", queryset=loose_notes),
        )
    )
    payload = []
    for chapter in chapters:
        items = [
            {
                "uuid": str(topic.uuid),
                "title": topic.title,
                "description": topic.description,
                "kind": "topic",
                "status": topic.status,
            }
            for topic in chapter.topics.all()
        ]
        items.extend(
            {
                "uuid": str(note.uuid),
                "title": note.title,
                "description": note.description,
                "kind": "note",
                "status": note.status,
            }
            for note in chapter.notes.all()
        )
        payload.append(
            {
                "uuid": str(chapter.uuid),
                "chapter_name": chapter.chapter_name,
                "chapter_number": chapter.chapter_number,
                "title": chapter.title,
                "description": chapter.description,
                "topics": items,
            }
        )
    return payload


def _trail(subject_name, chapter_name, topic_title):
    parts = [part for part in (subject_name, chapter_name, topic_title) if part]
    return " > ".join(parts)


def search_catalog(query, user, limit=8):
    needle = (query or "").strip()
    if len(needle) < 2:
        raise ValueError("Enter at least 2 characters.")

    status = visible_status(user)
    subjects = Subject.objects.select_related("school_class").filter(
        Q(subject_name__icontains=needle) | Q(title__icontains=needle) | Q(description__icontains=needle)
    )[:limit]
    chapters = Chapter.objects.select_related("subject", "subject__school_class").filter(
        Q(chapter_name__icontains=needle) | Q(title__icontains=needle) | Q(description__icontains=needle)
    )[:limit]
    topics = student_topics(user).filter(
        Q(title__icontains=needle) | Q(description__icontains=needle)
    )[:limit]
    notes = student_notes(user).annotate(blocks_text=Cast("content_blocks", TextField())).filter(
        Q(title__icontains=needle)
        | Q(description__icontains=needle)
        | Q(content__icontains=needle)
        | Q(blocks_text__icontains=needle)
    )[: limit * 3]

    results = []
    for subject in subjects:
        results.append(
            {
                "type": "subject",
                "title": subject.subject_name,
                "trail": subject.school_class.class_name,
                "subject_uuid": str(subject.uuid),
                "school_class_uuid": str(subject.school_class.uuid),
            }
        )
    for chapter in chapters:
        results.append(
            {
                "type": "chapter",
                "title": chapter.chapter_name,
                "trail": _trail(chapter.subject.subject_name, None, None),
                "subject_uuid": str(chapter.subject.uuid),
                "chapter_uuid": str(chapter.uuid),
                "school_class_uuid": str(chapter.subject.school_class.uuid),
            }
        )
    for topic in topics:
        results.append(
            {
                "type": "topic",
                "title": topic.title,
                "trail": _trail(topic.chapter.subject.subject_name, topic.chapter.chapter_name, None),
                "subject_uuid": str(topic.chapter.subject.uuid),
                "chapter_uuid": str(topic.chapter.uuid),
                "topic_uuid": str(topic.uuid),
                "kind": "topic",
            }
        )
    for note in notes:
        chapter = note.chapter
        subject = chapter.subject
        formula_hit = _formula_match(note, needle)
        results.append(
            {
                "type": "formula" if formula_hit else "note",
                "title": formula_hit or note.title,
                "trail": _trail(subject.subject_name, chapter.chapter_name, note.topic.title if note.topic_id else note.title),
                "subject_uuid": str(subject.uuid),
                "chapter_uuid": str(chapter.uuid),
                "topic_uuid": str(note.topic.uuid) if note.topic_id else str(note.uuid),
                "kind": "topic" if note.topic_id else "note",
                "note_uuid": str(note.uuid),
            }
        )
    return results[: limit * 4]


def _formula_match(note, needle):
    blocks = note.content_blocks if isinstance(note.content_blocks, list) else []
    lowered = needle.lower()
    for block in blocks:
        if not isinstance(block, dict) or block.get("type") != "formula":
            continue
        haystack = " ".join(
            str(block.get(key) or "")
            for key in ("title", "latex", "content", "secondaryLatex")
        )
        if lowered in haystack.lower():
            return block.get("title") or block.get("latex") or note.title
    return None


def collect_formulas(user, subject_uuid=None, school_class_uuid=None, limit=20):
    notes = student_notes(user).order_by("-updated_at")
    if subject_uuid:
        notes = notes.filter(chapter__subject__uuid=subject_uuid)
    if school_class_uuid:
        notes = notes.filter(chapter__subject__school_class__uuid=school_class_uuid)
    formulas = []
    for note in notes[:200]:
        blocks = note.content_blocks if isinstance(note.content_blocks, list) else []
        for block in blocks:
            if not isinstance(block, dict) or block.get("type") != "formula":
                continue
            chapter = note.chapter
            formulas.append(
                {
                    "id": block.get("id"),
                    "title": block.get("title") or "Formula",
                    "latex": block.get("latex") or block.get("content") or "",
                    "secondary_latex": block.get("secondaryLatex") or "",
                    "topic_title": note.topic.title if note.topic_id else note.title,
                    "topic_uuid": str(note.topic.uuid) if note.topic_id else str(note.uuid),
                    "kind": "topic" if note.topic_id else "note",
                    "subject_name": chapter.subject.subject_name,
                    "subject_uuid": str(chapter.subject.uuid),
                    "chapter_name": chapter.chapter_name,
                }
            )
            if len(formulas) >= limit:
                return formulas
    return formulas


def _target_counts(subject, user):
    status = visible_status(user)
    topics = Topic.objects.filter(chapter__subject=subject)
    notes = Note.objects.filter(chapter__subject=subject, topic__isnull=True)
    if status:
        topics = topics.filter(status=status)
        notes = notes.filter(status=status)
    return topics, notes


def progress_summary(user, school_class=None):
    goal, _created = StudyGoal.objects.get_or_create(user=user)
    today = timezone.localdate()
    completed_today = user.study_progress.filter(completed=True, completed_at__date=today).count()
    subjects = Subject.objects.select_related("school_class").all()
    if school_class is not None:
        subjects = subjects.filter(school_class=school_class)

    completed_topic_ids = set(
        user.study_progress.filter(completed=True, topic__isnull=False).values_list("topic_id", flat=True)
    )
    completed_note_ids = set(
        user.study_progress.filter(completed=True, note__isnull=False).values_list("note_id", flat=True)
    )
    subject_rows = []
    overall_done = 0
    overall_total = 0
    for subject in subjects:
        topics, notes = _target_counts(subject, user)
        topic_ids = list(topics.values_list("id", flat=True))
        note_ids = list(notes.values_list("id", flat=True))
        done = len(set(topic_ids) & completed_topic_ids) + len(set(note_ids) & completed_note_ids)
        total = len(topic_ids) + len(note_ids)
        overall_done += done
        overall_total += total
        subject_rows.append(
            {
                "uuid": str(subject.uuid),
                "subject_name": subject.subject_name,
                "title": subject.title,
                "icon": subject.icon,
                "chapter_count": subject.chapters.count(),
                "completed": done,
                "total": total,
                "percent": round((done / total) * 100) if total else 0,
            }
        )

    recent = []
    continue_topic = None
    rows = (
        user.study_progress.select_related(
            "topic__chapter__subject",
            "note__chapter__subject",
            "note__topic",
        )
        .order_by("-viewed_at")[:8]
    )
    for row in rows:
        item = _progress_item(row)
        if item is None:
            continue
        recent.append(item)
        if continue_topic is None and not row.completed:
            continue_topic = item
    if continue_topic is None and recent:
        continue_topic = recent[0]

    recommended = []
    if school_class is not None:
        candidates = student_topics(user).filter(chapter__subject__school_class=school_class).exclude(
            id__in=completed_topic_ids
        )[:4]
        for topic in candidates:
            recommended.append(
                {
                    "title": topic.title,
                    "kind": "topic",
                    "uuid": str(topic.uuid),
                    "subject_name": topic.chapter.subject.subject_name,
                    "subject_uuid": str(topic.chapter.subject.uuid),
                    "chapter_name": topic.chapter.chapter_name,
                }
            )

    upcoming = ScheduledTest.objects.select_related("subject").filter(
        status="published",
        scheduled_on__gte=today,
    )
    if school_class is not None:
        upcoming = upcoming.filter(subject__school_class=school_class)

    return {
        "daily_goal": goal.daily_target,
        "completed_today": completed_today,
        "overall": {
            "completed": overall_done,
            "total": overall_total,
            "percent": round((overall_done / overall_total) * 100) if overall_total else 0,
        },
        "subjects": subject_rows,
        "continue_topic": continue_topic,
        "recent": recent[:5],
        "recommended": recommended,
        "upcoming_tests": [
            {
                "uuid": str(item.uuid),
                "title": item.title,
                "description": item.description,
                "scheduled_on": item.scheduled_on.isoformat(),
                "subject_name": item.subject.subject_name,
                "subject_uuid": str(item.subject.uuid),
            }
            for item in upcoming[:5]
        ],
    }


def _progress_item(row):
    if row.topic_id:
        topic = row.topic
        return {
            "uuid": str(topic.uuid),
            "kind": "topic",
            "title": topic.title,
            "completed": row.completed,
            "viewed_at": row.viewed_at.isoformat(),
            "subject_name": topic.chapter.subject.subject_name,
            "subject_uuid": str(topic.chapter.subject.uuid),
            "chapter_name": topic.chapter.chapter_name,
        }
    if row.note_id:
        note = row.note
        return {
            "uuid": str(note.uuid),
            "kind": "note",
            "title": note.title,
            "completed": row.completed,
            "viewed_at": row.viewed_at.isoformat(),
            "subject_name": note.chapter.subject.subject_name,
            "subject_uuid": str(note.chapter.subject.uuid),
            "chapter_name": note.chapter.chapter_name,
        }
    return None


def mark_progress(user, topic=None, note=None, completed=None):
    if topic is None and note is None:
        raise ValueError("topic or note is required.")
    lookup = {"user": user}
    if topic is not None:
        lookup["topic"] = topic
    else:
        lookup["note"] = note
    row, _created = UserProgress.objects.get_or_create(**lookup)
    if completed is not None:
        row.completed = bool(completed)
        row.completed_at = timezone.now() if row.completed else None
    row.save()
    return row


def reading_target(uuid_value):
    topic = Topic.objects.filter(uuid=uuid_value).select_related(
        "chapter__subject__school_class"
    ).first()
    if topic:
        return topic, None
    note = Note.objects.filter(uuid=uuid_value).select_related(
        "chapter__subject__school_class",
        "topic",
    ).first()
    return None, note


def reorder_blocks(note, block_ids):
    blocks = note.content_blocks
    if not isinstance(blocks, list):
        raise ValueError("Only list-style content blocks can be reordered.")
    by_id = {str(block.get("id")): block for block in blocks if isinstance(block, dict)}
    ordered = []
    for block_id in block_ids:
        block = by_id.pop(str(block_id), None)
        if block is not None:
            ordered.append(block)
    ordered.extend(by_id.values())
    for index, block in enumerate(ordered):
        block["order"] = index
    note.content_blocks = ordered
    note.save(update_fields=["content_blocks", "updated_at"])
    return note


def bookmark_payload(bookmark):
    return {
        "uuid": str(bookmark.uuid),
        "target_type": bookmark.target_type,
        "target_id": bookmark.target_id,
        "title": bookmark.title,
        "subtitle": bookmark.subtitle,
        "context": bookmark.context or {},
        "created_at": bookmark.created_at.isoformat(),
    }


def user_bookmarks(user):
    return [bookmark_payload(item) for item in Bookmark.objects.filter(user=user)]
