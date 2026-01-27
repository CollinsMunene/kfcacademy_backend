import re
from rest_framework import serializers
from django.db.models import Prefetch
from .models import (
    ActionLogs, CourseModules, Courses, Main2FALog, Permission, Users, Role, 
    QuizQuestions, ModuleTopics, ModuleQuizes, QuizResponses, CourseDiscussions,
    UsersCourseEnrollment, UserModuleProgress, QuizSubmissionFeedback
)

class PermissionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = '__all__'
        depth = 1
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name in('created_by','created_at','deleted_at','deleted_by','updated_by','updated_at'):
                field.required = False
            else: 
                field.required = True

class RoleSerializer(serializers.ModelSerializer):
    permission_id = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        default=[]
    )
    permission = PermissionsSerializer(many=True, read_only=True)

    class Meta:
        model = Role
        fields = '__all__'
        depth = 2

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name in (
                'created_by', 'created_at', 'deleted_at',
                'deleted_by', 'updated_by', 'updated_at',
                'permission', 'permission_id', 'description'
            ):
                field.required = False
            else: 
                field.required = True

    def create(self, validated_data):
        permission_ids = validated_data.pop('permission_id', [])
        role = super().create(validated_data)
        if permission_ids:
            role.permission.set(Permission.objects.filter(guid__in=permission_ids))
        return role

    def update(self, instance, validated_data):
        permission_ids = validated_data.pop('permission_id', None)
        role = super().update(instance, validated_data)
        if permission_ids is not None:
            role.permission.set(Permission.objects.filter(guid__in=permission_ids))
        return role

