import urllib

from django.core.exceptions import ImproperlyConfigured
from django.core.mail import send_mail
from django.db import models
from django.db.models.manager import EmptyManager

from django.utils.crypto import get_random_string
from django.utils.encoding import smart_str
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType



# UNUSABLE_PASSWORD is still imported here for backwards compatibility

from django.contrib.auth.hashers import (
    check_password, make_password, is_password_usable, UNUSABLE_PASSWORD)


from Core.Backend.Components.models import UserPrivileges
from Core.UserManagement import auth
from Core.UserManagement.signals import user_logged_in

import sys


def update_last_login(sender, user, **kwargs):
    """
    A signal receiver which updates the last_login date for
    the user logging in.
    """
    user.last_login = timezone.now()
    user.save()
user_logged_in.connect(update_last_login)


class UserType(models.Model):
    name = models.CharField( max_length=254,unique=True)
    friendly_name = models.CharField( max_length=300)
    class Meta:
        #abstract = True
        verbose_name = 'User type'
        verbose_name_plural = 'User types'

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        return self.name

    def __unicode__(self):
        return self.name

class UserStatus(models.Model):
    name = models.CharField(max_length=254,unique=True)
    allow_login = models.BooleanField(default=False)
    friendly_name = models.CharField( max_length=300)    
    class Meta:
        #abstract = True
        verbose_name = 'User status'
        verbose_name_plural = 'User status'

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        return self.name

    def __unicode__(self):
        return self.name


def _user_get_all_permissions(user,client, obj):
    permissions = set()
    for backend in auth.get_backend(client):
        if hasattr(backend, "get_all_permissions"):
            if obj is not None:
                permissions.update(backend.get_all_permissions(user, obj))
            else:
                permissions.update(backend.get_all_permissions(user))
    return permissions


def _user_has_perm(user, perm, obj):
    anon = user.is_anonymous()
    active = user.is_active
    for backend in auth.get_backends():
        if anon or active or backend.supports_inactive_user:
            if hasattr(backend, "has_perm"):
                if obj is not None:
                    if backend.has_perm(user, perm, obj):
                            return True
                else:
                    if backend.has_perm(user, perm):
                        return True
    return False


def _user_has_module_perms(user, app_label):
    anon = user.is_anonymous()
    
    active = user.is_active
    for backend in auth.get_backends():
        if anon or active or backend.supports_inactive_user:
            if hasattr(backend, "has_module_perms"):
                if backend.has_module_perms(user, app_label):
                    return True
    return False


class GlobalUserGroupsModel(models.Model):
    modules = models.ManyToManyField(UserPrivileges, blank=True)
    group_name = models.CharField( max_length=300)
    owner = models.IntegerField(blank=False,default=0)
    modified = models.DateTimeField(auto_now=True)
    class Meta:
        verbose_name = _('User group')
        verbose_name_plural = _('User groups')
        abstract = True
    def get_full_name(self):
        return self.group_name

    def get_short_name(self):
        return self.group_name

    def __unicode__(self):
        return self.group_name



