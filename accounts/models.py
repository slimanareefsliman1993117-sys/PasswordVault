from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.db.models.functions import Lower
from cryptography.fernet import Fernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from .demo import DEMO_EMAIL, DEMO_USERNAME
import logging
logger = logging.getLogger(__name__)
def get_fernet():
    """Never generate ephemeral keys: recovery must survive process restarts."""
    try:
        return Fernet(settings.RECOVERY_CODE_KEY.encode())
    except (ValueError, TypeError, AttributeError) as exc:
        raise ImproperlyConfigured('RECOVERY_CODE_KEY must be a persistent Fernet key.') from exc

# ==============================================================================
class CustomUserManager(UserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email).strip().lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('email_verified', True)
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self.create_user(email, password, **extra_fields)

    def get_by_natural_key(self, username):
        return self.get(email__iexact=username.strip())
# ==============================================================================
class User(AbstractUser):
    email = models.EmailField(unique=True, null=False, blank=False)
    first_name = models.CharField(max_length=50, blank=False)  # Added
    last_name = models.CharField(max_length=50, blank=False)   # Added
    username = models.CharField(max_length=150, blank=True, null=True)
    is_2fa_enabled = models.BooleanField(default=False)  # Add for 2FA
    email_verified = models.BooleanField(default=False)     # Add for email verification

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    class Meta(AbstractUser.Meta):
        abstract = False
        constraints = [models.UniqueConstraint(Lower('email'), name='accounts_email_case_insensitive')]

    def __str__(self):
        return self.email

    @property
    def is_public_demo(self):
        return self.email.casefold() == DEMO_EMAIL and self.username == DEMO_USERNAME
# ==============================================================================
class RecoveryCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=255)  # Stores hashed code
    encrypted_raw_code = models.TextField()  # Stores encrypted raw code
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.encrypted_raw_code and hasattr(self, '_raw_code'):
            fernet = get_fernet()
            try:
                self.encrypted_raw_code = fernet.encrypt(self._raw_code.encode()).decode()
            except Exception as e:
                logger.error(f"Encryption failed: {str(e)}")
                raise ValueError("Failed to encrypt raw code.")
        super().save(*args, **kwargs)

    def get_raw_code(self):
        fernet = get_fernet()
        try:
            return fernet.decrypt(self.encrypted_raw_code.encode()).decode()
        except Exception as e:
            logger.error(f"Decryption failed: {str(e)}")
            raise ValueError("Failed to decrypt raw code. The encryption key may be incorrect.")

    def __str__(self):
        return f"Recovery code for {self.user.email}"


class RateLimitBucket(models.Model):
    key = models.CharField(max_length=64, unique=True)
    count = models.PositiveIntegerField(default=0)
    expires_at = models.BigIntegerField(db_index=True)
