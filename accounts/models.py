from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    def create_user(self, email, raw_password=None, full_name=None, role=None, **extra_fields):
        if not email:
            raise ValueError(_('The Email field must be set'))
        email = self.normalize_email(email)
        extra_fields.setdefault('is_active', True)
        role = role or User.Role.OWNER
        user = self.model(email=email, full_name=full_name or '', role=role, **extra_fields)
        if raw_password is not None:
            user.set_password(raw_password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, raw_password=None, full_name=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))

        return self.create_user(
            email,
            raw_password=raw_password,
            full_name=full_name or 'Super Admin',
            role=User.Role.SUPER_ADMIN,
            **extra_fields,
        )


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        OWNER = 'owner', _('Owner')
        STAFF = 'staff', _('Staff')
        SUPER_ADMIN = 'super_admin', _('Super Admin')

    email = models.EmailField(_('email address'), unique=True)
    full_name = models.CharField(_('full name'), max_length=255)
    role = models.CharField(_('role'), max_length=32, choices=Role.choices, default=Role.OWNER)
    is_active = models.BooleanField(_('active'), default=True)
    is_staff = models.BooleanField(_('staff status'), default=False)
    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        ordering = ['email']

    def __str__(self):
        return self.email

    def get_full_name(self):
        return self.full_name or self.email

    def get_short_name(self):
        return self.full_name or self.email

    @property
    def is_owner(self):
        return self.role == self.Role.OWNER

    @property
    def is_super_admin(self):
        return self.role == self.Role.SUPER_ADMIN or self.is_superuser