class GlobalUserModel(models.Model):
    """
    Users within the Django authentication system are represented by this
    model.

    Username and password are required. Other fields are optional.
    """
    username = models.CharField(('username'), max_length=30, blank=True,
        help_text=_('Required. 30 characters or fewer. Letters, numbers and '
                    '@/./+/-/_ characters'))
    first_name = models.CharField(('first_name'), max_length=30, blank=True)
    last_name = models.CharField(('last_name'), max_length=30, blank=True)
    email = models.EmailField(('e-mail'), blank=True)
    password = models.CharField(('password'), max_length=128)
    
    is_active = models.ForeignKey('UserStatus')
    last_login = models.DateTimeField(('last_login'), default=timezone.now)
    date_joined = models.DateTimeField(('date_joined'), default=timezone.now)
    user_type = models.ForeignKey('UserType')
    class Meta:
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        abstract = True
        #unique_together = (('username', 'country'),)
        

    def __unicode__(self):
        return self.username

    def natural_key(self):
        return (self.username,)

    def get_absolute_url(self):
        return "/users/%s/" % urllib.quote(smart_str(self.username))

    def is_anonymous(self):
        """
        Always returns False. This is a way of comparing User objects to
        anonymous users.
        """
        return False

    def is_authenticated(self):
        """
        Always return True. This is a way to tell if the user has been
        authenticated in templates.
        """
        return True

    def get_full_name(self):
        """
        Returns the first_name plus the last_name, with a space in between.
        """
        full_name = u'%s %s' % (self.first_name, self.last_name)
        return full_name.strip()

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        """
        Returns a boolean of whether the raw_password was correct. Handles
        hashing formats behind the scenes.
        """
        def setter(raw_password):
            self.set_password(raw_password)
            self.save()
        return check_password(raw_password, self.password, setter)

    def set_unusable_password(self):
        # Sets a value that will never be a valid hash
        self.password = make_password(None)

    def has_usable_password(self):
        return is_password_usable(self.password)

    def get_group_permissions(self, obj=None):
        """
        Returns a list of permission strings that this user has through his/her
        groups. This method queries all available auth backends. If an object
        is passed in, only permissions matching this object are returned.
        """
        permissions = set()
        for backend in auth.get_backends():
            if hasattr(backend, "get_group_permissions"):
                if obj is not None:
                    permissions.update(backend.get_group_permissions(self,
                                                                     obj))
                else:
                    permissions.update(backend.get_group_permissions(self))
        return permissions

    def get_all_permissions(self, obj=None):
        return _user_get_all_permissions(self, obj)

    def has_perm(self, perm, obj=None):
        """
        Returns True if the user has the specified permission. This method
        queries all available auth backends, but returns immediately if any
        backend returns True. Thus, a user who has permission from a single
        auth backend is assumed to have permission in general. If an object is
        provided, permissions for this specific object are checked.
        """

        # Active superusers have all permissions.

        if self.is_active and self.is_superuser:
            return True

        # Otherwise we need to check the backends.
        return _user_has_perm(self, perm, obj)

    def has_perms(self, perm_list, obj=None):
        """
        Returns True if the user has each of the specified permissions. If
        object is passed, it checks if the user has all required perms for this
        object.
        """
        for perm in perm_list:
            if not self.has_perm(perm, obj):
                return False
        return True

    def has_module_perms(self, app_label):
        """
        Returns True if the user has any permissions in the given app label.
        Uses pretty much the same logic as has_perm, above.
        """
        # Active superusers have all permissions.
        if self.is_active and self.is_superuser:
            return True

        return _user_has_module_perms(self, app_label)

    def email_user(self, subject, message, from_email=None):
        """
        Sends an email to this User.
        """
        send_mail(subject, message, from_email, [self.email])

    def get_profile(self):
        """
        Returns site-specific profile for this user. Raises
        SiteProfileNotAvailable if this site does not allow profiles.
        """
        #for perm in _user_get_all_permissions(self,obj=None):

        if not hasattr(self, '_profile_cache'):
            from django.conf import settings
            if not getattr(settings, 'LOGIN_PROFILE_MODULE', False):
                raise SiteProfileNotAvailable(
                    'You need to set LOGIN_PROFILE_MODULE in your project '
                    'settings')
            try:
                app_label, model_name = settings.LOGIN_PROFILE_MODULE.split('.')
            except ValueError:
                raise SiteProfileNotAvailable(
                    'app_label and model_name should be separated by a dot in '
                    'the LOGIN_PROFILE_MODULE setting')
            try:
                model = models.get_model(app_label, model_name)
                if model is None:
                    raise SiteProfileNotAvailable(
                        'Unable to load the profile model, check '
                        'LOGIN_PROFILE_MODULE in your project settings')
                self._profile_cache = model._default_manager.using(
                                   self._state.db).get(id__exact=self.id)
                self._profile_cache.user = self
            except (ImportError, ImproperlyConfigured):
                raise SiteProfileNotAvailable
        return self._profile_cache


class AnonymousUser(object):
    id = None
    is_active = {
        'allow_login': False,
        'name' : 'Anonymous',
    }
    user_type = {
        'name' : 'Anonymous',
    }#is_active = UserStatus.objects.get(name='Anonymous')
    #user_type = UserType.objects.get(name='Anonymous')

    _groups = EmptyManager()
    _user_permissions = EmptyManager()

    class Meta:
        abstract = True

    def __init__(self):
        pass

    def __unicode__(self):
        return 'AnonymousUser'

    def __str__(self):
        return unicode(self).encode('utf-8')

    def __eq__(self, other):
        return isinstance(other, self.__class__)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return 1 # instances always return the same hash value

    def save(self):
        raise NotImplementedError

    def delete(self):
        raise NotImplementedError

    def set_password(self, raw_password):
        raise NotImplementedError

    def check_password(self, raw_password):
        raise NotImplementedError

    def _get_groups(self):
        return self._groups
    groups = property(_get_groups)

    def _get_user_permissions(self):
        return self._user_permissions
    user_permissions = property(_get_user_permissions)

    def get_group_permissions(self, obj=None):
        return set()

    def get_all_permissions(self, obj=None):
        return _user_get_all_permissions(self, obj=obj)

    def has_perm(self, perm, obj=None):
        return _user_has_perm(self, perm, obj=obj)

    def has_perms(self, perm_list, obj=None):
        for perm in perm_list:
            if not self.has_perm(perm, obj):
                return False
        return True

    def has_module_perms(self, module):
        return _user_has_module_perms(self, module)

    def is_anonymous(self):
        return True

    def is_authenticated(self):
        return False
