from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken

from .models import User
from .serializers import LoginSerializer, UserSerializer


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = UserSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        phone_number = serializer.validated_data.get("phone_number")

        if User.objects.filter(email=email).exists():
            return Response(
                {"detail": "This email already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if phone_number and User.objects.filter(phone_number=phone_number).exists():
            return Response(
                {"detail": "This phone number already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = serializer.save()
        return Response(
            {
                "message": "User registered successfully",
                "data": {
                    "email": user.email,
                    "phone_number": user.phone_number,
                }
            },
            status=status.HTTP_201_CREATED
        )

class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]
        user = User.objects.filter(email=email).first()
        if user is None:
            return Response(
                {"detail": "User not found"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if not user.check_password(password):
            return Response(
                {"detail": "Invalid password"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        refresh = RefreshToken.for_user(user)
        access = AccessToken.for_user(user)
        return Response(
            {
                "message": "Login successful",
                "data": {
                    "email": user.email,
                    "phone_number": user.phone_number,
                    "is_staff": user.is_staff,
                    "refresh": str(refresh),
                    "access": str(access),
                },
            },
            status=status.HTTP_200_OK,
        )

class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response(
                    {"detail": "Refresh token is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                RefreshToken(refresh_token).blacklist()
                return Response(
                    {"detail": "Logout successful"},
                    status=status.HTTP_200_OK,
                )
            except Exception as e:
                return Response(
                    {"detail": "Invalid refresh token"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )