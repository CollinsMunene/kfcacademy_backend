# from datetime import datetime, timezone
import os
import random
from django.shortcuts import get_object_or_404, render
from django.core.files.uploadedfile import InMemoryUploadedFile
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_400_BAD_REQUEST, HTTP_201_CREATED, HTTP_204_NO_CONTENT, HTTP_200_OK,HTTP_404_NOT_FOUND,HTTP_401_UNAUTHORIZED,HTTP_403_FORBIDDEN)
from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image,ImageDraw, ImageFont
from django.conf import settings
from PIL import ImageColor
from uuid import UUID
from io import BytesIO
from KFCAcademy.settings import BASE_DIR, STATIC_URL
from KFCAcademy.tasks import send_email
from KFCAcademy.views import FreeAuthView, ProtectedAuthView, PublicAuthView
from main.models import (
    ActionLogs, Main2FALog, Permission, Role, Users, Courses, CourseModules, 
    ModuleTopics, ModuleQuizes, QuizQuestions, QuizResponses, CourseDiscussions,
    UsersCourseEnrollment, UserModuleProgress, QuizSubmissionFeedback
)
from main.serializers import (
    ActionLogsSerializer, Main2FASerializer, PermissionsSerializer, 
    RoleSerializer, UserSerializer, CourseSerializer, CourseModuleSerializer,
    QuizQuestionsSerializer, ModuleTopicSerializer, ModuleQuizSerializer,
    QuizResponseSerializer, CourseEnrollmentSerializer, UserProgressSerializer,
    PublicCourseSerializer, CourseDiscussionSerializer, TopicCompletionSerializer,
    EnrolledCourseSerializer, UnenrollmentSerializer, QuizSubmissionFeedbackSerializer
)
from main.signals import log_soft_delete
from rest_framework.parsers import MultiPartParser, FormParser


# Create your views here.

class AllUsers(ProtectedAuthView):
    serializer_class = UserSerializer
    filter_backends = []
    def get(self,request,format=None):
        """
        Get all users
        """
        all_users = Users.objects.filter(deleted_at__isnull=True)
        serializer = UserSerializer(all_users,many=True)
        return Response(serializer.data,status=HTTP_200_OK)

class OneUser(ProtectedAuthView):
    serializer_class = UserSerializer
    
    def get(self,request,guid,format=None):
        """
        Get one User
        """
        one_user = get_object_or_404(Users,guid=guid,deleted_at__isnull=True)
        serializer = UserSerializer(one_user)
        return Response(serializer.data,status=HTTP_200_OK)
    
class CurrentUser(ProtectedAuthView):
    serializer_class = UserSerializer
    def get(self,request,format=None):
        """
        Get one User
        """
        if request.user.is_authenticated:
            serializer = UserSerializer(request.user)
            response_data = {
                'access': str(request.auth),
                'type':'Bearer',
                'user': serializer.data,
                "message":""
            }
            return Response(response_data,status=HTTP_200_OK)
        else:
            return Response({
                    "status": "ok",
                    "message": f"An error occurred",
                    "data": f"An error occurred"
                }, status=HTTP_400_BAD_REQUEST)

       
class UserRegister(FreeAuthView):
    serializer_class = UserSerializer

    def post(self, request, format=None):
        try:
            email = request.data.get('email')
            if Users.objects.filter(email=email).exists():
                return Response({
                    "status": "ok",
                    "message": "User with the email already exists",
                    "data": "User with the email already exists"
                }, status=HTTP_400_BAD_REQUEST)


            # Username & password generation
            username = f"{request.data['first_name']}_{request.data['last_name']}{random.randint(1000, 9999)}"
            request.data['username'] = username
            initial_password = ";4yGcR56O{|1"
            print(initial_password)
            request.data['password'] = initial_password
            request.data['is_first_time_login'] = True

            serializer = UserSerializer(data=request.data)
            if serializer.is_valid():
                user = serializer.save(created_by="self", username=username)

                # Generate profile image
                user_initials = request.data['first_name'][0] + request.data['last_name'][0]
                image = self.create_profile_image(user_initials)
                img_name = f"{user_initials}.jpg"
                user.image.save(img_name, InMemoryUploadedFile(
                    image,
                    None,
                    img_name,
                    'image/jpeg',
                    image.tell,
                    None
                ))

                # if user.role_id not in [2, 4]: 
                # Email message
                message1 = f"You have been added to the FPC Academy Platform."
                message2 = "Your initial login credentials are as below. You will be required to change this on login."
                message3 = "Welcome to the team."
                link = 'https://fpc.academy/login'

                send_email.delay(
                    subject=f"Congratulations! Welcome to FPC Academy Platform",
                    context={
                        "user": request.data.get('first_name'),
                        "org": "FPC Academy",
                        "message1": message1,
                        "message2": message2,
                        "message3": message3,
                        "username": request.data.get('email'),
                        "password": initial_password,
                        "link": link
                    },
                    template='welcome_email.html',
                    to_email=request.data.get('email')
                )

                return Response({
                    "status": "ok",
                    "message": "Account Created Successfully",
                    "data": "Account Created Successfully"
                }, status=HTTP_200_OK)

            return Response({
                "status": "Failed",
                "message": "Account not created",
                "data": serializer.errors
            }, status=HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Account not created",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)

    def create_profile_image(self, user_initials):
        N = 500
        img = Image.new('RGB', (N, N), color=(255, 255, 255))

        font_path = os.path.join(BASE_DIR, "KFCAcademy/" + STATIC_URL + 'MontserratBlack.ttf')
        font = ImageFont.truetype(font_path, 350)

        draw = ImageDraw.Draw(img)
        _, _, text_width, text_height = draw.textbbox((0, 0), text=user_initials, font=font)
        x = (N - text_width) / 2
        y = (N - text_height) / 2
        draw.text((x, y), user_initials, font=font, fill=(116, 27, 71))

        buffer = BytesIO()
        img.save(fp=buffer, format='JPEG')
        return ContentFile(buffer.getvalue())
    
class AdminCreateUser(ProtectedAuthView):
    serializer_class = UserSerializer

    def post(self, request, format=None):
        try:
            email = request.data.get('email')
            if Users.objects.filter(email=email).exists():
                return Response({
                    "status": "ok",
                    "message": "User with the email already exists",
                    "data": "User with the email already exists"
                }, status=HTTP_400_BAD_REQUEST)

            # Validate role_guid if provided
            role_guid = request.data.get('role')
            if role_guid:
                try:
                    role = Role.objects.get(guid=role_guid, deleted_at__isnull=True)
                except Role.DoesNotExist:
                    return Response({
                        "status": "Failed",
                        "message": "Invalid role provided",
                        "data": "Role with the provided GUID does not exist"
                    }, status=HTTP_400_BAD_REQUEST)

            # Username & password generation
            username = f"{request.data['first_name']}_{request.data['last_name']}{random.randint(1000, 9999)}"
            request.data['username'] = username
            initial_password = ";4yGcR56O{|1"
            request.data['password'] = initial_password
            request.data['is_first_time_login'] = True

            serializer = UserSerializer(data=request.data)
            if serializer.is_valid():
                user = serializer.save(created_by=request.user.guid, username=username)

                # Generate profile image
                user_initials = request.data['first_name'][0] + request.data['last_name'][0]
                image = self.create_profile_image(user_initials)
                img_name = f"{user_initials}.jpg"
                user.image.save(img_name, InMemoryUploadedFile(
                    image,
                    None,
                    img_name,
                    'image/jpeg',
                    image.tell,
                    None
                ))

                # if user.role_id not in [2, 4]: 
                # Email message
                message1 = f"You have been added to the FPC Academy Platform."
                message2 = "Your initial login credentials are as below. You will be required to change this on login."
                message3 = "Welcome to the team."
                link = 'https://fpc.academy/login'

                send_email.delay(
                    subject=f"Congratulations! Welcome to FPC Academy Platform",
                    context={
                        "user": request.data.get('first_name'),
                        "org": "FPC Academy",
                        "message1": message1,
                        "message2": message2,
                        "message3": message3,
                        "username": request.data.get('email'),
                        "password": initial_password,
                        "link": link
                    },
                    template='welcome_email.html',
                    to_email=request.data.get('email')
                )

                return Response({
                    "status": "ok",
                    "message": "Account Created Successfully",
                    "data": "Account Created Successfully"
                }, status=HTTP_200_OK)

            return Response({
                "status": "Failed",
                "message": "Account not created",
                "data": serializer.errors
            }, status=HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Account not created",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)

    def create_profile_image(self, user_initials):
        N = 500
        img = Image.new('RGB', (N, N), color=(255, 255, 255))

        font_path = os.path.join(BASE_DIR, "KFCAcademy/" + STATIC_URL + 'MontserratBlack.ttf')
        font = ImageFont.truetype(font_path, 350)

        draw = ImageDraw.Draw(img)
        _, _, text_width, text_height = draw.textbbox((0, 0), text=user_initials, font=font)
        x = (N - text_width) / 2
        y = (N - text_height) / 2
        draw.text((x, y), user_initials, font=font, fill=(116, 27, 71))

        buffer = BytesIO()
        img.save(fp=buffer, format='JPEG')
        return ContentFile(buffer.getvalue())


class AdminReactivateUser(ProtectedAuthView):
    serializer_class = UserSerializer
    def post(self, request, format=None):
        """
        Reactivate User
        """
        try:
            user_guid = request.data.get('user_guid')
            user = Users.objects.get(guid=user_guid)
            if user.is_active:
                return Response({
                    "status": "ok",
                    "message": "User is already active",
                    "data": "User is already active"
                }, status=HTTP_400_BAD_REQUEST)
            
            initial_password = ";4yGcR56O{|1"
            user.password = initial_password
            user.is_first_time_login = True

            user.is_active = True
            user.updated_by = request.user.guid
            user.save()

            send_email.delay(
                subject="Your FPC Academy Account has been Reactivated",
                context={
                    "user": user.first_name,
                    "message1": "Your account on the FPC Academy Platform has been Activated.",
                    "message2": "If you did not request this, please contact support immediately.",
                    "message3": "Welcome back to the team.",
                    "username": user.email,
                    "password": initial_password,
                    "link": 'https://fpc.com/login'
                },
                template='welcome_email.html',
                to_email=user.email
            )

            return Response({
                "status": "ok",
                "message": "User Reactivated Successfully",
                "data": "User Reactivated Successfully"
            }, status=HTTP_200_OK)
        except Users.DoesNotExist:
            return Response({
                "status": "Failed",
                "message": "User not found",
                "data": "User not found"
            }, status=HTTP_400_BAD_REQUEST)
 
class UpdateUserProfileImage(ProtectedAuthView):
    parser_classes = (MultiPartParser, FormParser)

    def put(self, request, guid, format=None):
        """
        Update user profile image
        """
        user = get_object_or_404(Users, guid=guid, deleted_at__isnull=True)

        if 'image' not in request.data:
            return Response({
                "status": "error",
                "message": "No image provided",
            }, status=HTTP_400_BAD_REQUEST)

        image = request.data['image']
        user.image = image
        user.save()

        return Response({
            "status": "success",
            "message": "Profile image updated successfully",
            "image":user.image.url
        }, status=HTTP_200_OK)
    
class UpdateUser(ProtectedAuthView):
    serializer_class = UserSerializer
    
    
    def patch(self,request,guid,format=None):
        """
        Update User
        """
        one_user=Users.objects.get(guid=guid)

        if 'password' in request.data:
            request.data['password'] = request.data['password']
        if 'first_time_login_request':
            updated_by = 'self'
        else:
            updated_by=request.user.guid


        serializer = UserSerializer(one_user,data=request.data,partial=True)
        if serializer.is_valid():
            serializer.save(updated_by=updated_by)
            return Response(serializer.data,status=HTTP_200_OK)
        else:
            print(serializer.errors)
            return Response({
                "status":"Failed",
                "message":"User Not Updated",
                "data":serializer.errors
            },status=HTTP_400_BAD_REQUEST)

class FirstTimeUpdateUser(ProtectedAuthView):
    serializer_class = UserSerializer
    def patch(self,request,guid,format=None):
        """
        Update User
        """
        one_user=Users.objects.get(guid=guid)

        if 'password' in request.data:
            request.data['password'] = request.data['password']
       
        if 'first_time_login_request':
            updated_by = 'self'

        serializer = UserSerializer(one_user,data=request.data,partial=True)
        if serializer.is_valid():
            serializer.save(updated_by=updated_by)
            return Response(serializer.data,status=HTTP_200_OK)
        else:
            return Response({
                "status":"Failed",
                "message":"User Not Updated",
                "data":"User Not Updated"
            },status=HTTP_400_BAD_REQUEST)


class DeleteUser(ProtectedAuthView):
    serializer_class = UserSerializer
    
    
    def delete(self,request,guid,format=None):
        """
        Delete User
        """
        user = get_object_or_404(Users,guid=guid)
        user.deleted_at = timezone.now()
        user.deleted_by = request.user.guid
        user.is_active = False
        user.save()
        log_soft_delete(user, request.user)
        return Response({
            "status":"OK",
            "message":"Deleted Successfuly",
            "data":"Deleted Successfuly"
        },status=HTTP_200_OK)

# Role
class AllRole(ProtectedAuthView):
    serializer_class = RoleSerializer
    filter_backends = []
    def get(self,request,format=None):
        """
        Get all roles
        """
        all_permissions = Role.objects.filter(deleted_at__isnull=True)
        serializer = RoleSerializer(all_permissions,many=True)
        return Response(serializer.data,status=HTTP_200_OK)

class OneRole(ProtectedAuthView):
    serializer_class = RoleSerializer
    
    def get(self,request,guid,format=None):
        """
        Get one Role
        """
        one_role = get_object_or_404(Role,guid=guid,deleted_at__isnull=True)
        serializer = RoleSerializer(one_role)
        return Response(serializer.data,status=HTTP_200_OK)
        
class CreateRole(ProtectedAuthView):
    serializer_class = RoleSerializer
    
    def post(self,request,format=None):
        """
        Create roles
        """
        try:
            permission_guid_list = request.data.get('permission', [])
            request.data['permission'] = []
            serializer = RoleSerializer(data=request.data)
            if serializer.is_valid():
                one_role= serializer.save(created_by=request.user.guid)
                for permission_guid in permission_guid_list:
                    try:
                        perm_uuid = UUID(permission_guid)
                        permission = Permission.objects.get(guid=perm_uuid)
                        one_role.permission.add(permission)
                    except Permission.DoesNotExist:
                        return Response({
                            "status": "ok",
                            "message": "Permssion sent not found",
                            "data": "Permission sent not found"
                        }, status=HTTP_400_BAD_REQUEST)
                return Response(serializer.data, status=HTTP_200_OK)
            else:
                print(serializer.errors)
                return Response({
                        "status": "ok",
                        "message": serializer.errors,
                        "data": serializer.errors
                    }, status=HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(e)
            return Response({
                "status": "Failed",
                "message": "Role not created",
                "data": f"{e}"
            }, status=HTTP_400_BAD_REQUEST)
    
class UpdateRole(ProtectedAuthView):
    serializer_class = RoleSerializer
    def patch(self,request,guid,format=None):
        """
        Update roles
        """
        try:
            one_role = Role.objects.get(guid=guid)
        except Role.DoesNotExist:
            return Response({
                    "status": "ok",
                    "message": "Role sent not found",
                    "data": "Role sent not found"
                }, status=HTTP_404_NOT_FOUND)
        
        permission_guid_list = request.data.get('permission', [])
        for permission_guid in permission_guid_list:
            try:
                permission = Permission.objects.get(guid=permission_guid)
                one_role.permission.add(permission)
            except Permission.DoesNotExist:
                return Response({
                    "status": "ok",
                    "message": "Permission sent not found",
                    "data": "Permission sent not found"
                }, status=HTTP_400_BAD_REQUEST)

        serializer = RoleSerializer(one_role,data=request.data,partial=True)
        if serializer.is_valid():
            serializer.save(updated_by=request.user.guid)
            return Response(serializer.data, status=HTTP_200_OK)
        else:
            print(serializer.errors)
            return Response({
                    "status": "ok",
                    "message": serializer.errors,
                    "data": serializer.errors
                }, status=HTTP_400_BAD_REQUEST)

class DeleteRole(ProtectedAuthView):
    serializer_class = RoleSerializer
    
    def delete(self,request,guid,format=None):
        """
        Delete roles
        """
        role = get_object_or_404(Role,guid=guid,deleted_at__isnull=True)
        role.deleted_at = timezone.now()
        role.deleted_by = request.user.guid
        role.save()
        log_soft_delete(role, request.user)
        return Response({
            "status":"OK",
            "message":"Deleted Successfuly",
            "data":"Deleted Successfuly"
        },status=HTTP_200_OK)

# Permission
class AllPermissions(ProtectedAuthView):
  serializer_class = PermissionsSerializer
  filter_backends = []

  def get(self, request, format=None):
    """
    Get all permissions
    """
    queryset = Permission.objects.filter(deleted_at__isnull=True)
    serializer = self.serializer_class(queryset, many=True)
    return Response(serializer.data, status=HTTP_200_OK)

class OnePermission(ProtectedAuthView):
    serializer_class = PermissionsSerializer
    
    def get(self,request,guid,format=None):
        """
        Get one Permission
        """
        one_permission = get_object_or_404(Permission,guid=guid,deleted_at__isnull=True)
        serializer = PermissionsSerializer(one_permission)
        return Response(serializer.data,status=HTTP_200_OK)
    
class CreatePermissions(ProtectedAuthView):
    serializer_class = PermissionsSerializer
    
    def post(self,request,format=None):
        """
        Create Permission
        """
        serializer = PermissionsSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(created_by=request.user.guid)
            return Response(serializer.data, status=HTTP_200_OK)
        else:
            print(serializer.errors)
            return Response({
                    "status": "ok",
                    "message": serializer.errors,
                    "data": serializer.errors
                }, status=HTTP_400_BAD_REQUEST)

class UpdatePermissions(ProtectedAuthView):
    serializer_class = PermissionsSerializer
    
    def patch(self,request,guid,format=None):
        """
        Update Permission
        """
        one_permission = Permission.objects.get(guid=guid)
        serializer = PermissionsSerializer(one_permission,data=request.data,partial=True)
        if serializer.is_valid():
            serializer.save(updated_by=request.user.guid)
            return Response(serializer.data, status=HTTP_200_OK)
        else:
            print(serializer.errors)
            return Response({
                    "status": "ok",
                    "message": serializer.errors,
                    "data": serializer.errors
                }, status=HTTP_400_BAD_REQUEST)

class DeletePermissions(ProtectedAuthView):
    serializer_class = PermissionsSerializer
    
    def delete(self,request,guid,format=None):
        """
        Delete Permission
        """
        Permission.objects.get(guid=guid).delete()
        return Response({
            "status":"OK",
            "message":"Deleted Successfuly",
            "data":"Deleted Successfuly"
        },status=HTTP_200_OK)
    
# class Confirm2fa(ProtectedAuthView):
#     serializer_class = Main2FASerializer
#     def post(self, request, format=None):
#         try:
#             current_user = get_object_or_404(Users, guid=request.data['guid'])
#             # Try to get the log entry
#             log_entry = Main2FALog.objects.filter(
#                 otp=request.data['otp'],
#                 user=current_user.guid,
#                 status="Active"
#             ).first()

#             if not log_entry:
#                 return Response({
#                     "status": "Error",
#                     "message": "Expired OTP",
#                     "data": []
#                 }, status=HTTP_400_BAD_REQUEST)

#             # Update the OTP status to Inactive
#             log_entry.status = "Inactive"
#             log_entry.save()

#             return Response({
#                 "status": "ok",
#                 "message": "OTP confirmed",
#                 "data": ""
#             }, status=HTTP_200_OK)
#         except Exception as e:
#             return Response({
#                 "status": "Error",
#                 "message": "Expired OTP",
#                 "data":  ""
#             }, status=HTTP_400_BAD_REQUEST) 

class ActionLog(ProtectedAuthView):
    serializer_class = ActionLogsSerializer
    def get(self, request, format=None):
        all_actions = ActionLogs.objects.all().order_by('-created_at')
        optimized_queryset = ActionLogsSerializer.setup_eager_loading(all_actions)
        return Response(ActionLogsSerializer(optimized_queryset,many=True).data, status=HTTP_200_OK)


# =============================================================================
# COURSE MANAGEMENT VIEWS
# =============================================================================

class AllCourses(ProtectedAuthView):
    serializer_class = CourseSerializer
    filter_backends = []
    
    def get(self, request, format=None):
        """
        Get all courses with optimized queries
        """
        try:
            # Apply filters
            queryset = Courses.objects.filter(deleted_at__isnull=True)
            
            # Filter by status if provided
            status = request.query_params.get('status')
            if status:
                queryset = queryset.filter(status=status)
            
            # Filter by instructor if provided
            instructor_guid = request.query_params.get('instructor')
            if instructor_guid:
                queryset = queryset.filter(instructor__guid=instructor_guid)
                
            # Filter by featured if provided
            is_featured = request.query_params.get('featured')
            if is_featured is not None:
                queryset = queryset.filter(isFeatured=is_featured.lower() == 'true')
            
            # Optimize queries
            optimized_queryset = CourseSerializer.setup_eager_loading(queryset, user=request.user)
            
            serializer = CourseSerializer(optimized_queryset, many=True, context={'user': request.user})
            return Response(serializer.data, status=HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Error retrieving courses",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)

class OneCourse(PublicAuthView):
    serializer_class = CourseSerializer
    
    def get(self, request, guid, format=None):
        """
        Get single course with full details
        Public access - returns course info, plus user progress if authenticated
        """
        try:
            course = get_object_or_404(Courses, guid=guid, deleted_at__isnull=True)
            
            # Optimize single course query
            queryset = Courses.objects.filter(guid=guid, deleted_at__isnull=True)
            
            # Pass user context (None for anonymous users)
            user_context = request.user if request.user.is_authenticated else None
            optimized_queryset = CourseSerializer.setup_eager_loading(queryset, user=user_context)
            course = optimized_queryset.first()
            
            serializer = CourseSerializer(course, context={'user': user_context})
            return Response(serializer.data, status=HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Course not found",
                "data": str(e)
            }, status=HTTP_404_NOT_FOUND)

class CreateCourse(ProtectedAuthView):
    serializer_class = CourseSerializer
    
    def post(self, request, format=None):
        """
        Create new course
        """
        try:
            # Set instructor to current user if not provided
            if 'instructor' not in request.data:
                request.data['instructor'] = request.user.id
                
            serializer = CourseSerializer(data=request.data)
            if serializer.is_valid():
                course = serializer.save(created_by=str(request.user.guid))
                return Response({
                    "status": "ok",
                    "message": "Course created successfully",
                    "data": serializer.data
                }, status=HTTP_201_CREATED)
            else:
                return Response({
                    "status": "Failed",
                    "message": "Course not created",
                    "data": serializer.errors
                }, status=HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Course not created",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)

class UpdateCourse(ProtectedAuthView):
    serializer_class = CourseSerializer
    
    def patch(self, request, guid, format=None):
        """
        Update course
        """
        try:
            course = get_object_or_404(Courses, guid=guid, deleted_at__isnull=True)

            # Check if user can edit this course (instructor or admin)
            if course.instructor != request.user:
                # Add role-based permission check here if needed
                pass

            # Handle course image upload
            if 'image' in request.FILES:
                image = request.FILES['image']
                course.image = image

            serializer = CourseSerializer(course, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save(updated_by=str(request.user.guid))
                course.save()  # Save the course instance with the updated image
                return Response({
                    "status": "ok",
                    "message": "Course updated successfully",
                    "data": serializer.data
                }, status=HTTP_200_OK)
            else:
                return Response({
                    "status": "Failed",
                    "message": "Course not updated",
                    "data": serializer.errors
                }, status=HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Course not updated",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)

class DeleteCourse(ProtectedAuthView):
    serializer_class = CourseSerializer
    
    def delete(self, request, guid, format=None):
        """
        Soft delete course
        """
        try:
            course = get_object_or_404(Courses, guid=guid, deleted_at__isnull=True)
            
            # Check permissions
            if course.instructor != request.user:
                # Add role-based permission check here if needed
                pass
            
            course.deleted_at = timezone.now()
            course.deleted_by = str(request.user.guid)
            course.save()
            
            log_soft_delete(course, request.user)
            
            return Response({
                "status": "OK",
                "message": "Course deleted successfully",
                "data": "Course deleted successfully"
            }, status=HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Course not deleted",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)


# =============================================================================
# COURSE MODULE VIEWS
# =============================================================================

class AllCourseModules(PublicAuthView):
    serializer_class = CourseModuleSerializer
    
    def get(self, request, course_guid=None, format=None):
        """
        Get all modules, optionally filtered by course
        Public access - returns modules info, plus user progress if authenticated
        """
        try:
            if course_guid:
                # Get modules for specific course
                course = get_object_or_404(Courses, guid=course_guid, deleted_at__isnull=True)
                queryset = CourseModules.objects.filter(course=course, deleted_at__isnull=True).order_by('order')
            else:
                # Get all modules
                queryset = CourseModules.objects.filter(deleted_at__isnull=True).order_by('course', 'order')
            
            # Optimize queries
            queryset = queryset.select_related('course').prefetch_related('moduletopics_set')
            
            # Pass user context (None for anonymous users)
            user_context = request.user if request.user.is_authenticated else None
            serializer = CourseModuleSerializer(queryset, many=True, context={'user': user_context})
            return Response(serializer.data, status=HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Error retrieving modules",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)

class OneCourseModule(PublicAuthView):
    serializer_class = CourseModuleSerializer
    
    def get(self, request, guid, format=None):
        """
        Get single course module
        Public access - returns module info, plus user progress if authenticated
        """
        try:
            module = get_object_or_404(CourseModules, guid=guid, deleted_at__isnull=True)
            
            # Pass user context (None for anonymous users)
            user_context = request.user if request.user.is_authenticated else None
            serializer = CourseModuleSerializer(module, context={'user': user_context})
            return Response(serializer.data, status=HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Module not found",
                "data": str(e)
            }, status=HTTP_404_NOT_FOUND)

class CreateCourseModule(ProtectedAuthView):
    serializer_class = CourseModuleSerializer
    
    def post(self, request, format=None):
        """
        Create new course module
        """
        try:
            # Validate course exists and user has permission
            course_guid = request.data.get('course')
            if course_guid:
                course = get_object_or_404(Courses, guid=course_guid, deleted_at__isnull=True)
                # Check if user can add modules to this course
                if course.instructor != request.user:
                    # Add role-based permission check here if needed
                    pass
            
            serializer = CourseModuleSerializer(data=request.data)
            if serializer.is_valid():
                module = serializer.save(created_by=str(request.user.guid))
                return Response({
                    "status": "ok",
                    "message": "Module created successfully",
                    "data": serializer.data
                }, status=HTTP_201_CREATED)
            else:
                return Response({
                    "status": "Failed",
                    "message": "Module not created",
                    "data": serializer.errors
                }, status=HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Module not created",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)

class UpdateCourseModule(ProtectedAuthView):
    serializer_class = CourseModuleSerializer
    
    def patch(self, request, guid, format=None):
        """
        Update course module
        """
        try:
            module = get_object_or_404(CourseModules, guid=guid, deleted_at__isnull=True)
            
            # Check permissions
            if module.course.instructor != request.user:
                # Add role-based permission check here if needed
                pass
            
            serializer = CourseModuleSerializer(module, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save(updated_by=str(request.user.guid))
                return Response({
                    "status": "ok",
                    "message": "Module updated successfully",
                    "data": serializer.data
                }, status=HTTP_200_OK)
            else:
                return Response({
                    "status": "Failed",
                    "message": "Module not updated",
                    "data": serializer.errors
                }, status=HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Module not updated",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)

class DeleteCourseModule(ProtectedAuthView):
    serializer_class = CourseModuleSerializer
    
    def delete(self, request, guid, format=None):
        """
        Soft delete course module
        """
        try:
            module = get_object_or_404(CourseModules, guid=guid, deleted_at__isnull=True)
            
            # Check permissions
            if module.course.instructor != request.user:
                # Add role-based permission check here if needed
                pass
            
            module.deleted_at = timezone.now()
            module.deleted_by = str(request.user.guid)
            module.save()
            
            log_soft_delete(module, request.user)
            
            return Response({
                "status": "OK",
                "message": "Module deleted successfully",
                "data": "Module deleted successfully"
            }, status=HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Module not deleted",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)


# =============================================================================
# MODULE TOPICS VIEWS
# =============================================================================

class AllModuleTopics(PublicAuthView):
    serializer_class = ModuleTopicSerializer
    
    def get(self, request, module_guid=None, format=None):
        """
        Get all topics, optionally filtered by module
        Public access - returns topics info, plus user progress if authenticated
        """
        try:
            if module_guid:
                # Get topics for specific module
                module = get_object_or_404(CourseModules, guid=module_guid, deleted_at__isnull=True)
                queryset = ModuleTopics.objects.filter(module=module, deleted_at__isnull=True).order_by('order')
            else:
                # Get all topics
                queryset = ModuleTopics.objects.filter(deleted_at__isnull=True).order_by('module', 'order')
            
            # Optimize queries
            queryset = queryset.select_related('module', 'module__course')
            
            # Pass user context for progress tracking if authenticated
            user_context = request.user if request.user.is_authenticated else None
            serializer = ModuleTopicSerializer(queryset, many=True, context={'user': user_context})
            return Response(serializer.data, status=HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Error retrieving topics",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)

class OneModuleTopic(ProtectedAuthView):
    serializer_class = ModuleTopicSerializer
    
    def get(self, request, guid, format=None):
        """
        Get single module topic
        """
        try:
            topic = get_object_or_404(ModuleTopics, guid=guid, deleted_at__isnull=True)
            serializer = ModuleTopicSerializer(topic, context={'user': request.user})
            return Response(serializer.data, status=HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Topic not found",
                "data": str(e)
            }, status=HTTP_404_NOT_FOUND)

class CreateModuleTopic(ProtectedAuthView):
    serializer_class = ModuleTopicSerializer
    
    def post(self, request, format=None):
        """
        Create new module topic
        """
        try:
            # Validate module exists and user has permission
            module_guid = request.data.get('module')
            if module_guid:
                module = get_object_or_404(CourseModules, guid=module_guid, deleted_at__isnull=True)
                # Check if user can add topics to this module
                if module.course.instructor != request.user:
                    # Add role-based permission check here if needed
                    pass
            
            serializer = ModuleTopicSerializer(data=request.data)
            if serializer.is_valid():
                topic = serializer.save(created_by=str(request.user.guid))
                return Response({
                    "status": "ok",
                    "message": "Topic created successfully",
                    "data": serializer.data
                }, status=HTTP_201_CREATED)
            else:
                return Response({
                    "status": "Failed",
                    "message": "Topic not created",
                    "data": serializer.errors
                }, status=HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Topic not created",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)

class UpdateModuleTopic(ProtectedAuthView):
    serializer_class = ModuleTopicSerializer
    
    def patch(self, request, guid, format=None):
        """
        Update module topic
        """
        try:
            topic = get_object_or_404(ModuleTopics, guid=guid, deleted_at__isnull=True)
            
            # Check permissions
            if topic.module.course.instructor != request.user:
                # Add role-based permission check here if needed
                pass
            
            serializer = ModuleTopicSerializer(topic, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save(updated_by=str(request.user.guid))
                return Response({
                    "status": "ok",
                    "message": "Topic updated successfully",
                    "data": serializer.data
                }, status=HTTP_200_OK)
            else:
                return Response({
                    "status": "Failed",
                    "message": "Topic not updated",
                    "data": serializer.errors
                }, status=HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Topic not updated",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)

class DeleteModuleTopic(ProtectedAuthView):
    serializer_class = ModuleTopicSerializer
    
    def delete(self, request, guid, format=None):
        """
        Soft delete module topic
        """
        try:
            topic = get_object_or_404(ModuleTopics, guid=guid, deleted_at__isnull=True)
            
            # Check permissions
            if topic.module.course.instructor != request.user:
                # Add role-based permission check here if needed
                pass
            
            topic.deleted_at = timezone.now()
            topic.deleted_by = str(request.user.guid)
            topic.save()
            
            log_soft_delete(topic, request.user)
            
            return Response({
                "status": "OK",
                "message": "Topic deleted successfully",
                "data": "Topic deleted successfully"
            }, status=HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Topic not deleted",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)


# =============================================================================
# QUIZ MANAGEMENT VIEWS
# =============================================================================

class AllModuleQuizzes(ProtectedAuthView):
    serializer_class = ModuleQuizSerializer
    
    def get(self, request, module_guid=None, format=None):
        """
        Get all quizzes, optionally filtered by module
        """
        try:
            if module_guid:
                # Get quizzes for specific module
                module = get_object_or_404(CourseModules, guid=module_guid, deleted_at__isnull=True)
                queryset = ModuleQuizes.objects.filter(module=module, deleted_at__isnull=True)
            else:
                # Get all quizzes
                queryset = ModuleQuizes.objects.filter(deleted_at__isnull=True)
            
            # Optimize queries
            queryset = queryset.select_related('module', 'module__course').prefetch_related('quizquestions_set')
            
            serializer = ModuleQuizSerializer(queryset, many=True)
            return Response(serializer.data, status=HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Error retrieving quizzes",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)

class OneModuleQuiz(ProtectedAuthView):
    serializer_class = ModuleQuizSerializer
    
    def get(self, request, guid, format=None):
        """
        Get single module quiz with questions and user responses
        """
        try:
            quiz = get_object_or_404(ModuleQuizes, guid=guid, deleted_at__isnull=True)
            # Optimize query with prefetch
            quiz_queryset = ModuleQuizes.objects.filter(guid=guid).prefetch_related('quizquestions_set')
            quiz = quiz_queryset.first()
            
            serializer = ModuleQuizSerializer(quiz)
            quiz_data = serializer.data
            
            # Add user responses to each question
            if 'questions' in quiz_data:
                for question_data in quiz_data['questions']:
                    # Query for user's response to this question
                    user_response = QuizResponses.objects.filter(
                        user=request.user,
                        question__guid=question_data['guid']
                    ).first()
                    
                    if user_response:
                        question_data['user_response'] = {
                            'guid': str(user_response.guid),
                            'selected_answer': user_response.selected_answer,
                            'is_correct': user_response.is_correct,
                            'created_at': user_response.created_at,
                            'updated_at': user_response.updated_at
                        }
                    else:
                        question_data['user_response'] = None
            
            return Response(quiz_data, status=HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Quiz not found",
                "data": str(e)
            }, status=HTTP_404_NOT_FOUND)

class CreateModuleQuiz(ProtectedAuthView):
    serializer_class = ModuleQuizSerializer
    
    def post(self, request, format=None):
        """
        Create new module quiz
        """
        try:
            # Validate module exists and user has permission
            module_guid = request.data.get('module')
            if module_guid:
                module = get_object_or_404(CourseModules, guid=module_guid, deleted_at__isnull=True)
                # Check if user can add quizzes to this module
                if module.course.instructor != request.user:
                    # Add role-based permission check here if needed
                    pass
            
            serializer = ModuleQuizSerializer(data=request.data)
            if serializer.is_valid():
                quiz = serializer.save(created_by=str(request.user.guid))
                return Response({
                    "status": "ok",
                    "message": "Quiz created successfully",
                    "data": serializer.data
                }, status=HTTP_201_CREATED)
            else:
                return Response({
                    "status": "Failed",
                    "message": "Quiz not created",
                    "data": serializer.errors
                }, status=HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Quiz not created",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)

class UpdateModuleQuiz(ProtectedAuthView):
    serializer_class = ModuleQuizSerializer
    
    def patch(self, request, guid, format=None):
        """
        Update module quiz
        """
        try:
            quiz = get_object_or_404(ModuleQuizes, guid=guid, deleted_at__isnull=True)
            
            # Check permissions
            if quiz.module.course.instructor != request.user:
                # Add role-based permission check here if needed
                pass
            
            serializer = ModuleQuizSerializer(quiz, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save(updated_by=str(request.user.guid))
                return Response({
                    "status": "ok",
                    "message": "Quiz updated successfully",
                    "data": serializer.data
                }, status=HTTP_200_OK)
            else:
                return Response({
                    "status": "Failed",
                    "message": "Quiz not updated",
                    "data": serializer.errors
                }, status=HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Quiz not updated",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)

class DeleteModuleQuiz(ProtectedAuthView):
    serializer_class = ModuleQuizSerializer
    
    def delete(self, request, guid, format=None):
        """
        Soft delete module quiz
        """
        try:
            quiz = get_object_or_404(ModuleQuizes, guid=guid, deleted_at__isnull=True)
            
            # Check permissions
            if quiz.module.course.instructor != request.user:
                # Add role-based permission check here if needed
                pass
            
            quiz.deleted_at = timezone.now()
            quiz.deleted_by = str(request.user.guid)
            quiz.save()
            
            log_soft_delete(quiz, request.user)
            
            return Response({
                "status": "OK",
                "message": "Quiz deleted successfully",
                "data": "Quiz deleted successfully"
            }, status=HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Quiz not deleted",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)


# =============================================================================
# QUIZ QUESTIONS VIEWS
# =============================================================================

class AllQuizQuestions(ProtectedAuthView):
    serializer_class = QuizQuestionsSerializer
    
    def get(self, request, quiz_guid=None, format=None):
        """
        Get all quiz questions, optionally filtered by quiz
        """
        try:
            if quiz_guid:
                # Get questions for specific quiz
                quiz = get_object_or_404(ModuleQuizes, guid=quiz_guid, deleted_at__isnull=True)
                queryset = QuizQuestions.objects.filter(quiz=quiz, deleted_at__isnull=True).order_by('order')
            else:
                # Get all questions
                queryset = QuizQuestions.objects.filter(deleted_at__isnull=True).order_by('quiz', 'order')
            
            serializer = QuizQuestionsSerializer(queryset, many=True)
            return Response(serializer.data, status=HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Error retrieving questions",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)

class OneQuizQuestion(ProtectedAuthView):
    serializer_class = QuizQuestionsSerializer
    
    def get(self, request, guid, format=None):
        """
        Get single quiz question
        """
        try:
            question = get_object_or_404(QuizQuestions, guid=guid, deleted_at__isnull=True)
            serializer = QuizQuestionsSerializer(question)
            return Response(serializer.data, status=HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Question not found",
                "data": str(e)
            }, status=HTTP_404_NOT_FOUND)

class CreateQuizQuestion(ProtectedAuthView):
    serializer_class = QuizQuestionsSerializer
    
    def post(self, request, format=None):
        """
        Create new quiz question
        """
        try:
            # Validate quiz exists and user has permission
            quiz_guid = request.data.get('quiz')
            if quiz_guid:
                quiz = get_object_or_404(ModuleQuizes, guid=quiz_guid, deleted_at__isnull=True)
                # Check if user can add questions to this quiz
                if quiz.module.course.instructor != request.user:
                    # Add role-based permission check here if needed
                    pass
            
            serializer = QuizQuestionsSerializer(data=request.data)
            if serializer.is_valid():
                question = serializer.save(created_by=str(request.user.guid))
                return Response({
                    "status": "ok",
                    "message": "Question created successfully",
                    "data": serializer.data
                }, status=HTTP_201_CREATED)
            else:
                return Response({
                    "status": "Failed",
                    "message": "Question not created",
                    "data": serializer.errors
                }, status=HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Question not created",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)

class UpdateQuizQuestion(ProtectedAuthView):
    serializer_class = QuizQuestionsSerializer

    def patch(self, request, guid, format=None):
        """
        Update quiz question
        """
        try:
            question = get_object_or_404(QuizQuestions, guid=guid, deleted_at__isnull=True)

            # Resolve the quiz UUID to a ModuleQuizes instance
            # if 'quiz' in request.data:
            #     quiz_uuid = request.data['quiz']
            #     request.data['quiz'] = get_object_or_404(ModuleQuizes, guid=quiz_uuid).guid

            serializer = QuizQuestionsSerializer(question, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save(updated_by=str(request.user.guid))
                return Response({
                    "status": "ok",
                    "message": "Question updated successfully",
                    "data": serializer.data
                }, status=HTTP_200_OK)
            else:
                return Response({
                    "status": "Failed",
                    "message": "Question not updated",
                    "data": serializer.errors
                }, status=HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Question not updated",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)

class DeleteQuizQuestion(ProtectedAuthView):
    serializer_class = QuizQuestionsSerializer
    
    def delete(self, request, guid, format=None):
        """
        Soft delete quiz question
        """
        try:
            question = get_object_or_404(QuizQuestions, guid=guid, deleted_at__isnull=True)
            
            # Check permissions
            if question.quiz.module.course.instructor != request.user:
                # Add role-based permission check here if needed
                pass
            
            question.deleted_at = timezone.now()
            question.deleted_by = str(request.user.guid)
            question.save()
            
            log_soft_delete(question, request.user)
            
            return Response({
                "status": "OK",
                "message": "Question deleted successfully",
                "data": "Question deleted successfully"
            }, status=HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Question not deleted",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)


# =============================================================================
# STUDENT/LEARNING VIEWS
# =============================================================================

class EnrollInCourse(ProtectedAuthView):
    serializer_class = CourseEnrollmentSerializer
    
    def post(self, request, format=None):
        """
        Enroll current user in a course
        """
        try:
            course_guid = request.data.get('course')
            course = get_object_or_404(Courses, guid=course_guid, deleted_at__isnull=True)
            
            # Check if already enrolled
            if UsersCourseEnrollment.objects.filter(user=request.user, course=course, deleted_at__isnull=True).exists():
                return Response({
                    "status": "ok",
                    "message": "Already enrolled in this course",
                    "data": "Already enrolled in this course"
                }, status=HTTP_400_BAD_REQUEST)
            
            # Prepare data for serializer
            enrollment_data = {
                'user': request.user.guid,
                'course': course.guid,
            }
            
            serializer = self.serializer_class(data=enrollment_data)
            if serializer.is_valid():
                enrollment = serializer.save(created_by=str(request.user.guid))
                
                return Response({
                    "status": "ok",
                    "message": "Successfully enrolled in course",
                    "data": serializer.data
                }, status=HTTP_201_CREATED)
            else:
                return Response({
                    "status": "Failed",
                    "message": "Enrollment failed",
                    "data": serializer.errors
                }, status=HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Enrollment failed",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)

class UnenrollFromCourse(ProtectedAuthView):
    serializer_class = UnenrollmentSerializer
    
    def delete(self, request, course_guid, format=None):
        """
        Unenroll current user from a course
        """
        try:
            course = get_object_or_404(Courses, guid=course_guid, deleted_at__isnull=True)
            enrollment = get_object_or_404(
                UsersCourseEnrollment, 
                user=request.user, 
                course=course, 
                deleted_at__isnull=True
            )
            
            # Soft delete enrollment
            enrollment.deleted_at = timezone.now()
            enrollment.deleted_by = str(request.user.guid)
            enrollment.save()
            
            # Prepare response data
            response_data = {
                'course_guid': str(course.guid),
                'course_title': course.title,
                'unenrolled_at': enrollment.deleted_at,
                'message': 'Successfully unenrolled from course'
            }
            
            return Response({
                "status": "OK",
                "message": "Successfully unenrolled from course",
                "data": response_data
            }, status=HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Unenrollment failed",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)

class MyCourses(ProtectedAuthView):
    serializer_class = EnrolledCourseSerializer
    
    def get(self, request, format=None):
        """
        Get courses current user is enrolled in
        """
        try:
            enrollments = UsersCourseEnrollment.objects.filter(
                user=request.user, 
                deleted_at__isnull=True
            )
            
            # Optimize queries
            optimized_enrollments = EnrolledCourseSerializer.setup_eager_loading(enrollments, user=request.user)
            
            serializer = self.serializer_class(optimized_enrollments, many=True, context={'user': request.user})
            
            return Response(serializer.data, status=HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Error retrieving courses",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)

class CourseProgress(ProtectedAuthView):
    serializer_class = UserProgressSerializer
    
    def get(self, request, course_guid, format=None):
        """
        Get user's progress in a specific course
        """
        try:
            course = get_object_or_404(Courses, guid=course_guid, deleted_at__isnull=True)
            
            # Check if user is enrolled
            if not UsersCourseEnrollment.objects.filter(
                user=request.user, 
                course=course, 
                deleted_at__isnull=True
            ).exists():
                return Response({
                    "status": "Failed",
                    "message": "Not enrolled in this course",
                    "data": "Not enrolled in this course"
                }, status=HTTP_400_BAD_REQUEST)
            
            # Get modules and their progress
            modules = CourseModules.objects.filter(course=course, deleted_at__isnull=True).order_by('order')
            modules_progress_objects = []
            
            for module in modules:
                module_progress_obj, created = UserModuleProgress.objects.get_or_create(
                    user=request.user,
                    module=module
                )
                # Force update quiz progress
                module_progress_obj.update_quiz_progress()
                # Refresh from database to get updated values
                module_progress_obj.refresh_from_db()
                modules_progress_objects.append(module_progress_obj)
            
            # Optional: Clear cache if requested
            clear_cache = request.query_params.get('clear_cache', '').lower() == 'true'
            if clear_cache:
                from django.core.cache import cache
                cache_key = f"course_progress_{course.guid}_{request.user.guid}"
                cache.delete(cache_key)
            
            # Serialize the progress data
            serializer = self.serializer_class(modules_progress_objects, many=True)
            
            course_data = {
                'course_guid': str(course.guid),
                'course_title': course.title,
                'overall_progress': course.course_progress(request.user),
                'modules_progress': serializer.data,
                'debug_info': self._get_debug_info(course, request.user) if request.query_params.get('debug') == 'true' else None
            }
            
            return Response(course_data, status=HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Error retrieving progress",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)
    
    def _get_debug_info(self, course, user):
        """Debug information for progress calculation"""
        debug_info = []
        
        for module in course.coursemodules_set.filter(deleted_at__isnull=True):
            # Get quiz questions count
            total_questions = QuizQuestions.objects.filter(
                quiz__module=module, 
                deleted_at__isnull=True
            ).count()
            
            # Get answered questions count  
            answered_questions = QuizResponses.objects.filter(
                user=user,
                question__quiz__module=module,
                deleted_at__isnull=True
            ).count()
            
            # Get module progress object
            try:
                module_progress = UserModuleProgress.objects.get(user=user, module=module)
                quiz_completed = module_progress.quiz_completed
                topics_completed_count = len(module_progress.topics_completed_guids)
            except UserModuleProgress.DoesNotExist:
                quiz_completed = False
                topics_completed_count = 0
            
            # Get total topics
            total_topics = module.moduletopics_set.filter(deleted_at__isnull=True).count()
            
            debug_info.append({
                'module_name': module.name,
                'module_guid': str(module.guid),
                'total_questions': total_questions,
                'answered_questions': answered_questions,
                'quiz_completed': quiz_completed,
                'topics_completed_count': topics_completed_count,
                'total_topics': total_topics,
                'calculated_progress': module.module_progress(user)
            })
        
        return debug_info

class SubmitQuizResponse(ProtectedAuthView):
    serializer_class = QuizResponseSerializer
    
    def post(self, request, format=None):
        """
        Submit quiz answer
        """
        try:
            question_guid = request.data.get('question')
            selected_answer = request.data.get('selected_answer')
            
            question = get_object_or_404(QuizQuestions, guid=question_guid, deleted_at__isnull=True)
            
            # Check if user is enrolled in the course
            if not UsersCourseEnrollment.objects.filter(
                user=request.user, 
                course=question.quiz.module.course, 
                deleted_at__isnull=True
            ).exists():
                return Response({
                    "status": "Failed",
                    "message": "Not enrolled in this course",
                    "data": "Not enrolled in this course"
                }, status=HTTP_400_BAD_REQUEST)
            
            # Check if already answered
            existing_response = QuizResponses.objects.filter(
                user=request.user,
                question=question,
                deleted_at__isnull=True
            ).first()
            
            if existing_response:
                # Update existing response with new answer
                response_data = {
                    'selected_answer': selected_answer
                }
                
                serializer = QuizResponseSerializer(existing_response, data=response_data, partial=True)
                if serializer.is_valid():
                    response = serializer.save(updated_by=str(request.user.guid))
                    
                    return Response({
                        "status": "ok",
                        "message": "Answer updated successfully",
                        "data": {
                            "is_correct": response.is_correct,
                            "correct_answer": question.correct_answer if response.is_correct else None
                        }
                    }, status=HTTP_200_OK)
                else:
                    return Response({
                        "status": "Failed",
                        "message": "Failed to update answer",
                        "data": serializer.errors
                    }, status=HTTP_400_BAD_REQUEST)
            
            # Prepare data for serializer (new response)
            response_data = {
                'user': request.user.guid,
                'question': question.guid,
                'selected_answer': selected_answer
            }
            
            serializer = QuizResponseSerializer(data=response_data)
            if serializer.is_valid():
                response = serializer.save(created_by=str(request.user.guid))
                
                return Response({
                    "status": "ok",
                    "message": "Answer submitted successfully",
                    "data": {
                        "is_correct": response.is_correct,
                        "correct_answer": question.correct_answer if response.is_correct else None
                    }
                }, status=HTTP_201_CREATED)
            else:
                return Response({
                    "status": "Failed",
                    "message": "Failed to submit answer",
                    "data": serializer.errors
                }, status=HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Failed to submit answer",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)

class GetQuizResults(ProtectedAuthView):
    serializer_class = QuizResponseSerializer
    
    def get(self, request, quiz_guid, format=None):
        """
        Get user's quiz results
        """
        try:
            quiz = get_object_or_404(ModuleQuizes, guid=quiz_guid, deleted_at__isnull=True)
            
            # Check if user is enrolled in the course
            if not UsersCourseEnrollment.objects.filter(
                user=request.user, 
                course=quiz.module.course, 
                deleted_at__isnull=True
            ).exists():
                return Response({
                    "status": "Failed",
                    "message": "Not enrolled in this course",
                    "data": "Not enrolled in this course"
                }, status=HTTP_400_BAD_REQUEST)
            
            # Get user's responses for this quiz
            responses = QuizResponses.objects.filter(
                user=request.user,
                question__quiz=quiz,
                deleted_at__isnull=True
            ).select_related('question')
            
            serializer = self.serializer_class(responses, many=True)
            
            total_questions = quiz.quizquestions_set.filter(deleted_at__isnull=True).count()
            correct_answers = responses.filter(is_correct=True).count()
            total_marks = sum(r.question.marks for r in responses if r.is_correct)
            possible_marks = sum(q.marks for q in quiz.quizquestions_set.filter(deleted_at__isnull=True))
            
            results_data = {
                'quiz_name': quiz.name,
                'total_questions': total_questions,
                'questions_answered': responses.count(),
                'correct_answers': correct_answers,
                'score_percentage': (correct_answers / total_questions * 100) if total_questions > 0 else 0,
                'total_marks': total_marks,
                'possible_marks': possible_marks,
                'completed': responses.count() == total_questions,
                'responses': serializer.data
            }
            
            return Response(results_data, status=HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Error retrieving quiz results",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)

class MarkTopicComplete(ProtectedAuthView):
    serializer_class = TopicCompletionSerializer
    
    def post(self, request, format=None):
        """
        Mark topic as completed for current user
        """
        try:
            serializer = self.serializer_class(data=request.data)
            if not serializer.is_valid():
                return Response({
                    "status": "Failed",
                    "message": "Invalid data",
                    "data": serializer.errors
                }, status=HTTP_400_BAD_REQUEST)
            
            topic_guid = serializer.validated_data['topic_guid']
            topic = get_object_or_404(ModuleTopics, guid=topic_guid, deleted_at__isnull=True)
            
            # Check if user is enrolled in the course
            if not UsersCourseEnrollment.objects.filter(
                user=request.user, 
                course=topic.module.course, 
                deleted_at__isnull=True
            ).exists():
                return Response({
                    "status": "Failed",
                    "message": "Not enrolled in this course",
                    "data": "Not enrolled in this course"
                }, status=HTTP_400_BAD_REQUEST)
            
            # Get or create module progress
            module_progress, created = UserModuleProgress.objects.get_or_create(
                user=request.user,
                module=topic.module
            )
            
            # Add topic to completed list if not already there
            if str(topic.guid) not in module_progress.topics_completed_guids:
                module_progress.topics_completed.append(str(topic.guid))
                module_progress.save()
            
            return Response({
                "status": "ok",
                "message": "Topic marked as completed",
                "data": {
                    "topic_guid": str(topic.guid),
                    "topic_name": topic.name,
                    "module_progress": module_progress.progress
                }
            }, status=HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Failed to mark topic complete",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)


# =============================================================================
# PUBLIC/BROWSE VIEWS
# =============================================================================

class PublicCourses(FreeAuthView):
    serializer_class = PublicCourseSerializer
    
    def get(self, request, format=None):
        """
        Get public course catalog (no authentication required)
        """
        try:
            queryset = Courses.objects.filter(
                deleted_at__isnull=True,
                status='PUBLISHED'  # Only show published courses
            ).select_related('instructor')
            
            # Apply filters
            featured = request.query_params.get('featured')
            if featured is not None:
                queryset = queryset.filter(isFeatured=featured.lower() == 'true')
                
            expertise_level = request.query_params.get('level')
            if expertise_level:
                queryset = queryset.filter(expertise_level=expertise_level)
            
            courses = queryset[:20]  # Limit to 20 courses
            serializer = self.serializer_class(courses, many=True)
            
            return Response(serializer.data, status=HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Error retrieving courses",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)

class FeaturedCourses(FreeAuthView):
    serializer_class = PublicCourseSerializer
    
    def get(self, request, format=None):
        """
        Get featured courses
        """
        try:
            queryset = Courses.objects.filter(
                deleted_at__isnull=True,
                status='PUBLISHED',
                isFeatured=True
            ).select_related('instructor')[:10]  # Limit to 10 featured courses
            
            serializer = self.serializer_class(queryset, many=True)
            
            return Response(serializer.data, status=HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Error retrieving featured courses",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)

# class FeaturedCourses(FreeAuthView):
#     serializer_class = PublicCourseSerializer
#     # Provide a default queryset so DRF's GenericAPIView and tooling don't raise
#     # "should either include a `queryset` attribute, or override the `get_queryset()` method."
#     queryset = Courses.objects.filter(deleted_at__isnull=True, status='PUBLISHED', isFeatured=True)

#     def get_queryset(self):
#         """Return featured courses with related instructor, limited to 10."""
#         return self.queryset.select_related('instructor')[:10]

#     def get(self, request, format=None):
#         try:
#             queryset = self.get_queryset()
#             serializer = self.get_serializer(queryset, many=True)

#             return Response({
#                 "status": "ok",
#                 "message": "Featured courses retrieved",
#                 "data": serializer.data
#             }, status=HTTP_200_OK)

#         except Exception as e:
#             return Response({
#                 "status": "Failed",
#                 "message": "Error retrieving featured courses",
#                 "data": str(e)
#             }, status=HTTP_400_BAD_REQUEST)

# =============================================================================
# INSTRUCTOR/ADMIN VIEWS  
# =============================================================================

class CourseEnrollments(ProtectedAuthView):
    serializer_class = CourseEnrollmentSerializer
    
    def get(self, request, course_guid, format=None):
        """
        Get all enrollments for a course (admin/instructor only)
        """
        try:
            course = get_object_or_404(Courses, guid=course_guid, deleted_at__isnull=True)
            
            # Check if user can view enrollments for this course
            if course.instructor != request.user:
                # Add role-based permission check here for admin users
                pass
            
            enrollments = UsersCourseEnrollment.objects.filter(
                course=course,
                deleted_at__isnull=True
            ).select_related('user', 'course').order_by('-enrolled_at')
            
            serializer = self.serializer_class(enrollments, many=True)
            
            return Response({
                'course': {
                    'guid': str(course.guid),
                    'title': course.title
                },
                'quizzes': quiz_submissions_data
            }, status=HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Error retrieving enrollments",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)


# =============================================================================
# COURSE DISCUSSION VIEWS
# =============================================================================

class AllCourseDiscussions(ProtectedAuthView):
    serializer_class = CourseDiscussionSerializer
    
    def get(self, request, course_guid=None, format=None):
        """
        Get all discussions, optionally filtered by course
        """
        try:
            if course_guid:
                # Get discussions for specific course
                course = get_object_or_404(Courses, guid=course_guid, deleted_at__isnull=True)
                
                # Check if user has access to course discussions (enrolled or instructor)
                is_enrolled = UsersCourseEnrollment.objects.filter(
                    user=request.user, 
                    course=course, 
                    deleted_at__isnull=True
                ).exists()
                is_instructor = course.instructor == request.user
                
                if not (is_enrolled or is_instructor):
                    return Response({
                        "status": "Failed",
                        "message": "Not enrolled in this course",
                        "data": "Not enrolled in this course"
                    }, status=HTTP_400_BAD_REQUEST)
                
                queryset = CourseDiscussions.objects.filter(course=course, deleted_at__isnull=True)
            else:
                # Get discussions for all courses user is enrolled in or instructing
                enrolled_courses = UsersCourseEnrollment.objects.filter(
                    user=request.user, 
                    deleted_at__isnull=True
                ).values_list('course', flat=True)
                
                instructing_courses = Courses.objects.filter(
                    instructor=request.user,
                    deleted_at__isnull=True
                ).values_list('id', flat=True)
                
                # Combine enrolled and instructing courses
                from django.db.models import Q
                queryset = CourseDiscussions.objects.filter(
                    Q(course__in=enrolled_courses) | Q(course__in=instructing_courses),
                    deleted_at__isnull=True
                )
            
            # Optimize queries
            optimized_queryset = CourseDiscussionSerializer.setup_eager_loading(queryset)
            
            serializer = self.serializer_class(optimized_queryset, many=True)
            return Response(serializer.data, status=HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Error retrieving discussions",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)

class OneCourseDiscussion(ProtectedAuthView):
    serializer_class = CourseDiscussionSerializer
    
    def get(self, request, guid, format=None):
        """
        Get single course discussion
        """
        try:
            discussion = get_object_or_404(CourseDiscussions, guid=guid, deleted_at__isnull=True)
            
            # Check if user has access to this discussion (enrolled or instructor)
            is_enrolled = UsersCourseEnrollment.objects.filter(
                user=request.user, 
                course=discussion.course, 
                deleted_at__isnull=True
            ).exists()
            is_instructor = discussion.course.instructor == request.user
            
            if not (is_enrolled or is_instructor):
                return Response({
                    "status": "Failed",
                    "message": "Not enrolled in this course",
                    "data": "Not enrolled in this course"
                }, status=HTTP_400_BAD_REQUEST)
            
            serializer = self.serializer_class(discussion)
            return Response(serializer.data, status=HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Discussion not found",
                "data": str(e)
            }, status=HTTP_404_NOT_FOUND)

class CreateCourseDiscussion(ProtectedAuthView):
    serializer_class = CourseDiscussionSerializer
    
    def post(self, request, format=None):
        """
        Create new course discussion/comment
        """
        try:
            # Validate course exists and user is enrolled or instructor
            course_guid = request.data.get('course')
            if course_guid:
                course = get_object_or_404(Courses, guid=course_guid, deleted_at__isnull=True)
                
                # Check if user is enrolled in the course or is the instructor
                is_enrolled = UsersCourseEnrollment.objects.filter(
                    user=request.user, 
                    course=course, 
                    deleted_at__isnull=True
                ).exists()
                is_instructor = course.instructor == request.user
                
                if not (is_enrolled or is_instructor):
                    return Response({
                        "status": "Failed",
                        "message": "Not enrolled in this course",
                        "data": "Not enrolled in this course"
                    }, status=HTTP_400_BAD_REQUEST)
            
            # Set the user to current user GUID (pass UUID object, not string)
            discussion_data = request.data.copy()
            discussion_data['user'] = request.user.guid
            
            serializer = self.serializer_class(data=discussion_data)
            if serializer.is_valid():
                discussion = serializer.save(created_by=str(request.user.guid))
                return Response({
                    "status": "ok",
                    "message": "Discussion created successfully",
                    "data": serializer.data
                }, status=HTTP_201_CREATED)
            else:
                return Response({
                    "status": "Failed",
                    "message": "Discussion not created",
                    "data": serializer.errors
                }, status=HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Discussion not created",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)

class UpdateCourseDiscussion(ProtectedAuthView):
    serializer_class = CourseDiscussionSerializer
    
    def patch(self, request, guid, format=None):
        """
        Update course discussion (by author or instructor)
        """
        try:
            discussion = get_object_or_404(CourseDiscussions, guid=guid, deleted_at__isnull=True)
            
            # Check if user is the author or course instructor
            is_author = discussion.user == request.user
            is_instructor = discussion.course.instructor == request.user
            
            if not (is_author or is_instructor):
                return Response({
                    "status": "Failed",
                    "message": "You can only edit your own discussions or discussions in your courses",
                    "data": "Permission denied"
                }, status=HTTP_400_BAD_REQUEST)
            
            serializer = self.serializer_class(discussion, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save(updated_by=str(request.user.guid))
                return Response({
                    "status": "ok",
                    "message": "Discussion updated successfully",
                    "data": serializer.data
                }, status=HTTP_200_OK)
            else:
                return Response({
                    "status": "Failed",
                    "message": "Discussion not updated",
                    "data": serializer.errors
                }, status=HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Discussion not updated",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)

class DeleteCourseDiscussion(ProtectedAuthView):
    serializer_class = CourseDiscussionSerializer
    
    def delete(self, request, guid, format=None):
        """
        Soft delete course discussion (only by author or instructor)
        """
        try:
            discussion = get_object_or_404(CourseDiscussions, guid=guid, deleted_at__isnull=True)
            
            # Check if user is the author or course instructor
            is_author = discussion.user == request.user
            is_instructor = discussion.course.instructor == request.user
            
            if not (is_author or is_instructor):
                return Response({
                    "status": "Failed",
                    "message": "You can only delete your own discussions or discussions in your courses",
                    "data": "Permission denied"
                }, status=HTTP_400_BAD_REQUEST)
            
            discussion.deleted_at = timezone.now()
            discussion.deleted_by = str(request.user.guid)
            discussion.save()
            
            log_soft_delete(discussion, request.user)
            
            return Response({
                "status": "OK",
                "message": "Discussion deleted successfully",
                "data": "Discussion deleted successfully"
            }, status=HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Discussion not deleted",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)


# =============================================================================
# INSTRUCTOR QUIZ MANAGEMENT VIEWS
# =============================================================================

class CourseQuizSubmissions(ProtectedAuthView):
    """Get all quiz submissions for all quizzes in a course (for instructors)"""
    
    def get(self, request, course_guid, format=None):
        """Get quiz submissions summary for all quizzes in the course"""
        try:
            # Get the course and verify instructor ownership
            course = get_object_or_404(Courses, guid=course_guid, deleted_at__isnull=True)
            
            # Check if user is the instructor of this course
            if course.instructor != request.user:
                return Response({
                    "status": "Failed",
                    "message": "Access denied",
                    "data": "Only course instructors can view quiz submissions"
                }, status=HTTP_403_FORBIDDEN)
            
            # Get all quizzes for this course
            quizzes = ModuleQuizes.objects.filter(
                module__course=course,
                deleted_at__isnull=True
            ).select_related('module')
            
            quiz_submissions_data = []
            
            for quiz in quizzes:
                # Get unique users who have submitted responses for this quiz
                submitted_users = QuizResponses.objects.filter(
                    question__quiz=quiz,
                    deleted_at__isnull=True
               
                ).values('user').distinct()
                
                quiz_data = {
                    'quiz': {
                        'guid': str(quiz.guid),
                        'name': quiz.name,
                        'module_name': quiz.module.name,
                        'total_questions': quiz.quizquestions_set.filter(deleted_at__isnull=True).count()
                    },
                    'submissions_count': len(submitted_users),
                    'submitted_users': []
                }
                
                for user_data in submitted_users:
                    user = Users.objects.get(id=user_data['user'])
                    
                    # Calculate user's performance for this quiz
                    user_responses = QuizResponses.objects.filter(
                        user=user,
                        question__quiz=quiz,
                        deleted_at__isnull=True
                    )
                    
                    total_questions = quiz.quizquestions_set.filter(deleted_at__isnull=True).count()
                    answered_questions = user_responses.count()
                    correct_answers = user_responses.filter(is_correct=True).count()
                    score_percentage = (correct_answers / total_questions * 100) if total_questions > 0 else 0
                    
                    # Check if feedback exists
                    has_feedback = QuizSubmissionFeedback.objects.filter(
                        user=user,
                        quiz=quiz,
                        deleted_at__isnull=True
                    ).exists()
                    
                    quiz_data['submitted_users'].append({
                        'user': {
                            'guid': str(user.guid),
                            'name': f"{user.first_name} {user.last_name}",
                            'email': user.email
                        },
                        'answered_questions': answered_questions,
                        'total_questions': total_questions,
                        'correct_answers': correct_answers,
                        'score_percentage': round(score_percentage, 2),
                        'has_feedback': has_feedback,
                        'submitted_at': user_responses.order_by('-answered_at').first().answered_at if user_responses.exists() else None
                    })
                
                quiz_submissions_data.append(quiz_data)
            
            return Response({
                'course': {
                    'guid': str(course.guid),
                    'title': course.title
                },
                'quizzes': quiz_submissions_data
            }, status=HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Error retrieving quiz submissions",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)


class QuizSubmissions(ProtectedAuthView):
    """Get all submissions for a specific quiz (for instructors)"""
    
    def get(self, request, quiz_guid, format=None):
        """Get detailed submissions for a specific quiz"""
        try:
            # Get the quiz and verify instructor ownership
            quiz = get_object_or_404(ModuleQuizes, guid=quiz_guid, deleted_at__isnull=True)
            
            # Check if user is the instructor of the course that contains this quiz
            if quiz.module.course.instructor != request.user:
                return Response({
                    "status": "Failed",
                    "message": "Access denied",
                    "data": "Only course instructors can view quiz submissions"
                }, status=HTTP_403_FORBIDDEN)
            
            # Get unique users who have submitted responses for this quiz
            submitted_users = QuizResponses.objects.filter(
                question__quiz=quiz,
                deleted_at__isnull=True
            ).values('user').distinct()
            
            submissions_data = []
            total_questions = quiz.quizquestions_set.filter(deleted_at__isnull=True).count()
            
            for user_data in submitted_users:
                user = Users.objects.get(id=user_data['user'])
                
                # Get user's responses for this quiz
                user_responses = QuizResponses.objects.filter(
                    user=user,
                    question__quiz=quiz,
                    deleted_at__isnull=True
                ).select_related('question').order_by('question__order')
                
                answered_questions = user_responses.count()
                correct_answers = user_responses.filter(is_correct=True).count()
                score_percentage = (correct_answers / total_questions * 100) if total_questions > 0 else 0
                
                # Get feedback if it exists
                feedback = QuizSubmissionFeedback.objects.filter(
                    user=user,
                    quiz=quiz,
                    deleted_at__isnull=True
                ).first()
                
                submission_data = {
                    'user': {
                        'guid': str(user.guid),
                        'name': f"{user.first_name} {user.last_name}",
                        'email': user.email
                    },
                    'total_questions': total_questions,
                    'answered_questions': answered_questions,
                    'correct_answers': correct_answers,
                    'score_percentage': round(score_percentage, 2),
                    'submitted_at': user_responses.order_by('-answered_at').first().answered_at if user_responses.exists() else None,
                    'has_feedback': feedback is not None,
                    'feedback': {
                        'feedback': feedback.feedback,
                        'score': feedback.score,
                        'created_at': feedback.created_at
                    } if feedback else None
                }
                
                submissions_data.append(submission_data)
            
            # Sort by submission date (newest first)
            submissions_data.sort(key=lambda x: x['submitted_at'] or timezone.now(), reverse=True)
            
            return Response({
                'quiz': {
                    'guid': str(quiz.guid),
                    'name': quiz.name,
                    'description': quiz.description,
                    'module_name': quiz.module.name,
                    'course_title': quiz.module.course.title,
                    'total_questions': total_questions
                },
                'submissions': submissions_data
            }, status=HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Error retrieving quiz submissions",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)


class UserQuizSubmissionDetail(ProtectedAuthView):
    """Get detailed submission for a specific user and quiz (for instructors)"""
    
    def get(self, request, user_guid, quiz_guid, format=None):
        """Get detailed submission with all answers for a specific user and quiz"""
        try:
            # Get the quiz and verify instructor ownership
            quiz = get_object_or_404(ModuleQuizes, guid=quiz_guid, deleted_at__isnull=True)
            user = get_object_or_404(Users, guid=user_guid)
            
            # Check if user is the instructor of the course that contains this quiz
            if quiz.module.course.instructor != request.user:
                return Response({
                    "status": "Failed",
                    "message": "Access denied",
                    "data": "Only course instructors can view quiz submissions"
                }, status=HTTP_403_FORBIDDEN)
            
            # Get user's responses for this quiz
            user_responses = QuizResponses.objects.filter(
                user=user,
                question__quiz=quiz,
                deleted_at__isnull=True
            ).select_related('question').order_by('question__order')
            
            if not user_responses.exists():
                return Response({
                    "status": "Failed",
                    "message": "No submission found",
                    "data": "User has not submitted answers for this quiz"
                }, status=HTTP_404_NOT_FOUND)
            
            # Get all questions for this quiz
            all_questions = QuizQuestions.objects.filter(
                quiz=quiz,
                deleted_at__isnull=True
            ).order_by('order')
            
            # Calculate statistics
            total_questions = all_questions.count()
            answered_questions = user_responses.count()
            correct_answers = user_responses.filter(is_correct=True).count()
            score_percentage = (correct_answers / total_questions * 100) if total_questions > 0 else 0
            
            # Build detailed response data
            question_responses = []
            for question in all_questions:
                # Find user's response for this question
                response = user_responses.filter(question=question).first()
                
                question_data = {
                    'question': {
                        'guid': str(question.guid),
                        'question_text': question.question_text,
                        'question_type': question.question_type,
                        'options': question.options,
                        'correct_answer': question.correct_answer,
                        'marks': question.marks,
                        'order': question.order
                    },
                    'response': {
                        'selected_answer': response.selected_answer if response else None,
                        'is_correct': response.is_correct if response else False,
                        'answered_at': response.answered_at if response else None
                    } if response else None
                }
                
                question_responses.append(question_data)
            
            # Get feedback if it exists
            feedback = QuizSubmissionFeedback.objects.filter(
                user=user,
                quiz=quiz,
                deleted_at__isnull=True
            ).select_related('instructor').first()
            
            return Response({
                'user': {
                    'guid': str(user.guid),
                    'name': f"{user.first_name} {user.last_name}",
                    'email': user.email
                },
                'quiz': {
                    'guid': str(quiz.guid),
                    'name': quiz.name,
                    'description': quiz.description,
                    'module_name': quiz.module.name,
                    'course_title': quiz.module.course.title
                },
                'statistics': {
                    'total_questions': total_questions,
                    'answered_questions': answered_questions,
                    'correct_answers': correct_answers,
                    'score_percentage': round(score_percentage, 2),
                    'submitted_at': user_responses.order_by('-answered_at').first().answered_at
                },
                'questions_and_responses': question_responses,
                'feedback': {
                    'guid': str(feedback.guid),
                    'feedback': feedback.feedback,
                    'score': feedback.score,
                    'instructor': {
                        'name': f"{feedback.instructor.first_name} {feedback.instructor.last_name}",
                        'email': feedback.instructor.email
                    },
                    'created_at': feedback.created_at,
                    'updated_at': feedback.updated_at
                } if feedback else None
            }, status=HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Error retrieving submission details",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)


class AddQuizFeedback(ProtectedAuthView):
    """Add or update feedback for a user's quiz submission"""
    serializer_class = QuizSubmissionFeedbackSerializer
    
    def post(self, request, user_guid, quiz_guid, format=None):
        """Add feedback for a user's quiz submission"""
        try:
            # Get the quiz and verify instructor ownership
            quiz = get_object_or_404(ModuleQuizes, guid=quiz_guid, deleted_at__isnull=True)
            user = get_object_or_404(Users, guid=user_guid)
            
            # Check if user is the instructor of the course that contains this quiz
            if quiz.module.course.instructor != request.user:
                return Response({
                    "status": "Failed",
                    "message": "Access denied",
                    "data": "Only course instructors can add feedback"
                }, status=HTTP_403_FORBIDDEN)
            
            # Check if user has submitted answers for this quiz
            if not QuizResponses.objects.filter(
                user=user,
                question__quiz=quiz,
                deleted_at__isnull=True
            ).exists():
                return Response({
                    "status": "Failed",
                    "message": "No submission found",
                    "data": "User has not submitted answers for this quiz"
                }, status=HTTP_400_BAD_REQUEST)
            
            # Prepare data for serializer
            feedback_data = request.data.copy()
            feedback_data['user'] = user.guid
            feedback_data['quiz'] = quiz.guid
            feedback_data['instructor'] = request.user.guid
            
            # Check if feedback already exists (including soft-deleted records)
            # This prevents unique constraint violations
            existing_feedback = QuizSubmissionFeedback.objects.filter(
                user=user,
                quiz=quiz
            ).first()
            
            if existing_feedback:
                # Restore if soft-deleted
                if existing_feedback.deleted_at is not None:
                    existing_feedback.deleted_at = None
                    existing_feedback.deleted_by = None
                
                # Update existing feedback
                serializer = self.serializer_class(existing_feedback, data=feedback_data, partial=True)
                if serializer.is_valid():
                    feedback = serializer.save(updated_by=str(request.user.guid))
                    return Response({
                        "status": "ok",
                        "message": "Feedback updated successfully",
                        "data": serializer.data
                    }, status=HTTP_200_OK)
                else:
                    return Response({
                        "status": "Failed",
                        "message": "Feedback not updated",
                        "data": serializer.errors
                    }, status=HTTP_400_BAD_REQUEST)
            else:
                # Create new feedback
                serializer = self.serializer_class(data=feedback_data)
                if serializer.is_valid():
                    feedback = serializer.save(created_by=str(request.user.guid))
                    return Response({
                        "status": "ok",
                        "message": "Feedback added successfully",
                        "data": serializer.data
                    }, status=HTTP_201_CREATED)
                else:
                    return Response({
                        "status": "Failed",
                        "message": "Feedback not added",
                        "data": serializer.errors
                    }, status=HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Error adding feedback",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)
    
    def put(self, request, user_guid, quiz_guid, format=None):
        """Update existing feedback"""
        return self.post(request, user_guid, quiz_guid, format)
    
    def delete(self, request, user_guid, quiz_guid, format=None):
        """Delete feedback for a user's quiz submission"""
        try:
            # Get the quiz and verify instructor ownership
            quiz = get_object_or_404(ModuleQuizes, guid=quiz_guid, deleted_at__isnull=True)
            user = get_object_or_404(Users, guid=user_guid)
            
            # Check if user is the instructor of the course that contains this quiz
            if quiz.module.course.instructor != request.user:
                return Response({
                    "status": "Failed",
                    "message": "Access denied",
                    "data": "Only course instructors can delete feedback"
                }, status=HTTP_403_FORBIDDEN)
            
            # Get the feedback
            feedback = get_object_or_404(
                QuizSubmissionFeedback,
                user=user,
                quiz=quiz,
                deleted_at__isnull=True
            )
            
            # Soft delete the feedback
            feedback.deleted_at = timezone.now()
            feedback.deleted_by = str(request.user.guid)
            feedback.save()
            
            return Response({
                "status": "OK",
                "message": "Feedback deleted successfully",
                "data": "Feedback deleted successfully"
            }, status=HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": "Failed",
                "message": "Feedback not deleted",
                "data": str(e)
            }, status=HTTP_400_BAD_REQUEST)
