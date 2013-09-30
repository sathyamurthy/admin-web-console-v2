from functools import update_wrapper
from django.http import Http404,HttpResponseForbidden, HttpResponseRedirect
from django.contrib.admin import ModelAdmin, actions
from django.contrib.contenttypes import views as contenttype_views
from django.views.decorators.csrf import csrf_protect
from django.db.models.base import ModelBase
from django.core.exceptions import ImproperlyConfigured
from django.core.urlresolvers import reverse, NoReverseMatch
from django.template.response import TemplateResponse
from django.utils.safestring import mark_safe
from django.utils.text import capfirst
from django.utils.translation import ugettext as _
from django.views.decorators.cache import never_cache
from django.conf import settings
from django.contrib import admin
from django.core.urlresolvers import reverse
from tastypie.exceptions import Unauthorized

from Client.Ikea.Users.forms import AuthenticationForm
from Core.UserManagement import REDIRECT_FIELD_NAME,get_user
from Core.Backend.PrivilegeManagement import site
from Core.Backend.PrivilegeManagement.sites import get_accessble_modules,get_client_from_url


import sys

LOGIN_FORM_KEY = 'this_is_the_login_form'

site.usersite.CLIENT = "ikea"


def get_country_from_url( PATH):
    try:
        return PATH.split('/')[2]
    except:
        pass
    return ""

def error_template(error_id,request,context,label):
    return TemplateResponse(request, 'base_templates/%s.html'%(error_id), context = context, current_app=label)

