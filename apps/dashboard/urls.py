from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import include, path, reverse
from django.views.decorators.http import require_http_methods, require_POST

from apps.academic.models import Staff, Student, StudyProgram
from apps.academic.study_program_csv import search_s1_programs
from apps.accounts.models import User
from apps.content.models import SiteSetting
from apps.international.models import (
    OutboundLecturer,
    Partnership,
    Program,
    ProgramEnrollment,
)
from apps.website.context_processors import FOOTER_DEFAULTS
from apps.website.views import SETTING_DEFAULTS, about_image_url

from .crud import USER_TABS, _is_admin, crud_urlpatterns
from .dashboard_stats import STATUS_OPTIONS, admin_dashboard_context
from .forms import SiteSettingsForm
from .user_services import manageable_student
from .logbook_views import (
    admin_certificate_view,
    admin_student_logbook,
    student_certificate_upload,
    student_certificate_view,
    student_logbook_create,
    student_logbook_delete,
    student_logbook_edit,
    student_logbook_list,
)
from .student_programs import (
    student_program_enroll,
    student_program_list,
    student_program_show,
    student_register,
)
from .student_calendar import student_calendar, student_calendar_events
from .student_views import (
    student_dashboard_data,
    student_study_plan,
    student_study_plan_data,
    student_transcript,
    student_transcript_data,
)
from .user_views import (
    add_staff,
    add_student,
    english_score,
    student_detail,
    upload_csv,
    users_print,
)


@login_required
def study_program_autocomplete(request):
    user = request.user
    if not (_is_admin(user) or user.has_perm("accounts.manage_program")):
        return JsonResponse({"detail": "Forbidden"}, status=403)
    return JsonResponse(search_s1_programs(request.GET.get("query", "")), safe=False)


@login_required
def home(request):
    """Dashboard per role, urutan pengecekan sama dengan DashboardController Laravel: admin, staff, student."""
    user = request.user
    status = request.GET.get("status", "all")
    if status not in dict(STATUS_OPTIONS):
        status = "all"

    if _is_admin(user):
        return render(request, "dashboard/home.html", admin_dashboard_context(None, status, is_admin=True))

    if user.has_role("staff"):
        staff = Staff.objects.filter(user=user).select_related("study_program").first()
        if staff is None:
            return render(request, "dashboard/home.html", {
                "no_staff_profile": True,
                "is_admin": False,
                "status": status,
                "status_options": STATUS_OPTIONS,
            })
        return render(
            request, "dashboard/home.html",
            admin_dashboard_context(staff.study_program, status, is_admin=False),
        )

    if user.has_role("student"):
        return render(request, "dashboard/student_home.html", {
            "nim": user.username,
            "name": user.name,
            "email": user.email,
            "data_url": reverse("dashboard:student_dashboard_data"),
        })

    raise PermissionDenied



@login_required
def site_settings(request):
    if not _is_admin(request.user):
        raise PermissionDenied

    if request.method == "POST":
        form = SiteSettingsForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Settings saved successfully!")
            return redirect("dashboard:site_settings_list")
    else:
        defaults = {**SETTING_DEFAULTS, **FOOTER_DEFAULTS}
        form = SiteSettingsForm(initial=SiteSetting.get_all_with_defaults(defaults))

    image_path = SiteSetting.get("about_image", SETTING_DEFAULTS["about_image"])
    return render(
        request,
        "dashboard/site_settings/index.html",
        {"form": form, "image_url": about_image_url(image_path)},
    )


def _manageable_program(request, pk):
    user = request.user
    if not (_is_admin(user) or user.has_perm("accounts.manage_program")):
        raise PermissionDenied
    program = get_object_or_404(Program, pk=pk)
    if not _is_admin(user) and program.created_by_id != user.pk:
        raise PermissionDenied
    return program


@login_required
@require_POST
def program_enrollment_action(request, pk, enrollment_pk):
    program = _manageable_program(request, pk)
    enrollment = get_object_or_404(ProgramEnrollment, pk=enrollment_pk, program=program)
    action = request.POST.get("action")
    status = request.POST.get("status")

    if status == ProgramEnrollment.Status.APPROVED:
        enrollment.status = ProgramEnrollment.Status.APPROVED
        enrollment.save(update_fields=["status"])
        ProgramEnrollment.objects.filter(student=enrollment.student).exclude(
            pk=enrollment.pk
        ).exclude(status=ProgramEnrollment.Status.APPROVED).delete()
        approved_count = program.enrollments.filter(
            status=ProgramEnrollment.Status.APPROVED
        ).count()
        if approved_count >= program.participants_count:
            program.enrollments.filter(status=ProgramEnrollment.Status.PENDING).delete()
        messages.success(request, "Student has been approved.")
    elif status == ProgramEnrollment.Status.REJECTED:
        enrollment.delete()
        messages.success(request, "Student has been rejected.")
    elif action in ("finish", "unfinish"):
        enrollment.is_finished = action == "finish"
        enrollment.save(update_fields=["is_finished"])
        messages.success(request, "Student status has been updated.")
    elif action == "delete":
        enrollment.delete()
        messages.success(request, "Student has been removed from the program.")
    else:
        messages.error(request, "Invalid action.")
    return redirect("dashboard:programs_detail", pk=program.pk)


