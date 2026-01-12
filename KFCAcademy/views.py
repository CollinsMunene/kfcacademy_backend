import os
import secrets
from django.shortcuts import render
from rest_framework.generics import GenericAPIView 
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_400_BAD_REQUEST, HTTP_201_CREATED, HTTP_204_NO_CONTENT, HTTP_200_OK,HTTP_404_NOT_FOUND,HTTP_401_UNAUTHORIZED)
from rest_framework.permissions import BasePermission, IsAuthenticated, SAFE_METHODS,AllowAny
from rest_framework.generics import GenericAPIView 
from rest_framework_simplejwt.views import TokenViewBase
from django.utils import timezone
from KFCAcademy.serializers import OTPLoginSerializer, TokenObtainLifetimeSerializer, TokenRefreshLifetimeSerializer
from main.signals import set_current_user
from main.models import Main2FALog, ActionLogs
from main.serializers import UserSerializer
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError
from KFCAcademy.tasks import send_email


def generate_otp():
    return str(secrets.randbelow(9000) + 1000) 

class ReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS

class ProtectedAuthView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    filter_backends = []

    def initial(self, request, *args, **kwargs):
        # Set current user for logging
        if hasattr(request, 'user') and request.user.is_authenticated:
            set_current_user(request.user)
        else:
            set_current_user(None)
        super().initial(request, *args, **kwargs)

class FreeAuthView(GenericAPIView):
    # permission_classes = []
    permission_classes = [AllowAny]
    filter_backends = []
    pass


class PublicAuthView(GenericAPIView):
    """
    View that allows both authenticated and unauthenticated access.
    When authenticated, user context is available; when not, request.user will be AnonymousUser
    """
    permission_classes = [AllowAny]
    filter_backends = []

    def initial(self, request, *args, **kwargs):
        # Set current user for logging (if authenticated)
        if hasattr(request, 'user') and request.user.is_authenticated:
            set_current_user(request.user)
        else:
            set_current_user(None)
        super().initial(request, *args, **kwargs)


class PreTokenObtainPairView(FreeAuthView):
    serializer_class = OTPLoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        print("user", user)

        otp = generate_otp()
        obj, created = Main2FALog.objects.update_or_create(
            user=user,
            defaults={
                "otp": otp,
                "status": "Active",
                "reason": "Login OTP",
                "updated_at": timezone.now()
            }
        )

        send_email.delay(
            subject="Sign In OTP Notification - " + otp,
            context={
                "user": f"{user.first_name} {user.last_name}",
                "message1": "Kindly find below your OTP",
                "message2": otp
            },
            template="2fa_email.html",
            to_email=user.email
        )

        return Response({
            "status": "ok",
            "message": "OTP sent",
            "data": []
        }, status=HTTP_200_OK)


class TokenObtainPairView(TokenViewBase):
    """
        Return JWT tokens (access and refresh) for specific user based on username and password.
    """
    serializer_class = TokenObtainLifetimeSerializer
    def post(self, request, *args, **kwargs): 
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except AuthenticationFailed as e:
            return Response({
                "status":"ok",
                "message":"Invalid Email or Password",
                "data":[]
            }, status=HTTP_400_BAD_REQUEST)
        except TokenError as e:
            return Response({
                "status":"ok",
                "message":"Kindly Log out",
                "data":[]
            }, status=HTTP_401_UNAUTHORIZED)
        
        if serializer.validated_data != []:
            user = serializer.validated_data['user']
            log_entry = Main2FALog.objects.filter(
                otp=request.data['otp'],
                user=user,
                status="Active"
            ).first()

            if not log_entry:
                return Response({
                    "status": "Error",
                    "message": "Expired OTP",
                    "data": []
                }, status=HTTP_400_BAD_REQUEST)

            # Update the OTP status to Inactive
            log_entry.status = "Inactive"
            log_entry.save()

            
            ActionLogs.objects.create(
                initiator_id = user,
                action = f'{user.first_name} logged in', 
                extra_details={
                    "ip": request.META.get("HTTP_X_FORWARDED_FOR") or request.META.get("REMOTE_ADDR"),
                    "user_agent": request.META.get("HTTP_USER_AGENT"),
                    "referer": request.META.get("HTTP_REFERER"),
                    "path": request.path,
                    "method": request.method,
                    "query_params": request.GET.dict()
                }
                
            )

            response_data = {
                'access': serializer.validated_data['access'],
                'refresh': serializer.validated_data['refresh'],
                'type':serializer.validated_data['token_type'],
                'expires_at':serializer.validated_data['expires_in'],
                'user': UserSerializer(user).data,
                "message":"Success! Your Dashboard is being prepared."
            }

            return Response(response_data, status=HTTP_200_OK)
        else:
            return Response({
                "status":"ok",
                "message":"Invalid Email or Password",
                "data":[]
            }, status=HTTP_400_BAD_REQUEST)

    
class TokenRefreshView(TokenViewBase):
    serializer_class = TokenRefreshLifetimeSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # user = serializer.validated_data['user']

        response_data = {
            'access': serializer.validated_data['access'],
            'refresh': serializer.validated_data['refresh'],
            'type': serializer.validated_data['token_type'],
            'expires_at': serializer.validated_data['expires_in'],
            # 'user': UserSerializer(user).data if user else None,
        }
        return Response(response_data, status=HTTP_200_OK)