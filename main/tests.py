import uuid

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from main.models import Courses, Organizations, Role, Users, UsersCourseEnrollment


class OrganizationBulkEnrollUsersTests(APITestCase):
    endpoint = '/api/main/v1/organization/enrollments/bulk/'

    def setUp(self):
        self.org_admin_role = Role.objects.create(name='ORG_ADMIN')
        self.user_role = Role.objects.create(name='USER')

        self.organization = Organizations.objects.create(
            member_id='ORG-001',
            org_name='Acme Flowers',
            is_active=True
        )
        self.other_organization = Organizations.objects.create(
            member_id='ORG-002',
            org_name='Other Flowers',
            is_active=True
        )

        self.org_admin = self._create_user(
            email='admin@acme.test',
            username='org_admin',
            role=self.org_admin_role,
            organization=self.organization
        )
        self.member_one = self._create_user(
            email='member1@acme.test',
            username='member_one',
            role=self.user_role,
            organization=self.organization
        )
        self.member_two = self._create_user(
            email='member2@acme.test',
            username='member_two',
            role=self.user_role,
            organization=self.organization
        )
        self.outsider = self._create_user(
            email='outsider@other.test',
            username='outsider',
            role=self.user_role,
            organization=self.other_organization
        )
        self.user_without_org = self._create_user(
            email='solo@test.com',
            username='solo_user',
            role=self.org_admin_role,
            organization=None
        )

        self.course_one = Courses.objects.create(
            title='Post Harvest Basics',
            status='published'
        )
        self.course_two = Courses.objects.create(
            title='Greenhouse Safety',
            status='published'
        )

    def _create_user(self, email, username, role, organization):
        return Users.objects.create_user(
            email=email,
            username=username,
            password='testpass123',
            first_name='Test',
            last_name='User',
            role=role,
            organization=organization
        )

    def test_org_admin_can_bulk_enroll_users_in_courses(self):
        UsersCourseEnrollment.objects.create(
            user=self.member_one,
            course=self.course_one,
            created_by=str(self.org_admin.guid)
        )
        soft_deleted_enrollment = UsersCourseEnrollment.objects.create(
            user=self.member_two,
            course=self.course_one,
            created_by=str(self.org_admin.guid)
        )
        soft_deleted_enrollment.deleted_at = timezone.now()
        soft_deleted_enrollment.deleted_by = str(self.org_admin.guid)
        soft_deleted_enrollment.save()

        self.client.force_authenticate(user=self.org_admin)
        invalid_course_guid = uuid.uuid4()

        response = self.client.post(
            self.endpoint,
            {
                'user_guids': [
                    str(self.member_one.guid),
                    str(self.member_two.guid),
                    str(self.outsider.guid),
                ],
                'course_guids': [
                    str(self.course_one.guid),
                    str(self.course_two.guid),
                    str(invalid_course_guid),
                ]
            },
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['created_count'], 2)
        self.assertEqual(response.data['data']['reactivated_count'], 1)
        self.assertEqual(response.data['data']['already_enrolled_count'], 1)
        self.assertEqual(response.data['data']['invalid_user_guids'], [str(self.outsider.guid)])
        self.assertEqual(response.data['data']['invalid_course_guids'], [str(invalid_course_guid)])

        self.assertTrue(
            UsersCourseEnrollment.objects.filter(
                user=self.member_two,
                course=self.course_one,
                deleted_at__isnull=True
            ).exists()
        )
        self.assertTrue(
            UsersCourseEnrollment.objects.filter(
                user=self.member_one,
                course=self.course_two,
                deleted_at__isnull=True
            ).exists()
        )
        self.assertFalse(
            UsersCourseEnrollment.objects.filter(
                user=self.outsider,
                course=self.course_one
            ).exists()
        )

    def test_non_org_admin_cannot_bulk_enroll_users(self):
        self.client.force_authenticate(user=self.member_one)

        response = self.client.post(
            self.endpoint,
            {
                'user_guids': [str(self.member_one.guid)],
                'course_guids': [str(self.course_one.guid)]
            },
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_without_organization_cannot_bulk_enroll_users(self):
        self.client.force_authenticate(user=self.user_without_org)

        response = self.client.post(
            self.endpoint,
            {
                'user_guids': [str(self.member_one.guid)],
                'course_guids': [str(self.course_one.guid)]
            },
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
