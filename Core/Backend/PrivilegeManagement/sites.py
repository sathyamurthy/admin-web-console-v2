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

from Core.UserManagement import REDIRECT_FIELD_NAME,get_user


import sys

LOGIN_FORM_KEY = 'this_is_the_login_form'

class AlreadyRegistered(Exception):
    pass

class NotRegistered(Exception):
    pass

def error_template(error_id,request,context,label):
    return TemplateResponse(request, 'base_templates/%s.html'%(error_id), context = context, current_app=label)

def get_client_from_url( PATH):
    try:
        return PATH.split('/')[1]
    except:
        pass
    return ""

def get_accessble_modules(request,sel_mod='',sel_action='',client_name=''):
    #print >> sys.stdout,sel_mod
    user = get_user(request)
    CLIENT = client_name
    country = ""
    #country = user.user_market.country.iso_code
    modules = {'mod':[],'selected':[],'menus':[]}
    from Core.Backend.Components.models import UserModules,UserPrivileges,UserActions
    for s in user.get_all_permissions():
        modules['perm_'+s.replace('.','_').lower()]={'opt':['true']}
    for module in UserModules.objects.all():
        app_label = module.module_name
        permission_set = user.get_all_permissions()
        has_module_perms = user.has_module_perms(app_label)
        
        if has_module_perms:

            groups = ''
            if module.groups.title().lower() == "none":
                groups = ''
            else:
                groups = '%s/' % module.groups.title()

            selected = False
            if sel_mod.lower() == app_label.lower():
                modules['mod'].append({'name':app_label,'url':'/%s/%s%s/' % (CLIENT,groups,app_label),'sel':'active'})
                selected = True
                modules['selected'].append({'name':app_label,'url':'/%s/%s%s/' % (CLIENT,groups,app_label),'options':[]})
            else:
                modules['mod'].append({'name':app_label,'url':'/%s/%s%s/' % (CLIENT,groups,app_label),'sel':''})

            perms = module.get_model_perms(module=module.pk)
            for prm in perms:
                if UserPrivileges.objects.filter(module=module).filter(action=UserActions.objects.filter(action_name=prm))[0].show_as_link:
                    if "%s.%s" % (app_label,prm) in permission_set:
                        modules[app_label.lower()]={'opt':[]}
                        modules[app_label.lower()+'_'+prm.lower()]={'opt':[]}
                        modules[app_label.lower()]['opt'].append('/%s/%s%s/' % (CLIENT,groups,app_label))
                        modules[app_label.lower()+'_'+prm.lower()]['opt'].append('/%s/%s%s/%s' % (CLIENT,groups,app_label,prm))
                        if selected:
                            #print >> sys.stdout,prm
                            if prm.lower() == sel_action.lower():
                                modules['selected'][0]['options'].append({'name':prm,'url':'/%s/%s%s/%s' % (CLIENT,groups,app_label,prm),'sel':'active'})
                            else:
                                modules['selected'][0]['options'].append({'name':prm,'url':'/%s/%s%s/%s' % (CLIENT,groups,app_label,prm),'sel':''})

    #print >> sys.stdout,modules
    return modules

