from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import StudentProfile


class SignUpForm(UserCreationForm):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email")


class StudentProfileForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = (
            "full_name",
            "phone",
            "category",
            "admission_pool",
            "hsc_percentage",
            "city",
            "preferred_branch",
            "mht_cet_score",
            "mht_cet_basis",
            "jee_score",
            "jee_basis",
        )
        widgets = {
            "hsc_percentage": forms.NumberInput(attrs={"min": "0", "max": "100", "step": "0.01"}),
            "mht_cet_score": forms.NumberInput(attrs={"min": "0", "step": "0.001"}),
            "jee_score": forms.NumberInput(attrs={"min": "0", "step": "0.001"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        cet_score = cleaned_data.get("mht_cet_score")
        jee_score = cleaned_data.get("jee_score")

        if cet_score is None and jee_score is None:
            raise forms.ValidationError("Enter at least one MHT-CET or JEE Main score.")

        for exam, score, basis in (
            ("MHT-CET", cet_score, cleaned_data.get("mht_cet_basis")),
            ("JEE Main", jee_score, cleaned_data.get("jee_basis")),
        ):
            if score is not None and basis == "rank" and score < 1:
                self.add_error(
                    "mht_cet_score" if exam == "MHT-CET" else "jee_score",
                    "A rank must be at least 1.",
                )
        hsc_percentage = cleaned_data.get("hsc_percentage")
        if hsc_percentage is not None and hsc_percentage > 100:
            self.add_error("hsc_percentage", "Percentage cannot exceed 100.")
        return cleaned_data


class RecommendationFilterForm(forms.Form):
    year = forms.ChoiceField(required=False)
    city = forms.CharField(required=False, max_length=100)
    branch = forms.CharField(required=False, max_length=150)
    min_cutoff = forms.DecimalField(required=False, min_value=0, max_digits=10, decimal_places=3)
    max_cutoff = forms.DecimalField(required=False, min_value=0, max_digits=10, decimal_places=3)

    def __init__(self, *args, years=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["year"].choices = [("", "Latest available")] + [
            (year, year) for year in years
        ]
        self.fields["year"].widget.attrs["class"] = "form-select"
        for field in ("city", "branch", "min_cutoff", "max_cutoff"):
            self.fields[field].widget.attrs["class"] = "form-control"

    def clean(self):
        cleaned_data = super().clean()
        minimum = cleaned_data.get("min_cutoff")
        maximum = cleaned_data.get("max_cutoff")
        if minimum is not None and maximum is not None and minimum > maximum:
            raise forms.ValidationError("Minimum cutoff must not exceed maximum cutoff.")
        return cleaned_data
