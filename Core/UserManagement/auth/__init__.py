from warnings import warn
from django.core.exceptions import ImproperlyConfigured
from django.utils.importlib import import_module
from Core.UserManagement.signals import user_logged_in, user_logged_out
import sys

SESSION_KEY = '_login_user_id'
BACKEND_SESSION_KEY = '_login_user_backend'
REDIRECT_FIELD_NAME = '_login_user_next'
LBACKEND_PATH = '_login_user_next'
def load_backend(path):
    i = path.rfind('.')
    module, attr = path[:i], path[i+1:]
    try:
        mod = import_module(module)
    except ImportError, e:
        raise ImproperlyConfigured('Error importing authentication backend %s: "%s"' % (path, e))
    except ValueError, e:
        raise ImproperlyConfigured('Error importing authentication backends. Is AUTHENTICATION_BACKENDS a correctly defined list or tuple?')
    try:
        cls = getattr(mod, attr)
    except AttributeError:
        raise ImproperlyConfigured('Module "%s" does not define a "%s" authentication backend' % (module, attr))

    if not hasattr(cls, 'supports_inactive_user'):
        warn("Authentication backends without a `supports_inactive_user` attribute are deprecated. Please define it in %s." % cls,
             DeprecationWarning)
        cls.supports_inactive_user = False
    return cls()

def get_backends():
    from django.conf import settings
    backends = []
    
    for backend_path in settings.AUTH_BACKEND_CLIENT:
        backends.append(load_backend(settings.AUTH_BACKEND_CLIENT[backend_path]["BACKEND_PATH"]))
    if not backends:
        raise ImproperlyConfigured('No authentication backends have been defined. Does AUTHENTICATION_BACKENDS contain anything?')
    return backends
def get_backend(client):
    from django.conf import settings
    backends = []
    backends.append(load_backend(settings.AUTH_BACKEND_CLIENT[client]["BACKEND_PATH"]))
    return backends

def authenticate(**credentials):
    """
    If the given credentials are valid, return a User object.
    """
    CLIENT = "ikea"
    try:
        CLIENT =  sys.stdout,credentials["client"]
    except:
        pass
    
    for backend in get_backend(CLIENT):
        try:
            MyUser = backend.authenticate(**credentials)
        except TypeError:
            # This backend doesn't accept these credentials as arguments. Try the next one.
            continue
        if MyUser is None:
            continue


        # Annotate the user object with the path of the backend.
        MyUser.backend = "%s.%s" % (backend.__module__, backend.__class__.__name__)
        return MyUser

def setSessionKeys(request):
    from django.conf import settings
    SETS = {}
    if request.get_full_path().lower().find("/ikea/") > -1:
        SETS = settings.AUTH_BACKEND_CLIENT["ikea"]
    elif request.get_full_path().lower().find("/ecadmin/") > -1:
        SETS = settings.AUTH_BACKEND_CLIENT["ecadmin"]
    elif request.get_full_path().lower().find("/sandvik/") > -1:
        SETS = settings.AUTH_BACKEND_CLIENT["sandvik"]
    else:
        SETS = settings.AUTH_BACKEND_CLIENT["ec-small-client"]
        """
        SESSION_KEY = settings.AUTH_BACKEND_CLIENT["ec-small-client"]["SESSION_KEY"]
        BACKEND_SESSION_KEY = settings.AUTH_BACKEND_CLIENT["ec-small-client"]["BACKEND_SESSION_KEY"]
        REDIRECT_FIELD_NAME = settings.AUTH_BACKEND_CLIENT["ec-small-client"]["REDIRECT_FIELD_NAME"]
        LBACKEND_PATH = settings.AUTH_BACKEND_CLIENT["ec-small-client"]["BACKEND_PATH"]
        """
    return SETS
def login(request, MyUser):
    """
    Persist a user id and a backend in the request. This way a user doesn't
    have to reauthenticate on every request. Note that data set during
    the anonymous session is retained when the user logs in.
    """
    # TODO: It would be nice to support different login methods, like signed cookies.
    Backend_Settings = setSessionKeys(request)

    try:
        request.session[Backend_Settings["SESSION_KEY"]]
    except:
        request.session[Backend_Settings["SESSION_KEY"]]=''
        
    if request.session[Backend_Settings["SESSION_KEY"]]  in request.session:
        if request.session[Backend_Settings["SESSION_KEY"]] != MyUser.id:
            # To avoid reusing another user's session, create a new, empty
            # session if the existing session corresponds to a different
            # authenticated user.
            request.session.flush()
    else:
        request.session.cycle_key()
        
    request.session[Backend_Settings["SESSION_KEY"]] = MyUser.id
    request.session[Backend_Settings["BACKEND_SESSION_KEY"]] = MyUser.backend
    from datetime import datetime
    request.session['last_activity'] = datetime.now()

    user_logged_in.send(sender=MyUser.__class__, request=request, user=MyUser)

def logout(request):
    """
    Removes the authenticated user's ID from the request and flushes their
    session data.
    """
    # Dispatch the signal before the user is logged out so the receivers have a
    # chance to find out *who* logged out.
    Backend_Settings = setSessionKeys(request)
    request.session[Backend_Settings["SESSION_KEY"]] = ''
    request.session[Backend_Settings["BACKEND_SESSION_KEY"]] = ''
    request.session['last_activity'] = ''
    user = getattr(request, 'user', None)
    if hasattr(user, 'is_authenticated') and not user.is_authenticated():
        user = None
    user_logged_out.send(sender=user.__class__, request=request, user=user)

    request.session.flush()
    #if hasattr(request, 'user'):
    #    from Core.UserManagement.models import AnonymousUser
    #    request.user = AnonymousUser()


def get_user(request):
    #logout(request)
    Backend_Settings = setSessionKeys(request)
    backend = load_backend(Backend_Settings["BACKEND_PATH"])
    try:
        user_id = request.session[Backend_Settings["SESSION_KEY"]]
        backend_path = request.session[Backend_Settings["BACKEND_SESSION_KEY"]]
        backend = load_backend(backend_path)
        user = backend.get_user(user_id) or backend.get_user(-1)
    except KeyError:
        user = backend.get_user(-1)
        #user = None
    return user
