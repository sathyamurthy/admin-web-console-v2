from django.db import models
from django.db.models.manager import EmptyManager
from django.utils.translation import ugettext_lazy as _

from jsonfield import JSONField
from Core.Taxonomy.models import Taxonomy
from Core.Countries.models import WorldCountries
#from Client.Ikea.Users.models import Market
import sys

class Categories(Taxonomy):
    available_to_market = models.ManyToManyField('IkeaMarkets', blank=True)
    class Meta:
        verbose_name = _('Ikea book catagory')
        verbose_name_plural = _('Ikea book catagories')
    
class IkeaMarkets(models.Model):
    name = models.CharField(max_length=120)
    country = models.ForeignKey(WorldCountries,blank=False)
    market_settings = JSONField(default=None)
    class Meta:
        verbose_name = _('Ikea Market')
        verbose_name_plural = _('Ikea Markets ')
        unique_together = (('name', 'country'),)

    def get_full_name(self):
        # The user is identified by their email address
        return self.name

    def get_short_name(self):
        # The user is identified by their email address
        return self.name

    def __unicode__(self):
        return self.name
