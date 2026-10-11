from django.urls import path

from . import views


urlpatterns = [
    path("", views.index, name="index"),
    path("login/", views.StudentLoginView.as_view(), name="login"),
    path("logout/", views.StudentLogoutView.as_view(), name="logout"),
    path("signup/", views.signup, name="signup"),
    path("results/", views.results, name="results"),
    path("colleges/<int:college_id>/", views.college_detail, name="college_detail"),
]
