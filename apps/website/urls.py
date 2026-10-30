from django.urls import path

from . import views

app_name = "website"

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("news/", views.news_list, name="news_list"),
    path("news/<int:pk>/", views.news_detail, name="news_detail"),
    path("events/", views.event_list, name="event_list"),
    path("events/<int:pk>/", views.event_detail, name="event_detail"),
    path("study-programs/", views.study_program_list, name="study_program_list"),
    path("study-programs/<int:pk>/", views.study_program_detail, name="study_program_detail"),
    path("international-exposure/", views.ie_list, name="ie_list"),
    path("international-exposure/<int:pk>/", views.ie_detail, name="ie_detail"),
    path("degree-programs/", views.degree_list, name="degree_list"),
    path("degree-programs/<int:pk>/", views.degree_detail, name="degree_detail"),
]
