from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.db.models import F
from django.shortcuts import get_object_or_404, render
from django.templatetags.static import static

from apps.academic.models import IeProgram, StudyProgram
from apps.content.models import Event, News, SiteSetting
from apps.international.models import Partnership, Program

# Teks default halaman (sama dengan $settingDefaults di LandingPageController Laravel).
SETTING_DEFAULTS = {
    "about_title": "About International Class",
    "about_paragraph_1": (
        "The International Class is a separate program from regular classes, conducted in English or another "
        "foreign language as the medium of instruction. This program is specially designed to equip graduates "
        "with knowledge, skills, and proficiency in foreign languages, enabling them to compete in the global "
        "marketplace."
    ),
    "about_paragraph_2": (
        "Each student will participate in an international exposure activity, such as joint degrees, double "
        "degrees, sit-ins, internships, or other forms, at partner universities or institutions abroad, gaining "
        "valuable international learning experience."
    ),
    "about_image": "images/imageAbout.png",
    "ie_card_1_title": "Sit In Program",
    "ie_card_1_desc": "Short-term academic experience at international universities",
    "ie_card_2_title": "Internship Program",
    "ie_card_2_desc": "Professional work experience in multinational companies",
    "ie_card_3_title": "Short Course",
    "ie_card_3_desc": "Intensive learning programs on specialized topics",
    "ie_card_4_title": "Enrichment Program",
    "ie_card_4_desc": "Cultural and academic enrichment activities abroad",
}


def about_image_url(path):
    """Gambar hasil upload ada di MEDIA (settings/...), default ada di static."""
    return default_storage.url(path) if path.startswith("settings/") else static(path)


def site_settings():
    data = SiteSetting.get_all_with_defaults(SETTING_DEFAULTS)
    data["about_image_url"] = about_image_url(data["about_image"])
    return data


HOME_DESCRIPTION = (
    "Join our International Class to experience a world-class education, expert instructors, and a diverse "
    "community. Gain valuable skills, global insights, and hands-on learning opportunities that will prepare you "
    "for a bright future in an interconnected world."
)

DEGREE_TYPES = [
    Partnership.PartnershipType.DOUBLE_DEGREE,
    Partnership.PartnershipType.SINGLE_DEGREE,
    Partnership.PartnershipType.JOINT_DEGREE,
]


def format_idr(value):
    """Pengganti number_format($value, 2, ',', '.') di Laravel."""
    return f"{(value or 0):,.2f}".translate(str.maketrans({",": ".", ".": ","}))


def home(request):
    context = {
        "title": "International Class",
        "description": HOME_DESCRIPTION,
        "settings": site_settings(),
        "ie_programs": IeProgram.objects.all(),
        "study_programs": StudyProgram.objects.select_related("faculty"),
        "news": News.objects.order_by("-created_at")[:3],
        "events": Event.objects.order_by("-created_at")[:2],
        "available_programs": Program.objects.select_related("ie_program").order_by(
            "-created_at"
        )[:6],
    }
    return render(request, "website/home.html", context)


def about(request):
    return render(
        request,
        "website/about.html",
        {
            "title": "About",
            "description": (
                "The International Class at Hasanuddin University is a prestigious program established in 2006 to "
                "provide world-class education. It aims to produce globally competitive graduates through innovative "
                "learning, international collaborations, and a focus on the unique potential of the Indonesian "
                "Maritime Continent."
            ),
            "settings": site_settings(),
        },
    )


NEWS_DESCRIPTION = (
    "Explore the latest updates from Hasanuddin University International Class, featuring student "
    "achievements, international collaborations, and important developments that showcase our dedication "
    "to global academic excellence."
)
EVENT_DESCRIPTION = (
    "Discover upcoming activities and programs from Hasanuddin University International Class. From academic "
    "workshops to cultural exchanges, these events are designed to enhance learning experiences, foster global "
    "connections, and celebrate our diverse community."
)


def news_list(request):
    page = Paginator(News.objects.order_by("-created_at"), 4).get_page(
        request.GET.get("page")
    )
    popular = News.objects.order_by("-views")[:4]
    return render(
        request,
        "website/news_list.html",
        {
            "title": "News",
            "description": NEWS_DESCRIPTION,
            "page": page,
            "popular": popular,
        },
    )


def news_detail(request, pk):
    item = get_object_or_404(News, pk=pk)
    News.objects.filter(pk=pk).update(views=F("views") + 1)
    item.refresh_from_db(fields=["views"])
    return render(
        request,
        "website/news_detail.html",
        {"title": "News", "description": NEWS_DESCRIPTION, "item": item},
    )


