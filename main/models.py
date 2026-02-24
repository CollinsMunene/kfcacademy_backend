from datetime import timedelta
from django.utils import timezone
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from io import BytesIO
from django.core.files import File
from PIL import Image
from django.contrib.postgres.fields import ArrayField
import uuid
from django.db import connection


class SoftDeleteManager(models.Manager):
    """Manager to exclude soft-deleted objects"""
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class AllObjectsManager(models.Manager):
    """Manager to include all objects (including soft-deleted)"""
    def get_queryset(self):
        return super().get_queryset()

# Create your models here.

class Permission(models.Model):
    guid = models.UUIDField(default=uuid.uuid4, editable=False,unique=True)
    action = models.CharField(max_length=200,blank=False,null=False)
    description = models.TextField(blank=True,null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=200,blank=True,null=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=200,blank=True,null=True)
    deleted_at = models.DateTimeField(blank=True,null=True)
    deleted_by = models.CharField(max_length=200,blank=True,null=True)

    # Managers
    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    def __str__(self):
        return f'{self.action}'

    class Meta:
        db_table = 'permission'
        indexes = [
            models.Index(fields=['action']),
            models.Index(fields=['created_at']),
        ]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
    
class Role(models.Model):
    guid = models.UUIDField(default=uuid.uuid4, editable=False,unique=True)
    name = models.CharField(max_length=200,blank=False,null=False)
    description = models.TextField(blank=True,null=True)
    permission = models.ManyToManyField(Permission, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=200,blank=True,null=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=200,blank=True,null=True)
    deleted_at = models.DateTimeField(blank=True,null=True)
    deleted_by = models.CharField(max_length=200,blank=True,null=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'role'
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['created_at']),
        ]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

def user_upload_to(instance, filename):
    return 'user_profile_image/{}'.format(filename)

def get_default_role():
    try:
        if "role" in connection.introspection.table_names():
            return Role.objects.get(name="USER")
    except:
        pass
    return None


class Users(AbstractUser):
    guid = models.UUIDField(default=uuid.uuid4, editable=False,unique=True)
    image = models.ImageField(default='default.png', blank=True, null=True, upload_to=user_upload_to)
    email = models.EmailField('email address', unique = True,blank=True,null=True)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    first_name = models.CharField(max_length=40, unique=False, default='')
    last_name = models.CharField(max_length=40, unique=False, default='',blank=True)
    phone_number = models.CharField(max_length = 20,blank=True,null=True)
    profession = models.CharField(max_length=200,blank=True,null=True)
    gender = models.CharField(max_length=20,blank=True,null=True)
    age = models.IntegerField(blank=True,null=True)
    bio = models.TextField(blank=True,null=True)
    password = models.CharField(max_length=300, blank=False, null=False)
    is_active = models.BooleanField(default=True)
    is_first_time_login = models.BooleanField(default=True)
    role = models.ForeignKey(Role,on_delete=models.SET_DEFAULT, default=get_default_role,blank=True,null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=200,blank=True,null=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=200,blank=True,null=True)
    deleted_at = models.DateTimeField(blank=True,null=True)
    deleted_by = models.CharField(max_length=200,blank=True,null=True)

    def __str__(self):
        return "{}".format(self.email)
    
    class Meta:
        db_table = 'users'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['guid']),
            models.Index(fields=['is_active']),
            models.Index(fields=['role']),
            models.Index(fields=['created_at']),
        ]
    
    def save(self, *args, **kwargs):
        # Track if image was changed
        image_changed = False
        if self.pk:
            try:
                old_instance = Users.objects.get(pk=self.pk)
                image_changed = old_instance.image != self.image
            except Users.DoesNotExist:
                image_changed = True
        else:
            image_changed = bool(self.image)

        super(Users, self).save(*args, **kwargs)

        # Process image in background if it changed
        if image_changed and self.image:
            try:
                from KFCAcademy.tasks import process_user_image
                process_user_image.delay(self.pk)
            except ImportError:
                # Fallback to synchronous processing if Celery not available
                self._process_image_sync()

    def _process_image_sync(self):
        """Synchronous image processing fallback"""
        if not self.image:
            return
            
        try:
            from django.core.files.storage import default_storage
            from django.core.files.base import ContentFile
            
            # Validate file size (max 10MB)
            if self.image.size > 10 * 1024 * 1024:
                print(f"Image too large: {self.image.size} bytes")
                return

            im = Image.open(self.image)
            im = im.convert('RGB')

            output_size = (300, 300)
            im.thumbnail(output_size)

            thumb_io = BytesIO()
            im.save(thumb_io, 'PNG', quality=85)

            # Save processed image
            self.image.save(
                self.image.name, 
                ContentFile(thumb_io.getvalue()), 
                save=False
            )
            
            # Only update image field to avoid recursion
            Users.objects.filter(pk=self.pk).update(image=self.image)
            
        except Exception as e:
            print(f"Error processing image: {e}")
            # Don't raise exception to avoid breaking user creation

