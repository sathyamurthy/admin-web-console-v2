import urllib

from django.core.exceptions import ImproperlyConfigured
from django.db import models
from Core.Countries.models import WorldCountries
from jsonfield import JSONField
from django.core.validators import URLValidator

class ClientInformation(models.Model):
    name = models.CharField(max_length=120,unique=True,null=False)
    country = models.ForeignKey(WorldCountries,blank=False)
    url = models.CharField(max_length=120,unique=True,null=False)
    domain = models.CharField(max_length=255, validators=[URLValidator])
    properties = JSONField(default=None)
    class Meta:
        verbose_name = 'Client information'
        verbose_name_plural = 'Client informations'

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        return self.name

    def __unicode__(self):
        return self.name