def event_list(request):
    from django.utils import timezone

    page = Paginator(Event.objects.order_by("-created_at"), 4).get_page(
        request.GET.get("page")
    )
    upcoming = Event.objects.filter(event_date__gte=timezone.now()).order_by("-created_at")[:4]
    return render(
        request,
        "website/event_list.html",
        {
            "title": "Event",
            "description": EVENT_DESCRIPTION,
            "page": page,
            "upcoming": upcoming,
        },
    )


def event_detail(request, pk):
    item = get_object_or_404(Event, pk=pk)
    return render(
        request,
        "website/event_detail.html",
        {"title": "Event", "description": NEWS_DESCRIPTION, "item": item},
    )




def event_detail(request, pk):
    item = get_object_or_404(Event, pk=pk)
    return render(
        request, "website/event_detail.html", {"title": "Event", "item": item}
    )


def study_program_list(request):
    return render(
        request,
        "website/study_program_list.html",
        {
            "title": "Study Program",
            "study_programs": StudyProgram.objects.select_related("faculty"),
            "ie_programs": IeProgram.objects.all(),
        },
    )


def study_program_detail(request, pk):
    item = get_object_or_404(StudyProgram.objects.select_related("faculty"), pk=pk)
    return render(
        request,
        "website/study_program_detail.html",
        {
            "title": item.name,
            "item": item,
            "partnerships": item.partnerships.all(),
            "ukt_fee": format_idr(item.ukt_fee),
            "ipi_fee": format_idr(item.ipi_fee),
            "news": News.objects.filter(study_program=item).order_by("-created_at")[:3],
            "events": Event.objects.filter(study_program=item).order_by("-created_at")[
                :2
            ],
        },
    )


IE_DESCRIPTION = (
    "Join our International Class to experience a world-class education, expert instructors, and a diverse "
    "community. Gain valuable skills, global insights, and hands-on learning opportunities that will prepare "
    "you for a bright future in an interconnected world."
)


def _recommended_ie_programs(today):
    """Pengganti recommendedPrograms di LandingPageController Laravel: program mendatang yang sudah punya
    peserta approved, belum penuh, diurutkan dari peserta approved terbanyak, maksimal 5."""
    from django.db.models import Count, F, Q

    return (
        Program.objects.select_related("ie_program")
        .filter(execution_date__gt=today, study_programs__isnull=False, enrollments__status="approved")
        .annotate(
            approved_count=Count(
                "enrollments", filter=Q(enrollments__status="approved"), distinct=True
            )
        )
        .filter(approved_count__lt=F("participants_count"))
        .order_by("-approved_count")[:5]
    )


def ie_list(request):
    from django.utils import timezone

    today = timezone.localdate()
    page = Paginator(
        Program.objects.select_related("ie_program").order_by("-created_at"), 5
    ).get_page(request.GET.get("page"))
    return render(
        request,
        "website/ie_list.html",
        {
            "title": "International Exposure",
            "description": IE_DESCRIPTION,
            "page": page,
            "recommended_programs": _recommended_ie_programs(today),
            "new_programs": Program.objects.select_related("ie_program").order_by("-created_at")[:5],
        },
    )


def ie_detail(request, pk):
    from django.utils import timezone

    item = get_object_or_404(Program.objects.select_related("ie_program"), pk=pk)
    return render(
        request,
        "website/ie_detail.html",
        {
            "title": "International Exposure",
            "description": IE_DESCRIPTION,
            "item": item,
            "is_upcoming": item.execution_date > timezone.localdate(),
        },
    )


def degree_list(request):
    items = (
        Partnership.objects.filter(partnership_type__in=DEGREE_TYPES, is_active=True)
        .select_related("study_program")
        .order_by("-created_at")
    )
    return render(
        request,
        "website/degree_list.html",
        {
            "title": "Double / Joint Degree",
            "description": "Partnership programs with prestigious international "
            "universities offering dual qualifications and global academic experience.",
            "items": items,
            "double_items": [i for i in items if i.partnership_type == "double_degree"],
            "joint_items": [i for i in items if i.partnership_type == "joint_degree"],
        },
    )


def degree_detail(request, pk):
    item = get_object_or_404(
        Partnership.objects.select_related("study_program"),
        pk=pk,
        partnership_type__in=DEGREE_TYPES,
    )
    return render(
        request,
        "website/degree_detail.html",
        {
            "title": item.partner_university or "Degree Program",
            "item": item,
            "news": News.objects.filter(study_program=item.study_program).order_by(
                "-created_at"
            )[:3]
            if item.study_program_id
            else [],
            "events": Event.objects.filter(study_program=item.study_program).order_by(
                "-created_at"
            )[:2]
            if item.study_program_id
            else [],
        },
    )
