# despesas/auth_backends.py
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q
from .models import UsuarioPerfil

User = get_user_model()

def _normaliza_cpf(cpf: str) -> str:
    return "".join(ch for ch in cpf if ch.isdigit())

class CPFOrUsernameBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        username = username.strip()

        user = None
        # tenta por username/email padrão
        try:
            user = User.objects.get(Q(username__iexact=username) | Q(email__iexact=username))
        except User.DoesNotExist:
            # tenta por CPF no perfil
            cpf = _normaliza_cpf(username)
            if cpf:
                try:
                    perfil = UsuarioPerfil.objects.select_related("user").get(cpf=cpf)
                    user = perfil.user
                except UsuarioPerfil.DoesNotExist:
                    return None

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
