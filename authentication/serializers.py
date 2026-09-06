from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(
        required=True,
        max_length=25,
        validators=[],
    )

    class Meta:
        model = User
        fields = [
            "email",
            "phone_number",
            "password",
        ]

        extra_kwargs = {
            "email": {
                "required": True,
                "validators": [],
            },
            "phone_number": {
                "required": True,
                "validators": [],
            },
            "password": {
                "write_only": True
            }
        }

    def validate_phone_number(self, value):
        phone_number = "".join(character for character in value if character.isdigit())
        if not 10 <= len(phone_number) <= 15:
            raise serializers.ValidationError(
                "Phone number must contain 10 to 15 digits."
            )
        return phone_number

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)