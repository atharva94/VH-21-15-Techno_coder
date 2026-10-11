from django.contrib import admin

from .models import College, Cutoff, StudentProfile


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("full_name", "user", "category", "city")
    search_fields = ("full_name", "user__username", "user__email", "city")
    list_filter = ("category", "city")


@admin.register(College)
class CollegeAdmin(admin.ModelAdmin):
    list_display = ("institute_code", "name", "city")
    search_fields = ("institute_code", "name", "city")
    list_filter = ("city",)


@admin.register(Cutoff)
class CutoffAdmin(admin.ModelAdmin):
    list_display = (
        "college",
        "course_name",
        "admission_year",
        "cap_round",
        "admission_pool",
        "category",
        "seat_type",
        "exam",
        "score_basis",
        "cutoff_score",
    )
    search_fields = ("college__name", "college__institute_code", "course_name", "category")
    list_filter = (
        "admission_year",
        "cap_round",
        "admission_pool",
        "category",
        "exam",
        "score_basis",
    )