@login_required
@require_POST
def program_add_student(request, pk):
    program = _manageable_program(request, pk)
    nim = request.POST.get("nim", "").strip()
    detail_url = redirect("dashboard:programs_detail", pk=program.pk)

    student = (
        Student.objects.filter(student_id_number=nim)
        .select_related("study_program")
        .first()
    )
    if not student:
        messages.error(request, "Student with this NIM was not found.")
        return detail_url

    approved_count = program.enrollments.filter(
        status=ProgramEnrollment.Status.APPROVED
    ).count()
    if approved_count >= program.participants_count:
        messages.error(
            request, "This program has reached its maximum participant limit."
        )
        return detail_url
    if program.enrollments.filter(student=student).exists():
        messages.error(request, "This student is already enrolled in this program.")
        return detail_url
    if not program.study_programs.filter(pk=student.study_program_id).exists():
        messages.error(request, "Student's study program does not match this program.")
        return detail_url

    ProgramEnrollment.objects.create(
        program=program,
        student=student,
        status=ProgramEnrollment.Status.APPROVED,
        is_finished=True,
    )
    messages.success(request, "Student has been added to the program.")
    return detail_url


def _study_program_detail_redirect(pk):
    return redirect("dashboard:study_programs_detail", pk=pk)


@login_required
@require_POST
def study_program_add_partnership(request, pk):
    if not _is_admin(request.user) and not request.user.has_perm(
        "accounts.manage_program"
    ):
        raise PermissionDenied
    study_program = get_object_or_404(StudyProgram, pk=pk)
    number = request.POST.get("mou_moa_ia_number", "").strip()
    title = request.POST.get("title_of_cooperation", "").strip()
    validity = request.POST.get("validity_period", "").strip()
    if not (number and title and validity):
        messages.error(request, "All fields are required.")
    elif not validity.isdigit() or int(validity) > 32767:
        messages.error(request, "Validity Period must be a whole number.")
    else:
        Partnership.objects.create(
            study_program=study_program,
            mou_moa_ia_number=number,
            title_of_cooperation=title,
            validity_period=int(validity),
        )
        messages.success(request, "Partnership added successfully")
    return _study_program_detail_redirect(study_program.pk)


@login_required
@require_POST
def study_program_add_outbound_lecturer(request, pk):
    if not _is_admin(request.user) and not request.user.has_perm(
        "accounts.manage_program"
    ):
        raise PermissionDenied
    study_program = get_object_or_404(StudyProgram, pk=pk)
    data = {
        key: request.POST.get(key, "").strip()
        for key in (
            "lecturer_name",
            "gender",
            "role_in_ki",
            "university_name",
            "activity_year",
        )
    }
    if not all(data.values()):
        messages.error(request, "All fields are required.")
    elif data["gender"] not in ("Male", "Female"):
        messages.error(request, "Gender must be Male or Female.")
    elif not data["activity_year"].isdigit() or int(data["activity_year"]) > 32767:
        messages.error(request, "Activity Year must be a whole number.")
    else:
        OutboundLecturer.objects.create(
            study_program=study_program,
            lecturer_name=data["lecturer_name"],
            gender=data["gender"],
            role_in_ki=data["role_in_ki"],
            university_name=data["university_name"],
            activity_year=int(data["activity_year"]),
        )
        messages.success(request, "Outbound Lecturer added successfully")
    return _study_program_detail_redirect(study_program.pk)


def _manageable_student(request, pk):
    return manageable_student(request.user, pk)


def _choose_program_permission():
    return Permission.objects.get(codename="choose_program", content_type__app_label="accounts")


def _back_to_users(request, tab):
    if tab not in USER_TABS:
        tab = "all"
    return redirect(f"{reverse('dashboard:users_list')}?tab={tab}")


