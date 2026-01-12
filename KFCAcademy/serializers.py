
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from main.models import Permission, Users
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from rest_framework.exceptions import AuthenticationFailed

def get_role_permissions(user):
    """
    Collects all permissions from the user's roles.
    Returns a dict with 'role' and 'permissions'.
    """
    roles = getattr(user, "role_set", None)
    if roles is None:
        return {"role": None, "permissions": []}

    permissions = []
    role_names = []

    for role in roles.all().prefetch_related("permission__module_id__platform_standard_id"):
        role_names.append(role.name)  # assuming Role has a `name` field
        for perm in role.permission.all():
            permissions.append({
                "action": perm.action,
                "module": perm.module_id.name if perm.module_id else None,
                "standard": (
                    perm.module_id.platform_standard_id.name
                    if perm.module_id and perm.module_id.platform_standard_id
                    else None
                )
            })

    return {
        "role": role_names if len(role_names) > 1 else (role_names[0] if role_names else None),
        "permissions": permissions
    }

class OTPLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    print("user email field initialized")
    print(email)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")
        print("Validating user with email:", email)
        print("Validating user with password:", password)

        user = authenticate(email=email, password=password)
        print("Authenticated user:", user)
        if not user or not user.is_active:
            raise AuthenticationFailed("Invalid Email or Password")

        attrs["user"] = user
        return attrs
    


class PreTokenObtainLifetimeSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        print("At validate")
        data = super().validate(attrs)
        print(self.user)

        my_user = Users.objects.filter(pk=self.user.id).first()
        if my_user:
            if my_user.is_active == True:
                data['user'] = my_user
                return data
            else:
                return []
        else:
            return []
        
class TokenObtainLifetimeSerializer(TokenObtainPairSerializer):
    otp = serializers.CharField()

    def validate(self, attrs):
        data = super().validate(attrs)

        my_user = Users.objects.filter(pk=self.user.id).first()
        if my_user:
            if my_user.is_active == True:
                refresh = self.get_token(self.user)
                role_info = get_role_permissions(my_user)
                refresh["role"] = role_info["role"]
                # refresh["permissions"] = role_info["permissions"]

                data['refresh'] = str(refresh)
                data['access'] = str(refresh.access_token)
                data['token_type'] = 'Bearer'
                data['expires_in'] = refresh.access_token.payload['exp'] - refresh.access_token.payload['iat']
                
            
                # if my_user:
                #     # use user serelizor or parse required fields
                data['user'] = my_user
                # data['user'] = {
                #     "id": my_user.id,
                #     "guid": str(my_user.guid),
                #     "username": my_user.username,
                #     "email": my_user.email,
                #     "role": role_info["role"]
                # }
                return data
            else:
                return []
        else:
            return []


class TokenRefreshLifetimeSerializer(TokenRefreshSerializer):

    def validate(self, attrs):
        try:
            data = super().validate(attrs)

            refresh = RefreshToken(attrs['refresh'])
            access_token = refresh.access_token

            # Add custom fields
            data['access'] = str(access_token)
            data['token_type'] = 'Bearer'
            data['expires_in'] = access_token.payload['exp'] - access_token.payload['iat']
            data['refresh'] = str(refresh)

            # ✅ Get user from refresh token
            # user_id = refresh.payload.get('user_id')
            # my_user = Users.objects.filter(pk=user_id).first()

            # if my_user:
            #     data['user'] = my_user

            return data
        except TokenError as e:
            # Return 401 instead of 400 when token is expired/invalid
            raise AuthenticationFailed(detail="Token is invalid or expired", code="token_not_valid")