class CustomerView(object):
    """
    An AdminSite object encapsulates an instance of the Django admin application, ready
    to be hooked in to your URLconf. Models are registered with the AdminSite using the
    register() method, and the get_urls() method can then be used to access Django view
    functions that present a full admin interface for the collection of registered
    models.
    """
    index_template = None
    app_index_template = None
    CLIENT = None
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
            client = self.CLIENT
            if not self.has_permission(request):
                status = self.get_user_status(request)
                if not status.lower() == 'anonymous' :
                    return self.not_accessable(request,status.lower())
                else:
                    return HttpResponseRedirect("/%s" % client)

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
        urlpatterns = list()

        # Add in each model's views.
        

        from Core.Backend.Components.models import UserModules
        for module in UserModules.objects.all():
            
            if module.groups.title().lower() == "none":
                urlpatterns += patterns('',
                    url(r'^%s/$' %(module.title()),
                        wrap(self.app_index,app_label= module.title()),
                        name=module.title()
                        #name='app_list'
                        )
                )
            else:
                urlpatterns += patterns('',
                    url(r'^%s/%s/$' %(module.groups.title(),module.title()),
                        wrap(self.app_index,app_label= module.title()),
                        name=module.title()
                        #name='app_list'
                        )
                )
            
              
        from Core.Backend.Components.models import UserPrivileges
        for privilege in UserPrivileges.objects.all():
            if privilege.module.groups.title().lower() == "none":
                urlpatterns += patterns('',
                    url(r'^%s/%s/$' % (privilege.module.title(), privilege.action.title()),
                        wrap(self.app_mod_index,app_label= privilege.module.title(),action=privilege.action.title()),
                        name=privilege.module.title()+"_"+privilege.action.title(),
                        ),
                )
                urlpatterns += patterns('',
                    url(r'^%s/%s/(?P<object_id>.+)/$' % (privilege.module.title(), privilege.action.title()),
                        wrap(self.app_mod_index,app_label= privilege.module.title(),action=privilege.action.title()),
                        name=privilege.module.title()+"_"+privilege.action.title(),
                        ),
                )
            else:
                urlpatterns += patterns('',
                    url(r'^%s/%s/%s/$' % (privilege.module.groups.title(),privilege.module.title(), privilege.action.title()),
                        wrap(self.app_mod_index,app_label= privilege.module.title(),action=privilege.action.title()),
                        name=privilege.module.title()+"_"+privilege.action.title(),
                        ),
                )
                urlpatterns += patterns('',
                    url(r'^%s/%s/%s/(?P<object_id>.+)/$' % (privilege.module.groups.title(),privilege.module.title(), privilege.action.title()),
                        wrap(self.app_mod_index,app_label= privilege.module.title(),action=privilege.action.title()),
                        name=privilege.module.title()+"_"+privilege.action.title(),
                        ),
                )

        #print >> sys.stdout,r'^%s/%s/' % (privillege.module.title(), privillege.action.title())
        """
        for model, model_admin in self._registry.iteritems():
            #print >> sys.stdout,model_admin.urls
            print >> sys.stdout,model_admin
            urlpatterns += patterns('',
                url(r'^%s/%s/' % (model._meta.app_label, model._meta.module_name),
                    include(model_admin.urls))
            )
        """
        #print >> sys.stdout,urlpatterns
        return urlpatterns

    @property
    def urls(self):
        #print >> sys.stdout, self.app_name, self.name
        return self.get_urls(), self.app_name, self.name

    def geturls(self,app_name,name):
        #print >> sys.stdout, self.app_name, self.name
        return self.get_urls(), app_name, name

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

    def not_accessable(self, request,template_name, extra_context=None):
        if extra_context is None:
            extra_context = dict()
            url = '/%s/' % (self.CLIENT)
            url = '/%s/' % (self.CLIENT)
            extra_context = {
                'country' :(url),
                'home_url' : url
            }
        return TemplateResponse(request, [
            'client/%s/%s.html' % (self.CLIENT,template_name),
            'client/%s/login.html' % (self.CLIENT),
            'base_templates/%s.html' % (template_name),
            'base_templates/login.html',
        ], context = extra_context)

    @never_cache
    def index(self, request, extra_context=None,template=None):
        """
        Displays the main admin index page, which lists all of the installed
        apps that have been registered in this site.
        """
        #user = request.user
        user = get_user(request)
        url = '/%s/' % (self.CLIENT)

        context = {
            'title': "Catalogue administartion",
        }

        extra_context = dict()
        extra_context['home_url'] = url
        extra_context['profile'] = user.get_profile();
        extra_context['modules'] = get_accessble_modules(request,sel_mod='',sel_action='',client_name=self.CLIENT)
        context.update(extra_context or {})
        return TemplateResponse(request, [
            template,
            'client/%s/index.html' % (self.CLIENT.lower()),
            self.index_template or 'base_templates/index.html',
        ], context, current_app=self.name,)

    def app_index(self, request, app_label, extra_context=None,template=None):
        user = get_user(request)
        context = {
            'title': _('%s administration') % capfirst(app_label),
        }
        extra_context = dict()

        url = '/%s/' % (self.CLIENT)

        extra_context['home_url'] = url
        extra_context['profile'] = user.get_profile();
        extra_context['modules'] = get_accessble_modules(request,sel_mod=app_label,sel_action='',client_name=self.CLIENT)
        if not extra_context['modules']:
            raise Http404('The requested admin page does not exist.')

        context.update(extra_context or {})

        return TemplateResponse(request, self.app_index_template or [
            template,
            'client/%s/%s/app_index.html' % (self.CLIENT,app_label.lower()),
            'client/%s/index.html' % (self.CLIENT.lower()),
            'base_templates/%s/app_index.html' % app_label.lower(),
            'base_templates/app_index.html'
        ], context, current_app=self.name)

    def app_mod_index(self, request, app_label,action,object_id=None, extra_context=None,template=None):
        user = get_user(request)
        url = '/%s/' % (self.CLIENT)
        
        permission_set = user.get_all_permissions()
    
        if "%s.%s" % (app_label,action) in permission_set:
            context = {
                'title': _('%s administration') % capfirst(app_label),
                'add' : True,
                'submit_row' : True,
                'uid': '69c2bcfd-4bab-43ac-a746-e456bf096a36',
                'maxfilesize': '16777216',
                'minfilesize': '1024',
                'open_tv': u'{{',
                'close_tv': u'}}',
            }
                
            extra_context = dict()
            extra_context['home_url'] = url
            extra_context['profile'] = get_user(request).get_profile();
            extra_context['action'] = action.lower();
            extra_context['object_id'] = object_id;
            extra_context['path'] = request.path;
            extra_context['modules'] = get_accessble_modules(request,sel_mod=app_label,sel_action=action,client_name=self.CLIENT)
            context.update(extra_context or {})

            return TemplateResponse(request, self.app_index_template or [
                template,
                'client/%s/%s/%s.html' % (self.CLIENT.lower(),app_label.lower(),action.lower()),
                'base_templates/%s/%s.html' % (app_label.lower(),action.lower()),
                'client/%s/index.html' % (self.CLIENT.lower()),
                'base_templates/app_index.html',
            ], context, current_app=self.name)
        else:
            context = {
                'error':'Permission denied',
                'home_url': url
            }
            return error_template('403',request=request,context=context,label='error')
            #raise Http404('!!!permission denied!!!')
            #raise Unauthorized("Permission denied")

# This global object represents the default admin site, for the common case.
# You can instantiate AdminSite in your own code to create a custom admin site.
usersite = CustomerView()
