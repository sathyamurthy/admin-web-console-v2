from django.db import transaction
from django.conf import settings
from django.contrib import admin
from Core.Clients.models import ClientInformation


class ClientInformationAdmin(admin.ModelAdmin):
    """A form for creating new users. Includes all the required
    fields, plus a repeated password."""

    class Meta:
        model = ClientInformation

    def save(self, commit=True):
        # Save the provided password in hashed format
        user = super(ClientInformationAdmin, self).save(commit=False)
        if commit:
            user.save()
        return user
admin.site.register(ClientInformation,ClientInformationAdmin)
