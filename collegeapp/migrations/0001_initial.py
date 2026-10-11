from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="College",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("institute_code", models.CharField(blank=True, max_length=20, null=True, unique=True)),
                ("name", models.CharField(max_length=255)),
                ("city", models.CharField(max_length=100)),
                ("address", models.TextField(blank=True)),
                ("website", models.URLField(blank=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="StudentProfile",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("full_name", models.CharField(max_length=150)),
                ("phone", models.CharField(blank=True, max_length=30)),
                ("category", models.CharField(choices=[("OPEN", "Open"), ("EWS", "EWS"), ("SC", "SC"), ("ST", "ST"), ("VJ", "VJ/DT (NT-A)"), ("NT-B", "NT-B"), ("NT-C", "NT-C"), ("NT-D", "NT-D"), ("OBC", "OBC"), ("SEBC", "SEBC")], default="OPEN", max_length=10)),
                ("admission_pool", models.CharField(choices=[("MH", "Maharashtra state CAP"), ("AI", "All India")], default="MH", max_length=2)),
                ("hsc_percentage", models.DecimalField(decimal_places=2, max_digits=5, validators=[MinValueValidator(0)])),
                ("city", models.CharField(blank=True, max_length=100)),
                ("preferred_branch", models.CharField(blank=True, max_length=150)),
                ("mht_cet_score", models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True, validators=[MinValueValidator(0)])),
                ("mht_cet_basis", models.CharField(choices=[("percentile", "Percentile"), ("rank", "Rank")], default="percentile", max_length=12)),
                ("jee_score", models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True, validators=[MinValueValidator(0)])),
                ("jee_basis", models.CharField(choices=[("percentile", "Percentile"), ("rank", "Rank")], default="percentile", max_length=12)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="student_profile", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["full_name"]},
        ),
        migrations.CreateModel(
            name="Cutoff",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("course_name", models.CharField(max_length=200)),
                ("admission_year", models.CharField(help_text="For example: 2026-27", max_length=9)),
                ("cap_round", models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])),
                ("admission_pool", models.CharField(choices=[("MH", "Maharashtra state CAP"), ("AI", "All India")], default="MH", max_length=2)),
                ("category", models.CharField(choices=[("OPEN", "Open"), ("EWS", "EWS"), ("SC", "SC"), ("ST", "ST"), ("VJ", "VJ/DT (NT-A)"), ("NT-B", "NT-B"), ("NT-C", "NT-C"), ("NT-D", "NT-D"), ("OBC", "OBC"), ("SEBC", "SEBC")], help_text="Normalized student category used for matching.", max_length=10)),
                ("seat_type", models.CharField(blank=True, help_text="Exact seat-type/category code from the official cutoff, if provided.", max_length=30)),
                ("exam", models.CharField(choices=[("MHT-CET", "MHT-CET"), ("JEE Main", "JEE Main")], max_length=12)),
                ("score_basis", models.CharField(choices=[("percentile", "Percentile"), ("rank", "Rank")], max_length=12)),
                ("cutoff_score", models.DecimalField(decimal_places=3, max_digits=10, validators=[MinValueValidator(0)])),
                ("source_url", models.URLField(help_text="Official source document or data page.")),
                ("source_notes", models.CharField(blank=True, max_length=255)),
                ("college", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="cutoffs", to="collegeapp.college")),
            ],
            options={"ordering": ["college__name", "course_name", "category"]},
        ),
        migrations.AddConstraint(
            model_name="cutoff",
            constraint=models.UniqueConstraint(
                fields=("college", "course_name", "admission_year", "cap_round", "admission_pool", "category", "seat_type", "exam", "score_basis"),
                name="unique_college_course_cutoff",
            ),
        ),
        migrations.AddIndex(
            model_name="cutoff",
            index=models.Index(fields=["admission_year", "cap_round", "admission_pool", "exam", "score_basis"], name="cutoff_admission_lookup"),
        ),
    ]