def _confirm_user_action(request, student_user, action):
    student = student_user.student
    if action == "accept":
        title = "Accept student?"
        message = (
            "This student will be verified and active, and can enroll in programs. "
            "Only students in your study program can be accepted by staff."
        )
        button = "Yes, accept"
        button_class = "bg-green-600 hover:bg-green-700"
    else:
        title = "Reject student?"
        message = "This student will be deactivated and will not be able to log in."
        button = "Yes, reject"
        button_class = "bg-red-600 hover:bg-red-700"
    return render(
        request,
        "dashboard/users/confirm_action.html",
        {
            "title": title,
            "message": message,
            "button": button,
            "button_class": button_class,
            "student_user": student_user,
            "student": student,
            "action_url": request.path,
            "cancel_url": f"{reverse('dashboard:users_list')}?tab=waiting",
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def user_accept(request, pk):
    student_user, student = _manageable_student(request, pk)
    if request.method == "GET":
        return _confirm_user_action(request, student_user, "accept")
    student.status = Student.Status.ACCEPTED
    student.is_verified = True
    student.is_active = True
    student.save()
    student_user.is_active = True
    student_user.save(update_fields=["is_active"])
    student_user.user_permissions.add(_choose_program_permission())
    messages.success(request, "Student has been accepted.")
    return _back_to_users(request, "waiting")


@login_required
@require_http_methods(["GET", "POST"])
def user_reject(request, pk):
    student_user, student = _manageable_student(request, pk)
    if request.method == "GET":
        return _confirm_user_action(request, student_user, "reject")
    student.status = Student.Status.REJECTED
    student.is_verified = False
    student.is_active = False
    student.save()
    student_user.is_active = False
    student_user.save(update_fields=["is_active"])
    student_user.user_permissions.remove(_choose_program_permission())
    messages.success(request, "Student has been rejected.")
    return _back_to_users(request, "waiting")


@login_required
@require_POST
def user_toggle_active(request, pk):
    student_user, student = _manageable_student(request, pk)
    new_state = not student.is_active
    student.is_active = new_state
    student.save()
    student_user.is_active = new_state
    student_user.save(update_fields=["is_active"])
    messages.success(request, "Student has been activated." if new_state else "Student has been deactivated.")
    return _back_to_users(request, request.POST.get("tab", "all"))


app_name = "dashboard"


urlpatterns = [
    path("", home, name="home"),
    path(
        "study-programs/autocomplete/",
        study_program_autocomplete,
        name="study_program_autocomplete",
    ),
    path("site-settings/", site_settings, name="site_settings_list"),
    path("users/<int:pk>/accept/", user_accept, name="user_accept"),
    path("users/<int:pk>/reject/", user_reject, name="user_reject"),
    path("users/<int:pk>/toggle-active/", user_toggle_active, name="user_toggle_active"),
    path("users/add-student/", add_student, name="user_add_student"),
    path("users/upload-csv/", upload_csv, name="user_upload_csv"),
    path("users/add-staff/", add_staff, name="user_add_staff"),
    path("users/print/", users_print, name="user_print"),
    path("users/<int:pk>/detail/", student_detail, name="user_detail"),
    path("users/<int:pk>/english-score/", english_score, name="user_english_score"),
    path("student/transcript/", student_transcript, name="student_transcript"),
    path("student/dashboard/data/", student_dashboard_data, name="student_dashboard_data"),
    path("student/transcript/data/", student_transcript_data, name="student_transcript_data"),
    path("student/study-plan/", student_study_plan, name="student_study_plan"),
    path("student/study-plan/data/", student_study_plan_data, name="student_study_plan_data"),
    path("student/programs/", student_program_list, name="student_programs"),
    path("student/programs/<int:pk>/", student_program_show, name="student_program_show"),
    path("student/programs/<int:pk>/enroll/", student_program_enroll, name="student_program_enroll"),
    path("student/register/", student_register, name="student_register"),
    path("student/calendar/", student_calendar, name="student_calendar"),
    path("student/calendar/events/", student_calendar_events, name="student_calendar_events"),
    path("student/programs/<int:pk>/logbook/", student_logbook_list, name="student_logbook_list"),
    path("student/programs/<int:pk>/logbook/new/", student_logbook_create, name="student_logbook_create"),
    path("student/programs/<int:pk>/logbook/<int:lid>/edit/", student_logbook_edit, name="student_logbook_edit"),
    path("student/programs/<int:pk>/logbook/<int:lid>/delete/", student_logbook_delete, name="student_logbook_delete"),
    path("student/programs/<int:pk>/certificate/", student_certificate_upload, name="student_certificate_upload"),
    path("student/programs/<int:pk>/certificate/view/", student_certificate_view, name="student_certificate_view"),
    path("programs/<int:pk>/students/<int:uid>/logbook/", admin_student_logbook, name="admin_student_logbook"),
    path("programs/<int:pk>/students/<int:uid>/certificate/", admin_certificate_view, name="admin_certificate_view"),
    path(
        "programs/<int:pk>/enrollments/<int:enrollment_pk>/action/",
        program_enrollment_action,
        name="program_enrollment_action",
    ),
    path(
        "programs/<int:pk>/add-student/",
        program_add_student,
        name="program_add_student",
    ),
    path(
        "study-programs/<int:pk>/partnerships/",
        study_program_add_partnership,
        name="study_program_add_partnership",
    ),
    path(
        "study-programs/<int:pk>/outbound-lecturers/",
        study_program_add_outbound_lecturer,
        name="study_program_add_outbound_lecturer",
    ),
    *crud_urlpatterns(),
]
