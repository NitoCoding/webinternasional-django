from django.contrib import admin

from .models import Faculty, IeProgram, Staff, Student, StudyProgram

admin.site.register(Faculty)
admin.site.register(StudyProgram)
admin.site.register(IeProgram)
admin.site.register(Staff)
admin.site.register(Student)
