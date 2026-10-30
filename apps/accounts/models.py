from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Pengguna aplikasi. Menggantikan tabel `users` Laravel.

    Role (admin, staff, student) dikelola lewat Group Django,
    dan permission kustom (pengganti Spatie) didefinisikan di sini.
    """

    name = models.CharField(max_length=255, blank=True)
    email = models.EmailField("email address", unique=True)

    class Meta(AbstractUser.Meta):
        swappable = "AUTH_USER_MODEL"
        permissions = [
            ("manage_news", "Dapat mengelola berita"),
            ("manage_event", "Dapat mengelola event"),
            ("manage_program", "Dapat mengelola program"),
            ("manage_class", "Dapat mengelola kelas"),
            ("choose_program", "Dapat memilih program"),
            ("manage_user", "Dapat mengelola user"),
        ]

    def has_role(self, role_name: str) -> bool:
        """Pengganti $user->hasRole() dari Spatie."""
        return self.groups.filter(name=role_name).exists()

    def __str__(self):
        return self.name or self.username
