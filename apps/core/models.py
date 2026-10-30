from django.db import models


class TimeStampedModel(models.Model):
    """Dasar untuk model dengan created_at/updated_at (sama seperti timestamps() di Laravel)."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
