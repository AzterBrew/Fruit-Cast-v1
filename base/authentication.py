from django.contrib.auth import get_user_model
User = get_user_model()
from base.models import UserInformation  

class EmailAuthBackend:
    def authenticate(self, request, username=None, password=None):
        user = User.objects.filter(email=username).first()  # Avoids multiple matches
        if user and user.check_password(password):
            return user
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

class PhoneAuthBackend:
    def authenticate(self, request, username=None, password=None):
        try:
            if not username.isdigit():
                return None
            
            extended = UserInformation.objects.filter(phone_number=username).first()  
            if extended:
                user = extended.user
                if user.check_password(password):
                    return user
        except UserInformation.DoesNotExist:
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
        