def course_image_upload_to(instance, filename):
    return 'course_image/{}'.format(filename)

class Courses(models.Model):
    guid = models.UUIDField(default=uuid.uuid4, editable=False,unique=True)
    title = models.CharField(max_length=200,blank=False,null=False)
    description = models.TextField(blank=True,null=True)
    category = models.CharField(max_length=200,blank=True,null=True)
    image = models.ImageField(default='course_image/default_course.png', blank=True, null=True, upload_to=course_image_upload_to)
    tags = ArrayField(models.CharField(max_length=100), blank=True, default=list)
    expertise_level = models.CharField(max_length=100,blank=True,null=True)
    prerequisites = ArrayField(models.CharField(max_length=100), blank=True, default=list)
    objectives = ArrayField(models.CharField(max_length=200), blank=True, default=list)
    isPaid = models.BooleanField(default=False)
    amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    currency = models.CharField(max_length=10,blank=True,null=True)
    isFeatured = models.BooleanField(default=False)
    instructor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,blank=True,null=True,related_name='instructor')
    status = models.CharField(max_length=200,blank=False,null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=200,blank=True,null=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=200,blank=True,null=True)
    deleted_at = models.DateTimeField(blank=True,null=True)
    deleted_by = models.CharField(max_length=200,blank=True,null=True)

    class Meta:
        db_table = 'courses'
        indexes = [
            models.Index(fields=['title']),
            models.Index(fields=['status']),
            models.Index(fields=['instructor']),
            models.Index(fields=['isPaid']),
            models.Index(fields=['isFeatured']),
            models.Index(fields=['expertise_level']),
            models.Index(fields=['created_at']),
        ]
    
    @property
    def total_duration(self):
        """Compute total duration across all modules and topics, return as string."""
        from django.db.models import Sum
        from django.core.cache import cache

        # Use caching to avoid repeated calculations
        cache_key = f"course_duration_{self.guid}"
        cached_duration = cache.get(cache_key)
        if cached_duration is not None:
            return cached_duration

        # Optimized query to sum all durations at once
        total_duration = self.coursemodules_set.aggregate(
            total=Sum('moduletopics__duration')
        )['total']

        # Debugging log
        print(f"Debug: Aggregated total_duration for course {self.guid}: {total_duration}")

        if not total_duration:
            result = "0h"
        else:
            # Convert total duration to weeks, days, hours
            total_seconds = int(total_duration.total_seconds())
            weeks, remainder = divmod(total_seconds, 604800)  # 7 * 24 * 3600
            days, remainder = divmod(remainder, 86400)
            hours, _ = divmod(remainder, 3600)

            parts = []
            if weeks > 0:
                parts.append(f"{weeks}w")
            if days > 0:
                parts.append(f"{days}d")
            if hours > 0:
                parts.append(f"{hours}h")

            result = " ".join(parts) or "0h"

        # Cache for 1 hour
        cache.set(cache_key, result, 3600)
        return result
    
    def course_progress(self, user):
        """Return average module progress for this user."""
        from django.core.cache import cache
        
        # Use caching for user progress
        cache_key = f"course_progress_{self.guid}_{user.guid}"
        cached_progress = cache.get(cache_key)
        if cached_progress is not None:
            return cached_progress

        modules = self.coursemodules_set.all()
        if not modules:
            return 0

        total = 0
        for module in modules:
            total += module.module_progress(user)
        
        result = round(total / modules.count(), 2)
        
        # Cache for 10 minutes (progress changes frequently)
        cache.set(cache_key, result, 600)
        return result

    def save(self, *args, **kwargs):
        from django.core.cache import cache
        # Invalidate duration cache when course is updated
        cache.delete(f"course_duration_{self.guid}")
        # Note: In production, consider using cache patterns for wildcard deletion
        super().save(*args, **kwargs)

