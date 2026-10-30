"""
Membuat group role (admin, staff, student) dan memberi permission,
mengikuti mapping role_has_permissions dari Laravel/Spatie.

Pemakaian: uv run python manage.py seed_roles
"""

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from apps.accounts.models import User

ALL_PERMS = [
    "manage_news",
    "manage_event",
    "manage_program",
    "manage_class",
    "choose_program",
    "manage_user",
]

ROLE_PERMS = {
    "admin": ALL_PERMS,
    "staff": ["manage_news", "manage_event", "manage_program", "manage_class", "manage_user"],
    "student": ["choose_program"],
}


class Command(BaseCommand):
    help = "Membuat group role dan permission default."

    def handle(self, *args, **options):
        ct = ContentType.objects.get_for_model(User)
        perms = {p.codename: p for p in Permission.objects.filter(content_type=ct)}

        for role, codenames in ROLE_PERMS.items():
            group, _ = Group.objects.get_or_create(name=role)
            group.permissions.set([perms[c] for c in codenames])
            self.stdout.write(f"Group '{role}': {len(codenames)} permission")
