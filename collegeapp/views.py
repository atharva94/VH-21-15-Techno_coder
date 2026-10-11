from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import RecommendationFilterForm, SignUpForm, StudentProfileForm
from .models import College, Cutoff, StudentProfile
from .services import get_recommendations


class StudentLoginView(LoginView):
    template_name = "login.html"


class StudentLogoutView(LogoutView):
    next_page = "index"


@require_http_methods(["GET", "POST"])
def signup(request):
    if request.user.is_authenticated:
        return redirect("index")

    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        StudentProfile.objects.create(
            user=user,
            full_name="{} {}".format(user.first_name, user.last_name).strip(),
            hsc_percentage=0,
        )
        login(request, user)
        messages.success(request, "Your account is ready. Complete your student profile.")
        return redirect("index")
    return render(request, "signup.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def index(request):
    profile, _ = StudentProfile.objects.get_or_create(
        user=request.user,
        defaults={
            "full_name": request.user.get_full_name() or request.user.get_username(),
            "hsc_percentage": 0,
        },
    )
    form = StudentProfileForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        student_profile = form.save(commit=False)
        student_profile.user = request.user
        student_profile.save()
        messages.success(request, "Your profile has been saved.")
        return redirect("results")
    return render(request, "index.html", {"form": form})


@login_required
@require_http_methods(["GET"])
def results(request):
    profile = get_object_or_404(StudentProfile, user=request.user)
    years = list(
        Cutoff.objects.order_by("-admission_year")
        .values_list("admission_year", flat=True)
        .distinct()
    )
    filters = RecommendationFilterForm(request.GET, years=years)
    if filters.is_valid():
        selected_year = filters.cleaned_data["year"] or (years[0] if years else "")
        recommendations = get_recommendations(
            profile,
            admission_year=selected_year,
            city=filters.cleaned_data["city"],
            branch=filters.cleaned_data["branch"],
            min_cutoff=filters.cleaned_data["min_cutoff"],
            max_cutoff=filters.cleaned_data["max_cutoff"],
        )
    else:
        selected_year = request.GET.get("year", "")
        recommendations = []
    return render(
        request,
        "results.html",
        {
            "profile": profile,
            "recommendations": recommendations,
            "years": years,
            "selected_year": selected_year,
            "filters": filters,
        },
    )


@login_required
@require_http_methods(["GET"])
def college_detail(request, college_id):
    college = get_object_or_404(College, pk=college_id)
    cutoffs = college.cutoffs.order_by(
        "-admission_year", "cap_round", "course_name", "category"
    )
    return render(request, "college_detail.html", {"college": college, "cutoffs": cutoffs})