class CourseModules(models.Model):
    guid = models.UUIDField(default=uuid.uuid4, editable=False,unique=True)
    name = models.CharField(max_length=200,blank=False,null=False)
    description = models.TextField(blank=True,null=True)
    course = models.ForeignKey(Courses,on_delete=models.CASCADE)
    order = models.IntegerField(blank=False,null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=200,blank=True,null=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=200,blank=True,null=True)
    deleted_at = models.DateTimeField(blank=True,null=True)
    deleted_by = models.CharField(max_length=200,blank=True,null=True)

    class Meta:
        db_table = 'course_modules'
        indexes = [
            models.Index(fields=['course', 'order']),
            models.Index(fields=['name']),
        ]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
    
    def module_progress(self, user):
        """Return module progress (0-100%) for a given user."""
        try:
            user_progress = UserModuleProgress.objects.get(user=user, module=self)
            return user_progress.progress  # property in UserModuleProgress
        except UserModuleProgress.DoesNotExist:
            return 0


class ModuleTopics(models.Model):
    guid = models.UUIDField(default=uuid.uuid4, editable=False,unique=True)
    name = models.CharField(max_length=200,blank=False,null=False)
    description = models.TextField(blank=True,null=True)
    files = ArrayField(models.CharField(max_length=300,blank=True),default=list,blank = True,null = True)
    files_description =  models.TextField(blank=True,null=True)
    videos = ArrayField(models.CharField(max_length=300,blank=True),default=list,blank = True,null = True)
    videos_description =  models.TextField(blank=True,null=True)
    images = ArrayField(models.CharField(max_length=300,blank=True),default=list,blank = True,null = True)
    images_description =  models.TextField(blank=True,null=True)
    duration = models.DurationField(help_text="Enter duration as HH:MM:SS",blank = True,null = True)
    module = models.ForeignKey(CourseModules,on_delete=models.CASCADE)
    order = models.IntegerField(blank=False,null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=200,blank=True,null=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=200,blank=True,null=True)
    deleted_at = models.DateTimeField(blank=True,null=True)
    deleted_by = models.CharField(max_length=200,blank=True,null=True)


    class Meta:
        db_table = 'module_topics'
        indexes = [
            models.Index(fields=['module', 'order']),
            models.Index(fields=['name']),
        ]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # Clear course duration cache when topic duration changes
        from django.core.cache import cache
        cache_key = f"course_duration_{self.module.course.guid}"
        cache.delete(cache_key)

class ModuleQuizes(models.Model):
    guid = models.UUIDField(default=uuid.uuid4, editable=False,unique=True)
    name = models.CharField(max_length=200,blank=False,null=False)
    description = models.TextField(blank=True,null=True)
    module = models.ForeignKey(CourseModules,on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=200,blank=True,null=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=200,blank=True,null=True)
    deleted_at = models.DateTimeField(blank=True,null=True)
    deleted_by = models.CharField(max_length=200,blank=True,null=True)

    class Meta:
        db_table = 'module_quizes'
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)