class IkeaView(object):
    """
    An AdminSite object encapsulates an instance of the Django admin application, ready
    to be hooked in to your URLconf. Models are registered with the AdminSite using the
    register() method, and the get_urls() method can then be used to access Django view
    functions that present a full admin interface for the collection of registered
    models.
    """
    login_form = None
    index_template = None
    app_index_template = None
    login_template = "client/ikea/login.html"
    logout_template = "client/ikea/registration/logged_out.html"
    password_reset = "client/ikea/registration/password_reset_form.html"
    password_change_template = "client/ikea/registration/password_change_form.html"
    password_change_done_template = "client/ikea/registration/password_change_done.html"

    def __init__(self, name='customer_admin', app_name='customer_admin'):
        self._registry = {} # model_class class -> admin_class instance
        self.name = name
        self.app_name = app_name
        self._actions = {'delete_selected': actions.delete_selected}
        self._global_actions = self._actions.copy()


    def has_permission(self, request):
        """
        Returns True if the given HttpRequest has permission to view
        *at least one* page in the admin site.
        """
        user = get_user(request);
        if isinstance(user.is_active, dict):
            return user.is_active['allow_login']
        else:
            return user.is_active.allow_login 
    def get_user_status(self, request):
        """
        Returns True if the given HttpRequest has permission to view
        *at least one* page in the admin site.
        """
        user = get_user(request);
        
        if isinstance(user.is_active, dict):
            return user.is_active['name']
        else:
            return user.is_active.name 

    def check_dependencies(self):
        """
        Check that all things needed to run the admin have been correctly installed.

        The default implementation checks that LogEntry, ContentType and the
        auth context processor are installed.
        """
        from django.contrib.admin.models import LogEntry
        from django.contrib.contenttypes.models import ContentType

        if not LogEntry._meta.installed:
            raise ImproperlyConfigured("Put 'django.contrib.admin' in your "
                "INSTALLED_APPS setting in order to use the admin application.")
        if not ContentType._meta.installed:
            raise ImproperlyConfigured("Put 'django.contrib.contenttypes' in "
                "your INSTALLED_APPS setting in order to use the admin application.")
        if not ('django.contrib.auth.context_processors.auth' in settings.TEMPLATE_CONTEXT_PROCESSORS or
            'django.core.context_processors.auth' in settings.TEMPLATE_CONTEXT_PROCESSORS):
            raise ImproperlyConfigured("Put 'django.contrib.auth.context_processors.auth' "
                "in your TEMPLATE_CONTEXT_PROCESSORS setting in order to use the admin application.")

    def admin_view(self, view, cacheable=False):
        """
        Decorator to create an admin view attached to this ``AdminSite``. This
        wraps the view and provides permission checking by calling
        ``self.has_permission``.

        You'll want to use this from within ``AdminSite.get_urls()``:

            class MyAdminSite(AdminSite):

                def get_urls(self):
                    from django.conf.urls import patterns, url

                    urls = super(MyAdminSite, self).get_urls()
                    urls += patterns('',
                        url(r'^my_view/$', self.admin_view(some_view))
                    )
                    return urls

        By default, admin_views are marked non-cacheable using the
        ``never_cache`` decorator. If the view can be safely cached, set
        cacheable=True.
        """
        def inner(request, *args, **kwargs):
            
            if not self.has_permission(request):
                client = get_client_from_url(request.get_full_path())
                status = self.get_user_status(request)
                #return HttpResponseRedirect("/%s/" % client)
                """
                if not status.lower() == 'anonymous' :
                    return HttpResponseRedirect("/%s/%s/" % (client,status.lower()))
                else:
                    return HttpResponseRedirect("/%s/" % client)
                """
                if not status.lower() == 'anonymous' :
                    if "/signout/" in request.path:
                        return self.logout(request)
                    else:
                        return self.access_restriction(request,status.lower())
                elif not "/password/" in request.path:
                    return self.login(request)
                else:
                    if "/password/reset/done/" in request.path:
                        return self.pwd_reset_done(request)
                    elif "/password/reset/confirm/complete/" in request.path:
                        return self.pwd_reset_confirm_complete(request)
                    elif "/password/reset/confirm/" in request.path:
                        return self.pwd_reset_confirm(request)
                    else:
                        return self.pwd_reset(request)
            return view(request, *args, **kwargs)
        if not cacheable:
            inner = never_cache(inner)
        # We add csrf_protect here so this function can be used as a utility
        # function for any view, without having to repeat 'csrf_protect'.
        if not getattr(view, 'csrf_exempt', False):
            inner = csrf_protect(inner)
        return update_wrapper(inner, view)

    def get_urls(self):
        from django.conf.urls import patterns, url, include

        if settings.DEBUG:
            self.check_dependencies()

        def wrap(view,app_label=None,action=None,cacheable=False):
            def wrapper(*args, **kwargs):
                if app_label is not None:
                    kwargs['app_label'] = app_label

                if action is not None:
                    kwargs['action'] = action
                    """
                    try :
                        kwargs['action'] = app_label.split('.')[1]
                    except :
                        pass
                    """
                #if action is not None:
                    

                return self.admin_view(view, cacheable)(*args, **kwargs)
            return update_wrapper(wrapper, view)

        # Admin-site-wide views.
        urlpatterns = patterns('',
            url(r'^$',
                wrap(self.index),
                name='index'),
            url(r'^signout/$',
                wrap(self.logout),
                name='logout'),
            url(r'^password_change/$',
                wrap(self.password_change, cacheable=False),
                name='password_change'),
            url(r'^Users/my_account/$',
                wrap(self.my_account, cacheable=False),
                name='my_accout'),
            url(r'^password/reset/$',
                wrap(self.pwd_reset, cacheable=False),
                name='pwd_reset'),
            url(r'^password/reset/done/$',
                wrap(self.pwd_reset_done, cacheable=False),
                name='pwd_reset_done'),
            url(r'^password/reset/confirm/$',
                wrap(self.pwd_reset_confirm, cacheable=False),
                name='pwd_reset_confirm'),
            url(r'^password/reset/confirm/complete/$',
                wrap(self.pwd_reset_confirm_complete, cacheable=False),
                name='pwd_reset_confirm_complete'),
            url(r'^password_change/done/$',
                wrap(self.password_change_done, cacheable=False),
                name='password_change_done'),
            url(r'^jsi18n/$',
                wrap(self.i18n_javascript, cacheable=False),
                name='jsi18n'),
            
            
        )
        urlpatterns += patterns('Admin',
            url(r'^' ,include(site.usersite.geturls(app_name='IKEA',name='IKEA')))
        )
        return urlpatterns

    @property
    def urls(self):
        #print >> sys.stdout, self.app_name, self.name
        return self.get_urls(), self.app_name, self.name

    def geturls(self,app_name,name):
        #print >> sys.stdout, self.app_name, self.name
        return self.get_urls(), app_name, name

    def access_restriction(self,request,status):
        client = get_client_from_url(request.get_full_path())
        #url = '/%s/%s/' % (client,country)
        user = get_user(request)
        url = '/%s/' % (client)
        extra_context = {
            'country' :(url),
            'home_url' : url
        }
        extra_context['profile'] = user.get_profile();
        return site.usersite.not_accessable(request,status,extra_context=extra_context)

    def i18n_javascript(self, request):
        """
        Displays the i18n JavaScript that the Django admin requires.

        This takes into account the USE_I18N setting. If it's set to False, the
        generated JavaScript will be leaner and faster.
        """
        if settings.USE_I18N:
            from django.views.i18n import javascript_catalog
        else:
            from django.views.i18n import null_javascript_catalog as javascript_catalog
        return javascript_catalog(request, packages=['django.conf', 'django.contrib.admin'])

    def password_change(self, request):
        """
        Handles the "change password" task -- both form display and validation.
        """
        from Core.UserManagement.views import password_change
        user = get_user(request)
        country = ""
        #country = user.user_market.country.iso_code
        client = get_client_from_url(request.get_full_path())
        #url = '/%s/%s/' % (client,country)
        url = '/%s/' % (client)
        extra_context = {
            'country' :(url),
            'home_url' : url
        }
        extra_context['profile'] = user.get_profile();
        extra_context['modules'] = get_accessble_modules(request,sel_mod='Users',sel_action='',client_name=client)
        
        defaults = {
            'current_app': self.name,
            'extra_context' : extra_context,
            'post_change_redirect': url + 'password_change/done/'
        }
        #import pdb
        #pdb.set_trace()

        if self.password_change_template is not None:
            defaults['template_name'] = self.password_change_template
        return password_change(request, **defaults)

    def password_change_done(self, request, extra_context=None):
        """
        Displays the "success" page after a password change.
        """
        from Core.UserManagement.views import password_change_done
        user = get_user(request)
        country = ""
        #country = user.user_market.country.iso_code
        client = get_client_from_url(request.get_full_path())
        #url = '/%s/%s/' % (client,country)
        url = '/%s/' % (client)
        extra_context = {
            'home_url' :url,
        }
        extra_context['profile'] = user.get_profile();
        extra_context['modules'] = get_accessble_modules(request,sel_mod='Users',sel_action='',client_name=client)

        defaults = {
            'current_app': self.name,
            'extra_context': extra_context or {},
        }
        if self.password_change_done_template is not None:
            defaults['template_name'] = self.password_change_done_template
        return password_change_done(request, **defaults)


    def pwd_reset_done(self, request):
        """
        Handles the "change password" task -- both form display and validation.
        """


        from Core.UserManagement.views import password_reset_done
        #country = get_country_from_url(request.get_full_path())
        country = ""
        client = get_client_from_url(request.get_full_path())
        #url = '/%s/%s/' % (client,country)
        url = '/%s/' % (client)
        extra_context = {
            'country' : '%s' % ( get_country_from_url(request.get_full_path())),
            'home_url' : url
        }
        defaults = {
            'current_app': self.name,
            'extra_context' : extra_context,
        }
        defaults['template_name'] = "client/ikea/registration/password_reset_done.html"
        return password_reset_done(request, **defaults)

    def pwd_reset_confirm_complete(self, request):
        """
        Handles the "change password" task -- both form display and validation.
        """

        
        from Core.UserManagement.views import password_reset_complete
        #country = get_country_from_url(request.get_full_path())
        country = ""
        client = get_client_from_url(request.get_full_path())
        #url = '/%s/%s/' % (client,country)
        url = '/%s/' % (client)
        extra_context = {
            'country' : '%s' % ( get_country_from_url(request.get_full_path())),
            'home_url' : url
        }
        defaults = {
            'current_app': self.name,
            'extra_context' : extra_context,
        }
        defaults['template_name'] = "client/ikea/registration/password_reset_complete.html"
        return password_reset_complete(request, **defaults)
    
    def pwd_reset_confirm(self, request):
        """
        Handles the "change password" task -- both form display and validation.
        """


        from Core.UserManagement.views import password_reset_confirm
        #country = get_country_from_url(request.get_full_path())
        country=""
        client = get_client_from_url(request.get_full_path())
        #url = '/%s/%s/' % (client,country)
        url = '/%s/' % (client)
        extra_context = {
            'country' : '%s' % ( get_country_from_url(request.get_full_path())),
            'home_url' : url
        }
        from Client.Ikea.Users.models import Ikea
        defaults = {
            'current_app': self.name,
            'uidb36': request.GET['uidb36'],
            'token' : request.GET['token'],
            'extra_context' : extra_context,
            'User':Ikea,
            'post_reset_redirect': '/%s/password/reset/confirm/complete/' % ( get_client_from_url(request.get_full_path())),
        }
        defaults['template_name'] = "client/ikea/registration/password_reset_confirm.html"
        return password_reset_confirm(request, **defaults)


    def pwd_reset(self, request):
        """
        Handles the "change password" task -- both form display and validation.
        """
        from Core.UserManagement.views import password_reset
        from Client.Ikea.Users.forms import PasswordResetForm
        #reverse('customer_admin:password_change_done', current_app=self.name)
        #country = get_country_from_url(request.get_full_path())
        country=""
        client = get_client_from_url(request.get_full_path())
        #url = '/%s/%s/password/reset/done/' % (client,country)
        url = '/%s/password/reset/done/' % (client)

        extra_context = {
            'country' : '%s' % ( get_country_from_url(request.get_full_path())),
        }

        defaults = {
            'current_app': self.name,
            'post_reset_redirect': url,
            'extra_context' : extra_context,
            'from_email': 'no-reply@ec.is',
        }
        #import pdb
        #pdb.set_trace()

        defaults['password_reset_form'] = PasswordResetForm
        if self.password_reset is not None:
            defaults['template_name'] = self.password_reset

        #print >> sys.stdout, password_reset(request, **defaults)
        return password_reset(request, **defaults)

    @never_cache
    def logout(self, request, extra_context=None):
        """
        Logs out the user for the given HttpRequest.

        This should *not* assume the user is already logged in.
        """
        from Core.UserManagement.views import logout
        extra_context = {
            'country' : '/%s/' % ( get_client_from_url(request.get_full_path())),
        }
        defaults = {
            'current_app': self.name,
            'extra_context': extra_context or {},
        }
        if self.logout_template is not None:
            defaults['template_name'] = self.logout_template
        return logout(request, **defaults)

    @never_cache
    def login(self, request, extra_context=None):
        """
        Displays the login form for the given HttpRequest.
        """
        from Client.Ikea.Users.views import login
        from django.db.models import Q
        #from Client.Ikea.Users.models import Market
        from Client.Ikea.IkeaCategories.models import IkeaMarkets as Market
        context = {
            'title': _('Log in'),
            'app_path': request.get_full_path(),
            'country' : get_country_from_url(request.get_full_path()),
            'password_reset_url' : '/%s/%s/password/reset/' % ( get_client_from_url(request.get_full_path()) , get_country_from_url(request.get_full_path()) ),
            REDIRECT_FIELD_NAME: request.get_full_path(),
            'countries':Market.objects.filter(~Q(country__pk=1000)),
        }
        context.update(extra_context or {})
        defaults = {
            'extra_context': context,
            'current_app': self.name,
            'authentication_form': self.login_form or AuthenticationForm,
            'template_name': self.login_template or 'client/ikea/login.html',
        }
        return login(request, **defaults)

    @never_cache
    def my_account(self, request, extra_context=None):
        """
        Displays the main admin index page, which lists all of the installed
        apps that have been registered in this site.
        """
        #user = request.user
        user = get_user(request)
        #country = user.user_market.country.iso_code
        country = ""
        client = get_client_from_url(request.get_full_path())
        #url = '/%s/%s/' % (client,country)
        url = '/%s/' % (client)

        context = {
            'title': "Catalogue administartion",
        }

        extra_context = dict()
        extra_context['home_url'] = url
        extra_context['profile'] = user.get_profile();
        extra_context['modules'] = get_accessble_modules(request,sel_mod='Users',sel_action='',client_name=client)

            #print >> sys.stdout, extra_context['modules']
            #print >> sys.stdout, 'edit' in [x.lower() for x in modules['users']['models']]
            #context.url ='/US/'
        context.update(extra_context or {})
        defaults = {
            'extra_context': context,
            'template_name': 'client/ikea/users/my_account.html',
        }
        from Client.Ikea.Users.views import accout_information_update
        return accout_information_update(request, **defaults)            

    @never_cache
    def index(self, request, extra_context=None):
        return site.usersite.index(request,extra_context=extra_context,template='client/ikea/app_index.html')

    def app_index(self, request, app_label, extra_context=None):
        return site.usersite.app_index(request,app_label,extra_context=extra_context)

    def app_mod_index(self, request, app_label,action,object_id=None, extra_context=None):
        return site.usersite.app_index(request,app_label,action,object_id=object_id,extra_context=extra_context)

# This global object represents the default admin site, for the common case.
# You can instantiate AdminSite in your own code to create a custom admin site.
ikeasite = IkeaView()
