from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.academic.models import StudyProgram
from apps.core.models import TimeStampedModel


class News(TimeStampedModel):
    title = models.CharField(max_length=255)
    content = models.TextField()
    publication_date = models.DateTimeField(default=timezone.now)
    image = models.ImageField(upload_to="news/", max_length=255)
    views = models.PositiveIntegerField(default=0)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="news")
    study_program = models.ForeignKey(StudyProgram, on_delete=models.PROTECT, related_name="news")

    class Meta:
        verbose_name_plural = "news"

    def __str__(self):
        return self.title


class Event(TimeStampedModel):
    title = models.CharField(max_length=255)
    content = models.TextField()
    event_date = models.DateTimeField()
    publication_date = models.DateTimeField(default=timezone.now)
    image = models.ImageField(upload_to="events/", max_length=255)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="events")
    study_program = models.ForeignKey(StudyProgram, on_delete=models.PROTECT, related_name="events")

    def __str__(self):
        return self.title


class Agenda(TimeStampedModel):
    title = models.CharField(max_length=255)
    description = models.TextField()
    start = models.DateTimeField()
    end = models.DateTimeField()

    def __str__(self):
        return self.title


class SiteSetting(TimeStampedModel):
    class Type(models.TextChoices):
        TEXT = "text", "Text"
        IMAGE = "image", "Image"
        HTML = "html", "HTML"

    key = models.CharField(max_length=255, unique=True)
    value = models.TextField(blank=True, null=True)
    type = models.CharField(max_length=10, choices=Type.choices, default=Type.TEXT)

    def __str__(self):
        return self.key

    @classmethod
    def get(cls, key, default=None):
        """Pengganti SiteSetting::get() di Laravel."""
        value = cls.objects.filter(key=key).values_list("value", flat=True).first()
        return value if value not in (None, "") else default

    @classmethod
    def get_all_with_defaults(cls, defaults):
        """Pengganti SiteSetting::getAllWithDefaults()."""
        stored = dict(cls.objects.filter(key__in=defaults.keys()).values_list("key", "value"))
        return {k: (stored.get(k) or v) for k, v in defaults.items()}