class UserSerializer(serializers.ModelSerializer):
    role = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    
    class Meta:
        model = Users
        fields = (
            'guid', 'image', 'email', 'first_name', 'last_name',
            'phone_number', 'bio','password', 'role', 'is_active',
            'is_first_time_login', 'created_at', 'created_by',
            'updated_at', 'updated_by'
        )
        extra_kwargs = {
            'password': {'write_only': True},
        }
    
    def validate_email(self, value):
        """Validate email format and uniqueness"""
        if value:
            # Check email format (basic validation, Django already does most)
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', value):
                raise serializers.ValidationError("Invalid email format")
            
            # Check uniqueness (excluding current instance if updating)
            queryset = Users.objects.filter(email=value)
            if self.instance:
                queryset = queryset.exclude(guid=self.instance.guid)
            if queryset.exists():
                raise serializers.ValidationError("Email already exists")
        
        return value
    
    def validate_phone_number(self, value):
        """Validate phone number format"""
        if value:
            # Basic phone number validation
            cleaned = re.sub(r'[^\d+]', '', value)
            if not re.match(r'^\+?[\d\s\-\(\)]{7,15}$', cleaned):
                raise serializers.ValidationError("Invalid phone number format")
            return cleaned  # Ensure the cleaned phone number is returned as a string
        return value
    
    def validate_role(self, value):
        """Validate role field - convert UUID string to Role instance"""
        if value is None or value == '':
            return None
            
        try:
            # Try to get the role by its GUID
            role = Role.objects.get(guid=value)
            return role
        except Role.DoesNotExist:
            raise serializers.ValidationError("Role with the provided GUID does not exist")
        except ValueError:
            raise serializers.ValidationError("Invalid UUID format for role")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name in('created_by','created_at','deleted_at','deleted_by','updated_by','updated_at','phone_number','image','role','bio'):
                field.required = False
            else: 
                field.required = True
            
    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = Users(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        return user

    def to_representation(self, instance):
        """Override to return role GUID and name instead of role ID"""
        data = super().to_representation(instance)
        if instance.role:
            data['role'] = {
                'guid': str(instance.role.guid),
                'name': instance.role.name
            }
        else:
            data['role'] = None
        return data

class CourseModuleSerializer(serializers.ModelSerializer):
    course = serializers.UUIDField(write_only=True, help_text="Course GUID - required for creation")
    course_details = serializers.SerializerMethodField(read_only=True)
    module_progress = serializers.SerializerMethodField()
    topics = serializers.SerializerMethodField(read_only=True)
    quizzes = serializers.SerializerMethodField(read_only=True)
    topic_count = serializers.SerializerMethodField()
    quiz_count = serializers.SerializerMethodField()

    class Meta:
        model = CourseModules
        fields = [
            'guid', 'course', 'course_details', 'name', 'description', 'order', 
            'module_progress', 'topics', 'quizzes', 'topic_count', 'quiz_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['guid', 'created_at', 'updated_at']

    def get_course_details(self, obj):
        """Return course details for display"""
        if obj.course:
            return {
                'guid': str(obj.course.guid),
                'title': obj.course.title,
                'status': obj.course.status
            }
        return None

    def get_module_progress(self, obj):
        user = self.context.get('user')
        if not user:
            return 0
        
        # Use prefetched data if available
        if hasattr(obj, '_prefetched_progress'):
            for progress in obj._prefetched_progress:
                if progress.user_id == user.id:
                    return progress.progress
            return 0
        
        return obj.module_progress(user)
    
    def get_topics(self, obj):
        """Return related topics for this module"""
        topics = obj.moduletopics_set.filter(deleted_at__isnull=True).order_by('order')
        topic_data = []
        
        for topic in topics:
            topic_data.append({
                'guid': str(topic.guid),
                'name': topic.name,
                'description': topic.description,
                'duration': str(topic.duration) if topic.duration else None,
                'order': topic.order,
                'files_count': len(topic.files) if topic.files else 0,
                'videos_count': len(topic.videos) if topic.videos else 0,
                'images_count': len(topic.images) if topic.images else 0,
                'created_at': topic.created_at
            })
        
        return topic_data
    
    def get_quizzes(self, obj):
        """Return related quizzes for this module"""
        quizzes = obj.modulequizes_set.filter(deleted_at__isnull=True)
        quiz_data = []
        
        for quiz in quizzes:
            quiz_data.append({
                'guid': str(quiz.guid),
                'name': quiz.name,
                'description': quiz.description,
                'question_count': quiz.quizquestions_set.filter(deleted_at__isnull=True).count(),
                'created_at': quiz.created_at
            })
        
        return quiz_data
    
    def get_topic_count(self, obj):
        """Return count of topics in this module"""
        return obj.moduletopics_set.filter(deleted_at__isnull=True).count()
    
    def get_quiz_count(self, obj):
        """Return count of quizzes in this module"""
        return obj.modulequizes_set.filter(deleted_at__isnull=True).count()
    
    def create(self, validated_data):
        """Convert course UUID to Course instance"""
        course_uuid = validated_data.pop('course')
        try:
            course = Courses.objects.get(guid=course_uuid)
            validated_data['course'] = course
        except Courses.DoesNotExist:
            raise serializers.ValidationError({
                'course': f'Course with GUID {course_uuid} does not exist.'
            })
        return super().create(validated_data)
    
    @classmethod
    def setup_eager_loading(cls, queryset, user=None):
        """Optimize queryset to prevent N+1 queries for CourseModules"""
        queryset = queryset.select_related('course')
        queryset = queryset.prefetch_related(
            'moduletopics_set',
            'modulequizes_set',
            'modulequizes_set__quizquestions_set'
        )
        
        if user:
            from .models import UserModuleProgress
            queryset = queryset.prefetch_related(
                Prefetch(
                    'usermoduleprogress_set',
                    queryset=UserModuleProgress.objects.filter(user=user),
                    to_attr='_prefetched_progress'
                )
            )
        
        return queryset
    
class CourseSerializer(serializers.ModelSerializer):
    total_duration = serializers.CharField(read_only=True)
    course_progress = serializers.SerializerMethodField()
    modules = CourseModuleSerializer(source='coursemodules_set', many=True, read_only=True)
    instructor = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    instructor_details = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Courses
        fields = [
            'id', 'guid', 'title', 'description', 'image', 'tags', 'category',
            'expertise_level', 'prerequisites', 'objectives', 'isPaid', 
            'amount', 'currency', 'isFeatured', 'status', 'instructor',
            'instructor_details', 'total_duration', 'course_progress', 'modules',
            'created_at', 'created_by', 'updated_at', 'updated_by', 
            'deleted_at', 'deleted_by'
        ]
        depth = 0  # Reduced depth to prevent over-fetching
    
    def get_instructor_details(self, obj):
        if obj.instructor:
            return {
                'guid': obj.instructor.guid,
                'email': obj.instructor.email,
                'first_name': obj.instructor.first_name,
                'last_name': obj.instructor.last_name,
                'bio': obj.instructor.bio,
                'image': obj.instructor.image.url if obj.instructor.image else None,
            }
        return None
    
    def validate_instructor(self, value):
        """Validate instructor field - convert UUID string to User instance"""
        if value is None or value == '':
            return None
            
        try:
            # Try to get the user by their GUID
            user = Users.objects.get(guid=value)
            return user
        except Users.DoesNotExist:
            raise serializers.ValidationError("User with the provided GUID does not exist")
        except ValueError:
            raise serializers.ValidationError("Invalid UUID format for instructor")
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name in('created_by','created_at','deleted_at','deleted_by','updated_by','updated_at','image'):
                field.required = False
            else: 
                field.required = True
    
    def get_course_progress(self, obj):
        user = self.context.get('user')
        if not user:
            return 0
        return obj.course_progress(user)
    
    @classmethod
    def setup_eager_loading(cls, queryset, user=None):
        """Optimize queryset to prevent N+1 queries"""
        queryset = queryset.select_related('instructor', 'instructor__role')
        queryset = queryset.prefetch_related(
            'coursemodules_set__moduletopics_set',
            'coursemodules_set__modulequizes_set',
            'coursemodules_set__modulequizes_set__quizquestions_set'
        )
        
        if user:
            from .models import UserModuleProgress
            queryset = queryset.prefetch_related(
                Prefetch(
                    'coursemodules_set__usermoduleprogress_set',
                    queryset=UserModuleProgress.objects.filter(user=user),
                    to_attr='_prefetched_progress'
                )
            )
        
        return queryset

    def to_representation(self, instance):
        """Override to return instructor GUID and details instead of instructor ID"""
        data = super().to_representation(instance)
        if instance.instructor:
            data['instructor'] = str(instance.instructor.guid)
        else:
            data['instructor'] = None
        return data


     
class Main2FASerializer(serializers.ModelSerializer):
    class Meta:
        model = Main2FALog
        fields = '__all__'
        depth = 2
        
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name in('created_by','created_at','deleted_at','deleted_by','updated_by','updated_at'):
                field.required = False
            else: 
                field.required = True

class ActionLogsSerializer(serializers.ModelSerializer):
    initiator_id = serializers.SerializerMethodField()

    class Meta:
        model = ActionLogs
        fields = '__all__'
        depth = 0
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name in('created_by','created_at','deleted_at','deleted_by','updated_by','updated_at'):
                field.required = False
            else: 
                field.required = True

    def get_initiator_id(self, obj):
        user = obj.initiator_id
        if not user:
            return None
        return {
            "guid": user.guid,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "image": user.image.url if user.image else None,
        }
    
    @classmethod
    def setup_eager_loading(cls, queryset):
        """Optimize queryset to prevent N+1 queries"""
        return queryset.select_related('initiator_id')


class QuizQuestionsSerializer(serializers.ModelSerializer):
    quiz = serializers.UUIDField(write_only=True)
    quiz_details = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = QuizQuestions
        fields = [
            'guid', 'quiz', 'quiz_details', 'question_text', 'question_type', 
            'options', 'correct_answer', 'marks', 'order', 'created_at', 'updated_at'
        ]
        read_only_fields = ['guid', 'created_at', 'updated_at']

    def get_quiz_details(self, obj):
        """Return quiz details for display"""
        if obj.quiz:
            return {
                'guid': str(obj.quiz.guid),
                'name': obj.quiz.name,
                'module_name': obj.quiz.module.name if obj.quiz.module else None
            }
        return None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name in('created_by','created_at','deleted_at','deleted_by','updated_by','updated_at','guid','quiz_details'):
                field.required = False

    def validate(self, data):
        """Validate question data"""
        if data.get('question_type') == 'mcq':
            if not data.get('options'):
                raise serializers.ValidationError({
                    'options': 'Options are required for multiple choice questions.'
                })
            
            if data.get('correct_answer') and data.get('correct_answer') not in data.get('options', []):
                raise serializers.ValidationError({
                    'correct_answer': 'Correct answer must be one of the available options.'
                })
        
        return data
    
    
    def validate_quiz(self, value):
        try:
            quiz_instance = ModuleQuizes.objects.get(guid=value)
            return quiz_instance
        except ModuleQuizes.DoesNotExist:
            raise serializers.ValidationError(f"Quiz with GUID {value} does not exist.")
        
    def create(self, validated_data):
        """Convert quiz UUID to Quiz instance"""
        # quiz_uuid = validated_data.pop('quiz')
        # try:
        #     quiz = ModuleQuizes.objects.get(guid=quiz_uuid)
        #     validated_data['quiz'] = quiz
        # except ModuleQuizes.DoesNotExist:
        #     raise serializers.ValidationError({
        #         'quiz': f'Quiz with GUID {quiz_uuid} does not exist.'
        #     })
        return super().create(validated_data)


class ModuleTopicSerializer(serializers.ModelSerializer):
    module = serializers.UUIDField(write_only=True, help_text="Module GUID - required for creation")
    module_details = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = ModuleTopics
        fields = [
            'guid', 'module', 'module_details', 'name', 'description', 'files', 
            'files_description', 'videos', 'videos_description', 'images', 
            'images_description', 'duration', 'order', 'created_at', 'updated_at'
        ]
        read_only_fields = ['guid', 'created_at', 'updated_at']

    def get_module_details(self, obj):
        """Return module details for display"""
        if obj.module:
            return {
                'guid': str(obj.module.guid),
                'name': obj.module.name,
                'course_title': obj.module.course.title if obj.module.course else None
            }
        return None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name in('created_by','created_at','deleted_at','deleted_by','updated_by','updated_at', 'guid', 'module_details','images_description','videos_description','files_description'):
                field.required = False
    
    def create(self, validated_data):
        """Convert module UUID to Module instance"""
        module_uuid = validated_data.pop('module')
        try:
            module = CourseModules.objects.get(guid=module_uuid)
            validated_data['module'] = module
        except CourseModules.DoesNotExist:
            raise serializers.ValidationError({
                'module': f'Module with GUID {module_uuid} does not exist.'
            })
        return super().create(validated_data)


class ModuleQuizSerializer(serializers.ModelSerializer):
    module = serializers.UUIDField(write_only=True, help_text="Module GUID - required for creation")
    module_details = serializers.SerializerMethodField(read_only=True)
    questions = QuizQuestionsSerializer(source='quizquestions_set', many=True, read_only=True)
    question_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ModuleQuizes
        fields = [
            'guid', 'module', 'module_details', 'name', 'description',
            'questions', 'question_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['guid', 'created_at', 'updated_at']

    def get_module_details(self, obj):
        """Return module details for display"""
        if obj.module:
            return {
                'guid': str(obj.module.guid),
                'name': obj.module.name,
                'course_title': obj.module.course.title if obj.module.course else None
            }
        return None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name in('created_by','created_at','deleted_at','deleted_by','updated_by','updated_at','questions','question_count','guid','module_details'):
                field.required = False
    
    def get_question_count(self, obj):
        return obj.quizquestions_set.filter(deleted_at__isnull=True).count()
    
    def create(self, validated_data):
        """Convert module UUID to Module instance"""
        module_uuid = validated_data.pop('module')
        try:
            module = CourseModules.objects.get(guid=module_uuid)
            validated_data['module'] = module
        except CourseModules.DoesNotExist:
            raise serializers.ValidationError({
                'module': f'Module with GUID {module_uuid} does not exist.'
            })
        return super().create(validated_data)


class QuizResponseSerializer(serializers.ModelSerializer):
    user = serializers.UUIDField(write_only=True, help_text="User GUID - required for creation")
    question = serializers.UUIDField(write_only=True, help_text="Question GUID - required for creation") 
    user_details = serializers.SerializerMethodField(read_only=True)
    question_details = serializers.SerializerMethodField(read_only=True)
    question_text = serializers.CharField(source='question.question_text', read_only=True)
    correct_answer = serializers.CharField(source='question.correct_answer', read_only=True)
    
    class Meta:
        model = QuizResponses
        fields = [
            'guid', 'user', 'question', 'user_details', 'question_details', 'question_text',
            'selected_answer', 'is_correct', 'correct_answer', 'answered_at', 'created_at'
        ]
        read_only_fields = ['guid', 'is_correct', 'answered_at', 'created_at']

    def get_user_details(self, obj):
        """Return user details for display"""
        if obj.user:
            return {
                'guid': str(obj.user.guid),
                'name': f"{obj.user.first_name} {obj.user.last_name}",
                'email': obj.user.email
            }
        return None

    def get_question_details(self, obj):
        """Return question details for display"""
        if obj.question:
            return {
                'guid': str(obj.question.guid),
                'question_text': obj.question.question_text,
                'marks': obj.question.marks
            }
        return None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name in('created_by','created_at','deleted_at','deleted_by','updated_by','updated_at','is_correct','answered_at','question_text','correct_answer','guid','user_details','question_details'):
                field.required = False
            else: 
                field.required = True
    
    def create(self, validated_data):
        """Convert user and question UUIDs to model instances"""
        user_uuid = validated_data.pop('user')
        question_uuid = validated_data.pop('question')
        
        try:
            user = Users.objects.get(guid=user_uuid)
            validated_data['user'] = user
        except Users.DoesNotExist:
            raise serializers.ValidationError({
                'user': f'User with GUID {user_uuid} does not exist.'
            })
        
        try:
            question = QuizQuestions.objects.get(guid=question_uuid)
            validated_data['question'] = question
        except QuizQuestions.DoesNotExist:
            raise serializers.ValidationError({
                'question': f'Question with GUID {question_uuid} does not exist.'
            })
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Convert UUIDs to model instances for updates"""
        if 'user' in validated_data:
            user_uuid = validated_data.pop('user')
            try:
                user = Users.objects.get(guid=user_uuid)
                validated_data['user'] = user
            except Users.DoesNotExist:
                raise serializers.ValidationError({
                    'user': f'User with GUID {user_uuid} does not exist.'
                })
        
        if 'question' in validated_data:
            question_uuid = validated_data.pop('question')
            try:
                question = QuizQuestions.objects.get(guid=question_uuid)
                validated_data['question'] = question
            except QuizQuestions.DoesNotExist:
                raise serializers.ValidationError({
                    'question': f'Question with GUID {question_uuid} does not exist.'
                })
        
        return super().update(instance, validated_data)


class CourseEnrollmentSerializer(serializers.ModelSerializer):
    user = serializers.UUIDField(write_only=True, help_text="User GUID - required for creation")
    course = serializers.UUIDField(write_only=True, help_text="Course GUID - required for creation")
    user_details = serializers.SerializerMethodField(read_only=True)
    course_details = serializers.SerializerMethodField(read_only=True)
    user_name = serializers.SerializerMethodField()
    course_title = serializers.CharField(source='course.title', read_only=True)
    progress = serializers.SerializerMethodField()
    
    class Meta:
        model = UsersCourseEnrollment
        fields = [
            'guid', 'user', 'course', 'user_details', 'course_details', 'user_name', 
            'course_title', 'progress', 'enrolled_at', 'created_at'
        ]
        read_only_fields = ['guid', 'enrolled_at', 'created_at']

    def get_user_details(self, obj):
        """Return user details for display"""
        if obj.user:
            return {
                'guid': str(obj.user.guid),
                'name': f"{obj.user.first_name} {obj.user.last_name}",
                'email': obj.user.email
            }
        return None

    def get_course_details(self, obj):
        """Return course details for display"""
        if obj.course:
            return {
                'guid': str(obj.course.guid),
                'title': obj.course.title,
                'status': obj.course.status
            }
        return None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name in('created_by','created_at','deleted_at','deleted_by','updated_by','updated_at','enrolled_at','user_name','course_title','progress','guid','user_details','course_details'):
                field.required = False
    
    def get_user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"
    
    def get_progress(self, obj):
        return obj.course.course_progress(obj.user) if obj.course else 0
    
    def create(self, validated_data):
        """Convert user and course UUIDs to model instances"""
        user_uuid = validated_data.pop('user')
        course_uuid = validated_data.pop('course')
        
        try:
            user = Users.objects.get(guid=user_uuid)
            validated_data['user'] = user
        except Users.DoesNotExist:
            raise serializers.ValidationError({
                'user': f'User with GUID {user_uuid} does not exist.'
            })
        
        try:
            course = Courses.objects.get(guid=course_uuid)
            validated_data['course'] = course
        except Courses.DoesNotExist:
            raise serializers.ValidationError({
                'course': f'Course with GUID {course_uuid} does not exist.'
            })
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Convert UUIDs to model instances for updates"""
        if 'user' in validated_data:
            user_uuid = validated_data.pop('user')
            try:
                user = Users.objects.get(guid=user_uuid)
                validated_data['user'] = user
            except Users.DoesNotExist:
                raise serializers.ValidationError({
                    'user': f'User with GUID {user_uuid} does not exist.'
                })
        
        if 'course' in validated_data:
            course_uuid = validated_data.pop('course')
            try:
                course = Courses.objects.get(guid=course_uuid)
                validated_data['course'] = course
            except Courses.DoesNotExist:
                raise serializers.ValidationError({
                    'course': f'Course with GUID {course_uuid} does not exist.'
                })
        
        return super().update(instance, validated_data)


class UserProgressSerializer(serializers.ModelSerializer):
    user = serializers.UUIDField(write_only=True, help_text="User GUID - required for creation")
    module = serializers.UUIDField(write_only=True, help_text="Module GUID - required for creation")
    user_details = serializers.SerializerMethodField(read_only=True)
    module_details = serializers.SerializerMethodField(read_only=True)
    progress = serializers.SerializerMethodField()
    module_name = serializers.CharField(source='module.name', read_only=True)
    course_title = serializers.CharField(source='module.course.title', read_only=True)
    
    class Meta:
        model = UserModuleProgress
        fields = [
            'guid', 'user', 'module', 'user_details', 'module_details', 'module_name',
            'course_title', 'topics_completed', 'quiz_completed', 'completed_at', 'progress'
        ]
        read_only_fields = ['guid', 'progress', 'quiz_completed', 'completed_at']

    def get_user_details(self, obj):
        """Return user details for display"""
        if obj.user:
            return {
                'guid': str(obj.user.guid),
                'name': f"{obj.user.first_name} {obj.user.last_name}"
            }
        return None

    def get_module_details(self, obj):
        """Return module details for display"""
        if obj.module:
            return {
                'guid': str(obj.module.guid),
                'name': obj.module.name,
                'course_title': obj.module.course.title if obj.module.course else None
            }
        return None

    def get_progress(self, obj):
        # Add debugging to see actual values
        print(f"Serializer - Quiz completed: {obj.quiz_completed}")
        print(f"Serializer - Progress calculation: {obj.progress}")
        return obj.progress

    def to_representation(self, instance):
        """Override to ensure fresh data"""
        # Refresh the instance from database to get latest values
        instance.refresh_from_db()
        return super().to_representation(instance)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name in('topics_completed','quiz_completed','completed_at','progress','module_name','course_title','guid','user_details','module_details'):
                field.required = False
    
    def create(self, validated_data):
        """Convert user and module UUIDs to model instances"""
        user_uuid = validated_data.pop('user')
        module_uuid = validated_data.pop('module')
        
        try:
            user = Users.objects.get(guid=user_uuid)
            validated_data['user'] = user
        except Users.DoesNotExist:
            raise serializers.ValidationError({
                'user': f'User with GUID {user_uuid} does not exist.'
            })
        
        try:
            module = CourseModules.objects.get(guid=module_uuid)
            validated_data['module'] = module
        except CourseModules.DoesNotExist:
            raise serializers.ValidationError({
                'module': f'Module with GUID {module_uuid} does not exist.'
            })
        
        return super().create(validated_data)


class PublicCourseSerializer(serializers.ModelSerializer):
    """Simplified serializer for public course listings"""
    instructor_name = serializers.SerializerMethodField()
    instructor_image = serializers.SerializerMethodField()
    total_duration = serializers.CharField(read_only=True)
    
    class Meta:
        model = Courses
        fields = [
            'guid', 'title', 'description', 'image', 'tags', 'expertise_level',
            'isPaid', 'amount', 'currency', 'isFeatured', 'instructor_name', 
            'instructor_image', 'total_duration','created_at', 'updated_at'
        ]

    def get_instructor_name(self, obj):
        if obj.instructor:
            return f"{obj.instructor.first_name} {obj.instructor.last_name}"
        return None
    
    def get_instructor_image(self, obj):
        if obj.instructor and obj.instructor.image:
            return obj.instructor.image.url
        return None


# =============================================================================
# COURSE DISCUSSIONS SERIALIZER
# =============================================================================

class CourseDiscussionSerializer(serializers.ModelSerializer):
    course = serializers.UUIDField(write_only=True, help_text="Course GUID - required for creation")
    user = serializers.UUIDField(write_only=True, help_text="User GUID - required for creation")
    course_details = serializers.SerializerMethodField(read_only=True)
    user_details = serializers.SerializerMethodField(read_only=True)
    guid = serializers.UUIDField(read_only=True)
    
    class Meta:
        model = CourseDiscussions
        fields = [
            'guid', 'course', 'user', 'course_details', 'user_details', 'comment', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'guid']

    def get_course_details(self, obj):
        """Return course details for display"""
        if obj.course:
            return {
                'guid': str(obj.course.guid),
                'title': obj.course.title,
                'status': obj.course.status
            }
        return None

    def get_user_details(self, obj):
        """Return user details for display"""
        if obj.user:
            return {
                'guid': str(obj.user.guid),
                'name': f"{obj.user.first_name} {obj.user.last_name}",
                'email': obj.user.email,
                'image': obj.user.image.url if obj.user.image else None,
            }
        return None

    
    def validate(self, attrs):
        # Validate that course exists and is not deleted
        course_uuid = attrs.get('course')
        if course_uuid:
            try:
                course = Courses.objects.get(guid=course_uuid)
                if course.deleted_at:
                    raise serializers.ValidationError("Cannot comment on deleted course")
            except Courses.DoesNotExist:
                raise serializers.ValidationError("Course not found")
        return attrs
    
    def create(self, validated_data):
        """Convert course and user UUIDs to model instances"""
        course_uuid = validated_data.pop('course')
        user_uuid = validated_data.pop('user')
        
        try:
            course = Courses.objects.get(guid=course_uuid)
            validated_data['course'] = course
        except Courses.DoesNotExist:
            raise serializers.ValidationError({
                'course': f'Course with GUID {course_uuid} does not exist.'
            })
        
        try:
            user = Users.objects.get(guid=user_uuid)
            validated_data['user'] = user
        except Users.DoesNotExist:
            raise serializers.ValidationError({
                'user': f'User with GUID {user_uuid} does not exist.'
            })
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Convert UUIDs to model instances for updates"""
        if 'course' in validated_data:
            course_uuid = validated_data.pop('course')
            try:
                course = Courses.objects.get(guid=course_uuid)
                validated_data['course'] = course
            except Courses.DoesNotExist:
                raise serializers.ValidationError({
                    'course': f'Course with GUID {course_uuid} does not exist.'
                })
        
        if 'user' in validated_data:
            user_uuid = validated_data.pop('user')
            try:
                user = Users.objects.get(guid=user_uuid)
                validated_data['user'] = user
            except Users.DoesNotExist:
                raise serializers.ValidationError({
                    'user': f'User with GUID {user_uuid} does not exist.'
                })
        
        return super().update(instance, validated_data)
    
    @staticmethod
    def setup_eager_loading(queryset):
        """Optimize database queries with select_related and prefetch_related"""
        return queryset.select_related(
            'user',
            'course'
        ).order_by('-created_at')


# =============================================================================
# ADDITIONAL LEARNING SERIALIZERS
# =============================================================================

class TopicCompletionSerializer(serializers.Serializer):
    """Serializer for marking topics as complete"""
    topic_guid = serializers.UUIDField(required=True)
    
    def validate_topic_guid(self, value):
        """Validate that topic exists and is not deleted"""
        try:
            topic = ModuleTopics.objects.get(guid=value, deleted_at__isnull=True)
            return value
        except ModuleTopics.DoesNotExist:
            raise serializers.ValidationError("Topic not found or has been deleted")


class EnrolledCourseSerializer(serializers.ModelSerializer):
    """Serializer for courses in 'My Courses' view"""
    guid = serializers.UUIDField(source='course.guid', read_only=True)
    title = serializers.CharField(source='course.title', read_only=True)
    description = serializers.CharField(source='course.description', read_only=True)
    expertise_level = serializers.CharField(source='course.expertise_level', read_only=True)
    isPaid = serializers.BooleanField(source='course.isPaid', read_only=True)
    amount = serializers.DecimalField(source='course.amount', max_digits=10, decimal_places=2, read_only=True)
    currency = serializers.CharField(source='course.currency', read_only=True)
    total_duration = serializers.CharField(source='course.total_duration', read_only=True)
    image = serializers.SerializerMethodField()
    status = serializers.CharField(source='course.status', read_only=True)
    course_progress = serializers.SerializerMethodField()
    instructor = serializers.SerializerMethodField()
    
    class Meta:
        model = UsersCourseEnrollment
        fields = [
            'guid', 'title', 'description', 'expertise_level', 'isPaid', 'amount', 'currency', 'total_duration', 'image', 'status', 
            'enrolled_at', 'course_progress', 'instructor','created_at', 'updated_at'
        ]
        read_only_fields = ['enrolled_at', 'created_at', 'updated_at']
    
    def get_image(self, obj):
        if obj.course.image:
            return obj.course.image.url
        return None
    
    def get_course_progress(self, obj):
        # Get the user from context
        user = self.context.get('user')
        if user:
            return obj.course.course_progress(user)
        return 0
    
    def get_instructor(self, obj):
        instructor = obj.course.instructor
        if instructor:
            return {
                'name': f"{instructor.first_name} {instructor.last_name}",
                'email': instructor.email
            }
        return None
    
    @staticmethod
    def setup_eager_loading(queryset, user=None):
        """Optimize database queries"""
        return queryset.select_related(
            'course',
            'course__instructor'
        ).filter(
            deleted_at__isnull=True,
            course__deleted_at__isnull=True
        )


class UnenrollmentSerializer(serializers.Serializer):
    """Serializer for course unenrollment responses"""
    course_guid = serializers.UUIDField(read_only=True)
    course_title = serializers.CharField(read_only=True)
    unenrolled_at = serializers.DateTimeField(read_only=True)
    message = serializers.CharField(read_only=True)


# =============================================================================
# INSTRUCTOR QUIZ MANAGEMENT SERIALIZERS
# =============================================================================

class QuizSubmissionFeedbackSerializer(serializers.ModelSerializer):
    user = serializers.UUIDField(write_only=True, help_text="User GUID")
    quiz = serializers.UUIDField(write_only=True, help_text="Quiz GUID")
    instructor = serializers.UUIDField(write_only=True, help_text="Instructor GUID")
    user_details = serializers.SerializerMethodField(read_only=True)
    quiz_details = serializers.SerializerMethodField(read_only=True)
    instructor_details = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = QuizSubmissionFeedback
        fields = [
            'guid', 'user', 'quiz', 'instructor', 'user_details', 'quiz_details', 
            'instructor_details', 'feedback', 'score', 'created_at', 'updated_at'
        ]
        read_only_fields = ['guid', 'created_at', 'updated_at']

    def get_user_details(self, obj):
        if obj.user:
            return {
                'guid': str(obj.user.guid),
                'name': f"{obj.user.first_name} {obj.user.last_name}",
                'email': obj.user.email
            }
        return None

    def get_quiz_details(self, obj):
        if obj.quiz:
            return {
                'guid': str(obj.quiz.guid),
                'name': obj.quiz.name,
                'module_name': obj.quiz.module.name if obj.quiz.module else None
            }
        return None

    def get_instructor_details(self, obj):
        if obj.instructor:
            return {
                'guid': str(obj.instructor.guid),
                'name': f"{obj.instructor.first_name} {obj.instructor.last_name}",
                'email': obj.instructor.email
            }
        return None

    def create(self, validated_data):
        """Convert UUIDs to model instances"""
        user_uuid = validated_data.pop('user')
        quiz_uuid = validated_data.pop('quiz')
        instructor_uuid = validated_data.pop('instructor')
        
        try:
            user = Users.objects.get(guid=user_uuid)
            validated_data['user'] = user
        except Users.DoesNotExist:
            raise serializers.ValidationError({
                'user': f'User with GUID {user_uuid} does not exist.'
            })
        
        try:
            quiz = ModuleQuizes.objects.get(guid=quiz_uuid)
            validated_data['quiz'] = quiz
        except ModuleQuizes.DoesNotExist:
            raise serializers.ValidationError({
                'quiz': f'Quiz with GUID {quiz_uuid} does not exist.'
            })
            
        try:
            instructor = Users.objects.get(guid=instructor_uuid)
            validated_data['instructor'] = instructor
        except Users.DoesNotExist:
            raise serializers.ValidationError({
                'instructor': f'Instructor with GUID {instructor_uuid} does not exist.'
            })
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Convert UUIDs to model instances for updates"""
        if 'user' in validated_data:
            user_uuid = validated_data.pop('user')
            try:
                user = Users.objects.get(guid=user_uuid)
                validated_data['user'] = user
            except Users.DoesNotExist:
                raise serializers.ValidationError({
                    'user': f'User with GUID {user_uuid} does not exist.'
                })
        
        if 'quiz' in validated_data:
            quiz_uuid = validated_data.pop('quiz')
            try:
                quiz = ModuleQuizes.objects.get(guid=quiz_uuid)
                validated_data['quiz'] = quiz
            except ModuleQuizes.DoesNotExist:
                raise serializers.ValidationError({
                    'quiz': f'Quiz with GUID {quiz_uuid} does not exist.'
                })
        
        if 'instructor' in validated_data:
            instructor_uuid = validated_data.pop('instructor')
            try:
                instructor = Users.objects.get(guid=instructor_uuid)
                validated_data['instructor'] = instructor
            except Users.DoesNotExist:
                raise serializers.ValidationError({
                    'instructor': f'Instructor with GUID {instructor_uuid} does not exist.'
                })
        
        return super().update(instance, validated_data)


class UserQuizSubmissionSerializer(serializers.Serializer):
    """Serializer for displaying a user's complete quiz submission"""
    user = serializers.SerializerMethodField()
    quiz = serializers.SerializerMethodField()
    responses = serializers.SerializerMethodField()
    feedback = serializers.SerializerMethodField()
    total_questions = serializers.IntegerField(read_only=True)
    answered_questions = serializers.IntegerField(read_only=True)
    correct_answers = serializers.IntegerField(read_only=True)
    score_percentage = serializers.FloatField(read_only=True)
    submitted_at = serializers.DateTimeField(read_only=True)

    def get_user(self, obj):
        return {
            'guid': str(obj['user'].guid),
            'name': f"{obj['user'].first_name} {obj['user'].last_name}",
            'email': obj['user'].email
        }

    def get_quiz(self, obj):
        quiz = obj['quiz']
        return {
            'guid': str(quiz.guid),
            'name': quiz.name,
            'description': quiz.description,
            'module_name': quiz.module.name if quiz.module else None,
            'course_title': quiz.module.course.title if quiz.module and quiz.module.course else None
        }

    def get_responses(self, obj):
        """Get all responses with question details"""
        responses = obj['responses']
        response_data = []
        
        for response in responses:
            response_data.append({
                'guid': str(response.guid),
                'question': {
                    'guid': str(response.question.guid),
                    'question_text': response.question.question_text,
                    'question_type': response.question.question_type,
                    'options': response.question.options,
                    'correct_answer': response.question.correct_answer,
                    'marks': response.question.marks,
                    'order': response.question.order
                },
                'selected_answer': response.selected_answer,
                'is_correct': response.is_correct,
                'answered_at': response.answered_at
            })
        
        # Sort by question order
        response_data.sort(key=lambda x: x['question']['order'])
        return response_data

    def get_feedback(self, obj):
        """Get instructor feedback if it exists"""
        feedback = obj.get('feedback')
        if feedback:
            return {
                'guid': str(feedback.guid),
                'feedback': feedback.feedback,
                'score': feedback.score,
                'instructor': {
                    'name': f"{feedback.instructor.first_name} {feedback.instructor.last_name}",
                    'email': feedback.instructor.email
                },
                'created_at': feedback.created_at
            }
        return None


class QuizSubmissionSummarySerializer(serializers.Serializer):
    """Serializer for quiz submission summaries (for listing view)"""
    user = serializers.SerializerMethodField()
    total_questions = serializers.IntegerField()
    answered_questions = serializers.IntegerField()
    correct_answers = serializers.IntegerField()
    score_percentage = serializers.FloatField()
    submitted_at = serializers.DateTimeField()
    has_feedback = serializers.BooleanField()

    def get_user(self, obj):
        return {
            'guid': str(obj['user'].guid),
            'name': f"{obj['user'].first_name} {obj['user'].last_name}",
            'email': obj['user'].email
        }