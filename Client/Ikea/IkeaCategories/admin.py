from django.conf import settings
from django.contrib import admin
from Core.Taxonomy.models import Taxonomy
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django import forms
from mptt.admin import MPTTModelAdmin
from Client.Ikea.IkeaCategories.models import Categories,IkeaMarkets

import sys 

class CategoriesAdmin(MPTTModelAdmin):
    """A form for creating new users. Includes all the required
    fields, plus a repeated password."""

    class Meta:
        model = Categories

    def save(self, commit=True):
        # Save the provided password in hashed format
        user = super(CategoriesAdmin, self).save(commit=False)
        if commit:
            user.save()
        return user

class IkeaMarketsAdmin(admin.ModelAdmin):
    """A form for creating new users. Includes all the required
    fields, plus a repeated password."""

    class Meta:
        model = IkeaMarkets

    def save(self, commit=True):
        # Save the provided password in hashed format
        user = super(IkeaMarketsAdmin, self).save(commit=False)
        if commit:
            user.save()
        return user
admin.site.register(Categories,CategoriesAdmin)
admin.site.register(IkeaMarkets,IkeaMarketsAdmin)

