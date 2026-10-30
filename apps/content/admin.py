from django.contrib import admin

from .models import Agenda, Event, News, SiteSetting

admin.site.register(News)
admin.site.register(Event)
admin.site.register(Agenda)
admin.site.register(SiteSetting)