class QuizQuestions(models.Model):
    guid = models.UUIDField(default=uuid.uuid4, editable=False,unique=True)
    quiz = models.ForeignKey(ModuleQuizes,on_delete=models.CASCADE)
    question_type = models.CharField(
        max_length=50,
        choices=[("mcq", "Multiple Choice"), ("tf", "True/False"), ("text", "Text Response")],
        default="mcq"
    )
    question_text = models.TextField()
    options = ArrayField(models.CharField(max_length=255), blank=False, default=list)  # e.g ["A","B","C","D"]
    correct_answer = models.CharField(max_length=255)  # must be one of options
    marks = models.IntegerField(default=1)
    order = models.IntegerField(blank=False,null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=200,blank=True,null=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=200,blank=True,null=True)
    deleted_at = models.DateTimeField(blank=True,null=True)
    deleted_by = models.CharField(max_length=200,blank=True,null=True)

    class Meta:
        db_table = 'quiz_questions'
    
    def clean(self):
        from django.core.exceptions import ValidationError
        # Validate that correct_answer is in options
        if self.correct_answer and self.correct_answer not in self.options:
            raise ValidationError({
                'correct_answer': 'Correct answer must be one of the available options.'
            })
        
        # Validate that options are not empty for MCQ
        if self.question_type == 'mcq' and not self.options:
            raise ValidationError({
                'options': 'Options are required for multiple choice questions.'
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

class QuizResponses(models.Model):
    guid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="user_responses", on_delete=models.CASCADE)
    question = models.ForeignKey(QuizQuestions, related_name="responses", on_delete=models.CASCADE)
    selected_answer = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)
    answered_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=200,blank=True,null=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=200,blank=True,null=True)
    deleted_at = models.DateTimeField(blank=True,null=True)
    deleted_by = models.CharField(max_length=200,blank=True,null=True)

    def save(self, *args, **kwargs):
        if self.selected_answer not in self.question.options:
            raise ValueError("Selected answer must be one of the available options.")
        self.is_correct = self.selected_answer == self.question.correct_answer
        super().save(*args, **kwargs)

        try:
            # Fixed: Correct relationship path quiz -> module
            progress, created = UserModuleProgress.objects.get_or_create(
                user=self.user,
                module=self.question.quiz.module
            )
            progress.update_quiz_progress()
        except Exception as e:
            # Optional: log
            print(f"Error updating module progress: {e}")

    def __str__(self):
        return f"{self.question.question_text[:30]}"

    class Meta:
        db_table = 'quiz_question_response'
        indexes = [
            models.Index(fields=['user', 'question']),
            models.Index(fields=['is_correct']),
            models.Index(fields=['answered_at']),
        ]

