from django.urls import include, re_path
from rest_framework.urlpatterns import format_suffix_patterns
from . import views

app_name = 'main'


urlpatterns = [
    # User
    re_path(r'^user/all/$', views.AllUsers.as_view(), name='all_users_by_entity'),
    re_path(r'^user/register/$', views.UserRegister.as_view(), name='user_register'),
    re_path(r'^user/by_guid/(?P<guid>[\w-]+)/$', views.OneUser.as_view(), name='one_user'),
    re_path(r'^user/admin_create/$', views.AdminCreateUser.as_view(), name='admin_create_user'),
    re_path(r'^user/admin_reactivate/$', views.AdminReactivateUser.as_view(), name='admin_reactivate_user'),
    re_path(r'^user/update_image/(?P<guid>[\w-]+)/$', views.UpdateUserProfileImage.as_view(), name='update_user_image'),
    re_path(r'^user/update/(?P<guid>[\w-]+)/$',views.UpdateUser.as_view(),name='update_user'),
    re_path(r'^user/delete/(?P<guid>[\w-]+)/$',views.DeleteUser.as_view(),name='delete_user'),

    re_path(r'^current_user/$', views.CurrentUser.as_view(), name='current_user'),

    # #user first time login
    re_path(r'^user/first_time_update/(?P<guid>[\w-]+)/$',views.FirstTimeUpdateUser.as_view(),name='first_time_update_user'),
    
    # Role
    re_path(r'^role/all/$', views.AllRole.as_view(), name='all_role'),
    re_path(r'^role/by_id/(?P<guid>[\w-]+)/$', views.OneRole.as_view(), name='one_role'),
    re_path(r'^role/create/$', views.CreateRole.as_view(), name='create_role'),
    re_path(r'^role/update/(?P<guid>[\w-]+)/$', views.UpdateRole.as_view(), name='update_role'),
    # re_path(r'^role/delete/(?P<guid>[\w-]+)/$', views.DeleteRole.as_view(), name='delete_role'),

    # Permissions
    re_path(r'^permissions/all/$', views.AllPermissions.as_view(), name='all_permissions'),
    re_path(r'^permission/by_id/(?P<guid>[\w-]+)/$', views.OnePermission.as_view(), name='one_permission'),
    re_path(r'^permissions/create/$', views.CreatePermissions.as_view(), name='create_permissions'),
    re_path(r'^permissions/update/(?P<guid>[\w-]+)/$', views.UpdatePermissions.as_view(), name='update_permissions'),
    re_path(r'^permissions/delete/(?P<guid>[\w-]+)/$', views.DeletePermissions.as_view(), name='delete_permissions'),


    #2FA
    # re_path(r'^2fa/confirm$', views.Confirm2fa.as_view(), name='confirm_2fa'),

    #audit logs
    re_path(r'^action/logs/$', views.ActionLog.as_view(), name='action_logs'),

    # =============================================================================
    # COURSE MANAGEMENT URLS
    # =============================================================================
    
    # Courses
    re_path(r'^courses/$', views.AllCourses.as_view(), name='all_courses'),
    re_path(r'^courses/create/$', views.CreateCourse.as_view(), name='create_course'),
    re_path(r'^courses/(?P<guid>[\w-]+)/$', views.OneCourse.as_view(), name='one_course'),
    re_path(r'^courses/(?P<guid>[\w-]+)/update/$', views.UpdateCourse.as_view(), name='update_course'),
    re_path(r'^courses/(?P<guid>[\w-]+)/delete/$', views.DeleteCourse.as_view(), name='delete_course'),
    
    # Course Modules
    re_path(r'^modules/$', views.AllCourseModules.as_view(), name='all_modules'),
    re_path(r'^courses/(?P<course_guid>[\w-]+)/modules/$', views.AllCourseModules.as_view(), name='course_modules'),
    re_path(r'^modules/create/$', views.CreateCourseModule.as_view(), name='create_module'),
    re_path(r'^modules/(?P<guid>[\w-]+)/$', views.OneCourseModule.as_view(), name='one_module'),
    re_path(r'^modules/(?P<guid>[\w-]+)/update/$', views.UpdateCourseModule.as_view(), name='update_module'),
    re_path(r'^modules/(?P<guid>[\w-]+)/delete/$', views.DeleteCourseModule.as_view(), name='delete_module'),
    
    # Module Topics
    re_path(r'^topics/$', views.AllModuleTopics.as_view(), name='all_topics'),
    re_path(r'^modules/(?P<module_guid>[\w-]+)/topics/$', views.AllModuleTopics.as_view(), name='module_topics'),
    re_path(r'^topics/create/$', views.CreateModuleTopic.as_view(), name='create_topic'),
    re_path(r'^topics/(?P<guid>[\w-]+)/$', views.OneModuleTopic.as_view(), name='one_topic'),
    re_path(r'^topics/(?P<guid>[\w-]+)/update/$', views.UpdateModuleTopic.as_view(), name='update_topic'),
    re_path(r'^topics/(?P<guid>[\w-]+)/delete/$', views.DeleteModuleTopic.as_view(), name='delete_topic'),
    
    # Module Quizzes
    re_path(r'^quizzes/$', views.AllModuleQuizzes.as_view(), name='all_quizzes'),
    re_path(r'^modules/(?P<module_guid>[\w-]+)/quizzes/$', views.AllModuleQuizzes.as_view(), name='module_quizzes'),
    re_path(r'^quizzes/create/$', views.CreateModuleQuiz.as_view(), name='create_quiz'),
    re_path(r'^quizzes/(?P<guid>[\w-]+)/$', views.OneModuleQuiz.as_view(), name='one_quiz'),
    re_path(r'^quizzes/(?P<guid>[\w-]+)/update/$', views.UpdateModuleQuiz.as_view(), name='update_quiz'),
    re_path(r'^quizzes/(?P<guid>[\w-]+)/delete/$', views.DeleteModuleQuiz.as_view(), name='delete_quiz'),
    
    # Quiz Questions
    re_path(r'^questions/$', views.AllQuizQuestions.as_view(), name='all_questions'),
    re_path(r'^quizzes/(?P<quiz_guid>[\w-]+)/questions/$', views.AllQuizQuestions.as_view(), name='quiz_questions'),
    re_path(r'^questions/create/$', views.CreateQuizQuestion.as_view(), name='create_question'),
    re_path(r'^questions/(?P<guid>[\w-]+)/$', views.OneQuizQuestion.as_view(), name='one_question'),
    re_path(r'^questions/(?P<guid>[\w-]+)/update/$', views.UpdateQuizQuestion.as_view(), name='update_question'),
    re_path(r'^questions/(?P<guid>[\w-]+)/delete/$', views.DeleteQuizQuestion.as_view(), name='delete_question'),

    # =============================================================================
    # STUDENT/LEARNING URLS
    # =============================================================================
    
    # Enrollment
    re_path(r'^enroll/$', views.EnrollInCourse.as_view(), name='enroll_course'),
    re_path(r'^unenroll/(?P<course_guid>[\w-]+)/$', views.UnenrollFromCourse.as_view(), name='unenroll_course'),
    re_path(r'^my-courses/$', views.MyCourses.as_view(), name='my_courses'),
    
    # Progress
    re_path(r'^courses/(?P<course_guid>[\w-]+)/progress/$', views.CourseProgress.as_view(), name='course_progress'),
    re_path(r'^topic/complete/$', views.MarkTopicComplete.as_view(), name='mark_topic_complete'),
    
    # Quiz Responses
    re_path(r'^quiz/submit/$', views.SubmitQuizResponse.as_view(), name='submit_quiz_response'),
    re_path(r'^quizzes/(?P<quiz_guid>[\w-]+)/results/$', views.GetQuizResults.as_view(), name='quiz_results'),

    # =============================================================================
    # PUBLIC/BROWSE URLS
    # =============================================================================
    
    re_path(r'^public/courses/$', views.PublicCourses.as_view(), name='public_courses'),
    re_path(r'^public/featured-courses/$', views.FeaturedCourses.as_view(), name='featured_courses'),

    # =============================================================================
    # INSTRUCTOR/ADMIN URLS
    # =============================================================================
    
    re_path(r'^courses/(?P<course_guid>[\w-]+)/enrollments/$', views.CourseEnrollments.as_view(), name='course_enrollments'),
    
    # Instructor Quiz Management
    re_path(r'^courses/(?P<course_guid>[\w-]+)/quizzes/submissions/$', views.CourseQuizSubmissions.as_view(), name='course_quiz_submissions'),
    re_path(r'^quizzes/(?P<quiz_guid>[\w-]+)/submissions/$', views.QuizSubmissions.as_view(), name='quiz_submissions'),
    re_path(r'^quiz-submissions/(?P<user_guid>[\w-]+)/(?P<quiz_guid>[\w-]+)/$', views.UserQuizSubmissionDetail.as_view(), name='user_quiz_submission_detail'),
    re_path(r'^quiz-submissions/(?P<user_guid>[\w-]+)/(?P<quiz_guid>[\w-]+)/feedback/$', views.AddQuizFeedback.as_view(), name='add_quiz_feedback'),

    # =============================================================================
    # COURSE DISCUSSION URLS
    # =============================================================================
    
    # Course Discussions
    # re_path(r'^discussions/$', views.AllCourseDiscussions.as_view(), name='all_discussions'),
    re_path(r'^courses/(?P<course_guid>[\w-]+)/discussions/$', views.AllCourseDiscussions.as_view(), name='course_discussions'),
    re_path(r'^discussions/create/$', views.CreateCourseDiscussion.as_view(), name='create_discussion'),
    re_path(r'^discussions/(?P<guid>[\w-]+)/$', views.OneCourseDiscussion.as_view(), name='one_discussion'),
    re_path(r'^discussions/(?P<guid>[\w-]+)/update/$', views.UpdateCourseDiscussion.as_view(), name='update_discussion'),
    re_path(r'^discussions/(?P<guid>[\w-]+)/delete/$', views.DeleteCourseDiscussion.as_view(), name='delete_discussion'),


]