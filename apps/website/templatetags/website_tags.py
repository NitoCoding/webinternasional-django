from django import template

register = template.Library()


@register.filter
def str_limit(value, limit=100):
    """Pengganti Str::limit() di Laravel: potong ke `limit` karakter, lalu tambahkan '...' jika terpotong."""
    text = str(value or "")
    limit = int(limit)
    return text[:limit] + "..." if len(text) > limit else text


@register.filter
def split_lines(value):
    """Pengganti *_array di Laravel: pecah teks per baris dan buang baris kosong."""
    return [line.strip() for line in str(value or "").splitlines() if line.strip()]