class QuizSubmissionFeedback(models.Model):
    guid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="quiz_feedbacks_received", on_delete=models.CASCADE)
    quiz = models.ForeignKey(ModuleQuizes, related_name="quiz_feedbacks", on_delete=models.CASCADE)
    instructor = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="quiz_feedbacks_given", on_delete=models.CASCADE)
    feedback = models.TextField(help_text="Instructor feedback on quiz submission")
    score = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, help_text="Overall score for the quiz submission")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=200, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=200, blank=True, null=True)
    deleted_at = models.DateTimeField(blank=True, null=True)
    deleted_by = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        db_table = 'quiz_submission_feedback'
        unique_together = ('user', 'quiz')  # One feedback per user per quiz
        indexes = [
            models.Index(fields=['user', 'quiz']),
            models.Index(fields=['instructor']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Feedback for {self.user.email} on {self.quiz.name}"

class CourseDiscussions(models.Model):
    guid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    course = models.ForeignKey(Courses, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    comment = models.TextField(blank=False, null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=200,blank=True,null=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=200,blank=True,null=True)
    deleted_at = models.DateTimeField(blank=True,null=True)
    deleted_by = models.CharField(max_length=200,blank=True,null=True)

    class Meta:
        db_table = 'course_discussions'
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

class UserModuleProgress(models.Model):
    guid = models.UUIDField(default=uuid.uuid4, editable=False,unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    module = models.ForeignKey(CourseModules, on_delete=models.CASCADE)
    topics_completed = ArrayField(
        models.UUIDField(), blank=True, default=list
    )
    quiz_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'user_module_progress'
        unique_together = ('user', 'module')
        indexes = [
            models.Index(fields=['user', 'module']),
            models.Index(fields=['quiz_completed']),
            models.Index(fields=['completed_at']),
        ]
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        
        # Clear course progress cache when module progress changes
        from django.core.cache import cache
        cache_key = f"course_progress_{self.module.course.guid}_{self.user.guid}"
        cache.delete(cache_key)
    
    def update_quiz_progress(self):
        """
        Checks if user has answered all quiz questions for this module,
        and marks quiz_completed = True if so.
        """
        # Fixed: Correct relationship path through quiz, include deleted_at filter
        total_questions = QuizQuestions.objects.filter(
            quiz__module=self.module, 
            deleted_at__isnull=True
        ).count()
        answered_questions = QuizResponses.objects.filter(
            user=self.user,
            question__quiz__module=self.module,
            deleted_at__isnull=True
        ).count()
        print(f"Total questions: {total_questions}, Answered questions: {answered_questions}")
        print(f"Current quiz_completed status: {self.quiz_completed}")

        if total_questions > 0 and answered_questions >= total_questions:
            print(f"Setting quiz_completed to True for user {self.user.email}")
            self.quiz_completed = True
            self.completed_at = self.completed_at or timezone.now()
            self.save(update_fields=['quiz_completed', 'completed_at'])
            print(f"Quiz completed status after save: {self.quiz_completed}")
        else:
            print(f"Quiz not completed yet. Need {total_questions} answers, have {answered_questions}")
    
    @property
    def topics_completed_guids(self):
        """Return list of completed topic GUIDs"""
        return self.topics_completed or []
    
    @property
    def progress(self):
        total_topics = self.module.moduletopics_set.count()
        if total_topics == 0:
            topic_percent = 0
        else:
            topic_percent = len(self.topics_completed_guids) / total_topics

        quiz_percent = 1 if self.quiz_completed else 0

        # Weighted example: 70% topics, 30% quiz
        return round((topic_percent * 0.7 + quiz_percent * 0.3) * 100, 2)

class UsersCourseEnrollment(models.Model):
    guid = models.UUIDField(default=uuid.uuid4, editable=False,unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    course = models.ForeignKey(Courses,on_delete=models.CASCADE)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=200,blank=True,null=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=200,blank=True,null=True)
    deleted_at = models.DateTimeField(blank=True,null=True)
    deleted_by = models.CharField(max_length=200,blank=True,null=True)

    class Meta:
        db_table = 'users_course_enrollment'
        unique_together = ('user', 'course')

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

class Main2FALog(models.Model): 
    guid = models.UUIDField(default=uuid.uuid4, editable=False,unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    otp = models.CharField(max_length=10,blank=False,null=False)
    reason = models.CharField(max_length=200,blank=False,null=False)
    status = models.CharField(max_length=200,blank=False,null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=200,blank=True,null=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=200,blank=True,null=True)
    deleted_at = models.DateTimeField(blank=True,null=True)
    deleted_by = models.CharField(max_length=200,blank=True,null=True)

    class Meta:
        db_table = 'main_2fa_log'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)


class ActionLogs(models.Model):
    guid = models.UUIDField(default=uuid.uuid4, editable=False,unique=True)
    initiator_id = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,blank=False,null=False)
    action = models.CharField(max_length=400,blank=True,null=True)
    extra_details = models.JSONField(null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=200,blank=True,null=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=200,blank=True,null=True)
    deleted_at = models.DateTimeField(blank=True,null=True)
    deleted_by = models.CharField(max_length=200,blank=True,null=True)

    def __str__(self):
        return f'{self.initiator_id.username} - {self.action} - {self.created_at}'

    class Meta:
        db_table = 'action_log'
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)