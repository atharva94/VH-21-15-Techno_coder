from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class StudentProfile(models.Model):
    ADMISSION_POOLS = [
        ("MH", "Maharashtra state CAP"),
        ("AI", "All India"),
    ]
    CATEGORIES = [
        ("OPEN", "Open"),
        ("EWS", "EWS"),
        ("SC", "SC"),
        ("ST", "ST"),
        ("VJ", "VJ/DT (NT-A)"),
        ("NT-B", "NT-B"),
        ("NT-C", "NT-C"),
        ("NT-D", "NT-D"),
        ("OBC", "OBC"),
        ("SEBC", "SEBC"),
    ]
    SCORE_BASES = [
        ("percentile", "Percentile"),
        ("rank", "Rank"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="student_profile"
    )
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30, blank=True)
    category = models.CharField(max_length=10, choices=CATEGORIES, default="OPEN")
    admission_pool = models.CharField(
        max_length=2, choices=ADMISSION_POOLS, default="MH"
    )
    hsc_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, validators=[MinValueValidator(0)]
    )
    city = models.CharField(max_length=100, blank=True)
    preferred_branch = models.CharField(max_length=150, blank=True)
    mht_cet_score = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    mht_cet_basis = models.CharField(max_length=12, choices=SCORE_BASES, default="percentile")
    jee_score = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    jee_basis = models.CharField(max_length=12, choices=SCORE_BASES, default="percentile")

    class Meta:
        ordering = ["full_name"]

    def clean(self):
        errors = {}
        if self.hsc_percentage is not None and self.hsc_percentage > 100:
            errors["hsc_percentage"] = "Percentage cannot exceed 100."
        for field, basis_field in (
            ("mht_cet_score", "mht_cet_basis"),
            ("jee_score", "jee_basis"),
        ):
            score = getattr(self, field)
            basis = getattr(self, basis_field)
            if score is None:
                continue
            if basis == "percentile" and score > 100:
                errors[field] = "A percentile must be between 0 and 100."
            elif basis == "rank" and score < 1:
                errors[field] = "A rank must be at least 1."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.full_name


class College(models.Model):
    institute_code = models.CharField(max_length=20, unique=True, null=True, blank=True)
    name = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    address = models.TextField(blank=True)
    website = models.URLField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        if self.institute_code:
            return "{} ({})".format(self.name, self.institute_code)
        return self.name


class Cutoff(models.Model):
    EXAMS = [
        ("MHT-CET", "MHT-CET"),
        ("JEE Main", "JEE Main"),
    ]
    SCORE_BASES = StudentProfile.SCORE_BASES
    CATEGORIES = StudentProfile.CATEGORIES
    ADMISSION_POOLS = StudentProfile.ADMISSION_POOLS

    college = models.ForeignKey(College, on_delete=models.CASCADE, related_name="cutoffs")
    course_name = models.CharField(max_length=200)
    admission_year = models.CharField(max_length=9, help_text="For example: 2026-27")
    cap_round = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    admission_pool = models.CharField(max_length=2, choices=ADMISSION_POOLS, default="MH")
    category = models.CharField(
        max_length=10,
        choices=CATEGORIES,
        help_text="Normalized student category used for matching.",
    )
    seat_type = models.CharField(
        max_length=30,
        blank=True,
        help_text="Exact seat-type/category code from the official cutoff, if provided.",
    )
    exam = models.CharField(max_length=12, choices=EXAMS)
    score_basis = models.CharField(max_length=12, choices=SCORE_BASES)
    cutoff_score = models.DecimalField(
        max_digits=10, decimal_places=3, validators=[MinValueValidator(0)]
    )
    source_url = models.URLField(help_text="Official source document or data page.")
    source_notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["college__name", "course_name", "category"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "college",
                    "course_name",
                    "admission_year",
                    "cap_round",
                    "admission_pool",
                    "category",
                    "seat_type",
                    "exam",
                    "score_basis",
                ],
                name="unique_college_course_cutoff",
            )
        ]
        indexes = [
            models.Index(
                fields=["admission_year", "cap_round", "admission_pool", "exam", "score_basis"],
                name="cutoff_admission_lookup",
            )
        ]

    def clean(self):
        if self.cutoff_score is None:
            return
        if self.cutoff_score < 0:
            raise ValidationError({"cutoff_score": "A cutoff cannot be negative."})
        if self.score_basis == "percentile" and self.cutoff_score > 100:
            raise ValidationError({"cutoff_score": "A percentile cutoff cannot exceed 100."})
        if self.score_basis == "rank" and self.cutoff_score < 1:
            raise ValidationError({"cutoff_score": "A rank cutoff must be at least 1."})

    def __str__(self):
        return "{} - {} ({}, CAP {})".format(
            self.college.name, self.course_name, self.category, self.cap_round
        )
