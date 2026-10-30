from django.contrib import admin

from .models import Logbook, OutboundLecturer, Partnership, Program, ProgramEnrollment

admin.site.register(Program)
admin.site.register(ProgramEnrollment)
admin.site.register(Logbook)
admin.site.register(Partnership)
admin.site.register(OutboundLecturer)
