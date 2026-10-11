import csv
from decimal import Decimal, InvalidOperation
import re

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import URLValidator
from django.db import transaction

from collegeapp.models import College, Cutoff, StudentProfile


class Command(BaseCommand):
    help = "Import verified college and cutoff records from a UTF-8 CSV file."

    required_columns = {
        "institute_code",
        "college_name",
        "city",
        "address",
        "website",
        "course_name",
        "admission_year",
        "cap_round",
        "admission_pool",
        "category",
        "seat_type",
        "exam",
        "score_basis",
        "cutoff_score",
        "source_url",
    }

    def add_arguments(self, parser):
        parser.add_argument("csv_file", help="Path to the verified cutoff CSV.")

    def handle(self, *args, **options):
        path = options["csv_file"]
        try:
            file_obj = open(path, encoding="utf-8-sig", newline="")
        except OSError as exc:
            raise CommandError("Unable to read CSV file '{}': {}".format(path, exc))

        imported = 0
        with file_obj:
            reader = csv.DictReader(file_obj)
            missing = self.required_columns - set(reader.fieldnames or [])
            if missing:
                raise CommandError(
                    "CSV is missing required column(s): {}".format(", ".join(sorted(missing)))
                )
            with transaction.atomic():
                for row_number, row in enumerate(reader, start=2):
                    try:
                        imported += self._import_row(row)
                    except (ValueError, InvalidOperation, KeyError, TypeError, ValidationError) as exc:
                        raise CommandError("Invalid CSV row {}: {}".format(row_number, exc))
        self.stdout.write(self.style.SUCCESS("Imported or updated {} cutoff row(s).".format(imported)))

    def _import_row(self, row):
        institute_code = self._text(row, "institute_code")
        if not institute_code:
            raise ValueError("institute_code must not be blank")
        category = self._text(row, "category").upper()
        if category not in dict(StudentProfile.CATEGORIES):
            raise ValueError("unknown normalized category '{}'".format(category))
        admission_pool = self._text(row, "admission_pool").upper()
        if admission_pool not in dict(Cutoff.ADMISSION_POOLS):
            raise ValueError("admission_pool must be MH or AI")
        exam = self._text(row, "exam")
        if exam not in dict(Cutoff.EXAMS):
            raise ValueError("exam must be MHT-CET or JEE Main")
        score_basis = self._text(row, "score_basis").lower()
        if score_basis not in dict(Cutoff.SCORE_BASES):
            raise ValueError("score_basis must be percentile or rank")
        admission_year = self._text(row, "admission_year")
        if not re.fullmatch(r"\d{4}-\d{2}", admission_year):
            raise ValueError("admission_year must use YYYY-YY format")
        source_url = self._text(row, "source_url")
        seat_type = self._text(row, "seat_type", required=False)
        URLValidator(schemes=["http", "https"])(source_url)

        college, _ = College.objects.update_or_create(
            institute_code=institute_code,
            defaults={
                "name": self._text(row, "college_name"),
                "city": self._text(row, "city"),
                "address": self._text(row, "address", required=False),
                "website": self._text(row, "website", required=False),
            },
        )
        cutoff_score = Decimal(self._text(row, "cutoff_score"))
        if not cutoff_score.is_finite() or cutoff_score < 0:
            raise ValueError("cutoff_score must be finite and nonnegative")
        if score_basis == "percentile" and cutoff_score > 100:
            raise ValueError("percentile cutoffs must not exceed 100")
        if score_basis == "rank" and cutoff_score < 1:
            raise ValueError("rank cutoffs must be at least 1")
        if cutoff_score != cutoff_score.quantize(Decimal("0.001")):
            raise ValueError("cutoff_score supports at most 3 decimal places")
        if cutoff_score >= Decimal("10000000"):
            raise ValueError("cutoff_score exceeds the supported range")
        cutoff_round = int(self._text(row, "cap_round"))
        if cutoff_round < 1 or cutoff_round > 32767:
            raise ValueError("cap_round must be between 1 and 32767")

        Cutoff.objects.update_or_create(
            college=college,
            course_name=self._text(row, "course_name"),
            admission_year=admission_year,
            cap_round=cutoff_round,
            admission_pool=admission_pool,
            category=category,
            seat_type=seat_type,
            exam=exam,
            score_basis=score_basis,
            defaults={
                "cutoff_score": cutoff_score,
                "source_url": source_url,
            },
        )
        return 1

    @staticmethod
    def _text(row, field, required=True):
        value = (row.get(field) or "").strip()
        if required and not value:
            raise ValueError("{} must not be blank".format(field))
        return value
