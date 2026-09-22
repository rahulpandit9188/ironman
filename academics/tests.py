from django.contrib.auth import get_user_model
from django.http import QueryDict
from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.test import APITestCase

from .models import SchoolClass
from .serializers import NoteSerializer


class NoteContentBlocksTests(SimpleTestCase):
    def test_multipart_json_blocks_are_parsed(self):
        data = QueryDict("", mutable=True)
        data["content_blocks"] = (
            '[{"type":"paragraph","text":"Electric potential"}]'
        )
        field = NoteSerializer().fields["content_blocks"]

        value = field.run_validation(field.get_value(data))

        self.assertEqual(value[0]["type"], "paragraph")

    def test_unknown_block_type_is_rejected(self):
        serializer = NoteSerializer()

        with self.assertRaisesMessage(ValidationError, "Unknown content block type"):
            serializer.validate_content_blocks([{"type": "unknown"}])

    def test_rich_editor_document_is_accepted(self):
        serializer = NoteSerializer()
        document = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Electric potential"}],
                }
            ],
        }

        self.assertEqual(serializer.validate_content_blocks(document), document)


class BulkCreateApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="staff@example.com",
            password="test-password",
            is_staff=True,
        )
        self.client.force_authenticate(self.user)

    def test_staff_can_create_multiple_classes(self):
        response = self.client.post(
            reverse("class-bulk-create"),
            [
                {
                    "class_name": "Class 9",
                    "title": "Class 9",
                    "medium": "English",
                },
                {
                    "class_name": "Class 10",
                    "title": "Class 10",
                    "medium": "English",
                },
            ],
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(SchoolClass.objects.count(), 2)

    def test_bulk_create_rejects_non_array_payload(self):
        response = self.client.post(
            reverse("class-bulk-create"),
            {"class_name": "Class 9"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(SchoolClass.objects.count(), 0)
