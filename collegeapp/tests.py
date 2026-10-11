import csv
import os
import tempfile
from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse

from .forms import RecommendationFilterForm, StudentProfileForm
from .management.commands.import_mahacet_cutoffs import (
    _layout_cells,
    _layout_percentiles,
    category_for_seat_type,
    parse_ai_pages,
)
from .models import College, Cutoff, StudentProfile
from .services import get_recommendations


class StudentFlowTests(TestCase):
    def test_signup_creates_account_and_logs_student_in(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "samstudent",
                "first_name": "Sam",
                "last_name": "Student",
                "email": "sam@example.com",
                "password1": "StrongPassword-3892",
                "password2": "StrongPassword-3892",
            },
        )

        self.assertRedirects(response, reverse("index"))
        user = User.objects.get(username="samstudent")
        self.assertTrue(user.check_password("StrongPassword-3892"))
        self.assertTrue(StudentProfile.objects.filter(user=user).exists())
        self.assertTrue("_auth_user_id" in self.client.session)

    def test_private_pages_require_login(self):
        response = self.client.get(reverse("results"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url.split("?")[0], reverse("login"))

    def test_profile_requires_one_exam_score_and_valid_percentile(self):
        no_score = StudentProfileForm(
            data={
                "full_name": "Sam Student",
                "category": "OPEN",
                "admission_pool": "MH",
                "hsc_percentage": "82",
                "mht_cet_score": "",
                "mht_cet_basis": "percentile",
                "jee_score": "",
                "jee_basis": "percentile",
            }
        )
        self.assertFalse(no_score.is_valid())
        self.assertIn("Enter at least one", str(no_score.non_field_errors()))

        invalid_percentile = StudentProfileForm(
            data={
                "full_name": "Sam Student",
                "category": "OPEN",
                "admission_pool": "MH",
                "hsc_percentage": "82",
                "mht_cet_score": "101",
                "mht_cet_basis": "percentile",
                "jee_score": "",
                "jee_basis": "percentile",
            }
        )
        self.assertFalse(invalid_percentile.is_valid())
        self.assertIn("mht_cet_score", invalid_percentile.errors)

        exam_score = StudentProfileForm(
            data={
                "full_name": "Sam Student",
                "category": "OPEN",
                "admission_pool": "AI",
                "hsc_percentage": "82",
                "mht_cet_score": "",
                "mht_cet_basis": "percentile",
                "jee_score": "84.8546239",
                "jee_basis": "score",
            }
        )
        self.assertTrue(exam_score.is_valid(), exam_score.errors)

    def test_student_can_save_profile(self):
        user = User.objects.create_user(username="profileuser", password="secret")
        StudentProfile.objects.create(
            user=user, full_name="Profile User", hsc_percentage=0
        )
        self.client.login(username="profileuser", password="secret")
        response = self.client.post(
            reverse("index"),
            {
                "full_name": "Profile User",
                "phone": "9876543210",
                "category": "OPEN",
                "admission_pool": "MH",
                "hsc_percentage": "84.50",
                "city": "Pune",
                "preferred_branch": "Computer Engineering",
                "mht_cet_score": "93.25",
                "mht_cet_basis": "percentile",
                "jee_score": "",
                "jee_basis": "percentile",
            },
        )

        self.assertRedirects(response, reverse("results"))
        profile = StudentProfile.objects.get(user=user)
        self.assertEqual(profile.city, "Pune")
        self.assertEqual(profile.mht_cet_score, Decimal("93.250"))

    def test_profile_offers_city_and_branch_suggestions(self):
        user = User.objects.create_user(username="suggestionsuser", password="secret")
        self.client.login(username="suggestionsuser", password="secret")

        response = self.client.get(reverse("index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'list="maharashtra-cities"')
        self.assertContains(response, '<option value="Pune">')
        self.assertContains(response, 'list="engineering-branches"')
        self.assertContains(response, '<option value="Computer Engineering">')

    def test_recommendations_compare_percentiles_and_filter_preferences(self):
        user = User.objects.create_user(username="samstudent", password="secret")
        profile = StudentProfile.objects.create(
            user=user,
            full_name="Sam Student",
            category="OBC",
            hsc_percentage=82,
            city="Pune",
            preferred_branch="Computer",
            mht_cet_score=94,
            mht_cet_basis="percentile",
        )
        pune_college = College.objects.create(
            institute_code="1001", name="Pune Engineering College", city="Pune"
        )
        mumbai_college = College.objects.create(
            institute_code="1002", name="Mumbai Engineering College", city="Mumbai"
        )
        Cutoff.objects.create(
            college=pune_college,
            course_name="Computer Engineering",
            admission_year="2026-27",
            cap_round=4,
            category="OBC",
            seat_type="GOBCS",
            exam="MHT-CET",
            score_basis="percentile",
            cutoff_score=90,
            source_url="https://example.com/official-cutoff.pdf",
        )
        Cutoff.objects.create(
            college=mumbai_college,
            course_name="Computer Engineering",
            admission_year="2026-27",
            cap_round=4,
            category="OBC",
            exam="MHT-CET",
            score_basis="percentile",
            cutoff_score=92,
            source_url="https://example.com/official-cutoff.pdf",
        )
        Cutoff.objects.create(
            college=pune_college,
            course_name="Mechanical Engineering",
            admission_year="2026-27",
            cap_round=4,
            category="OBC",
            exam="MHT-CET",
            score_basis="percentile",
            cutoff_score=95,
            source_url="https://example.com/official-cutoff.pdf",
        )
        Cutoff.objects.create(
            college=pune_college,
            course_name="Civil Engineering",
            admission_year="2026-27",
            cap_round=4,
            admission_pool="AI",
            category="OBC",
            exam="MHT-CET",
            score_basis="percentile",
            cutoff_score=90,
            source_url="https://example.com/official-cutoff.pdf",
        )

        results = get_recommendations(profile, admission_year="2026-27")
        self.assertEqual(len(results), 2)
        self.assertTrue(results[0]["city_match"])
        filtered = get_recommendations(profile, admission_year="2026-27", city="Mumbai")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["cutoff"].college, mumbai_college)
        score_filtered = get_recommendations(
            profile, admission_year="2026-27", min_cutoff=91, max_cutoff=93
        )
        self.assertEqual(len(score_filtered), 1)
        self.assertEqual(score_filtered[0]["cutoff"].college, mumbai_college)

    def test_rank_cutoff_is_reached_by_a_lower_rank_and_open_fallback(self):
        user = User.objects.create_user(username="rankstudent", password="secret")
        profile = StudentProfile.objects.create(
            user=user,
            full_name="Rank Student",
            category="OBC",
            hsc_percentage=80,
            mht_cet_score=120,
            mht_cet_basis="rank",
        )
        college = College.objects.create(institute_code="2001", name="State College", city="Pune")
        Cutoff.objects.create(
            college=college,
            course_name="Civil Engineering",
            admission_year="2026-27",
            cap_round=1,
            category="OBC",
            exam="MHT-CET",
            score_basis="rank",
            cutoff_score=130,
            source_url="https://example.com/obc-cutoff.pdf",
        )
        preferred_cutoff = Cutoff.objects.create(
            college=college,
            course_name="Civil Engineering",
            admission_year="2026-27",
            cap_round=3,
            category="OBC",
            exam="MHT-CET",
            score_basis="rank",
            cutoff_score=140,
            source_url="https://example.com/obc-cutoff.pdf",
        )
        Cutoff.objects.create(
            college=college,
            course_name="Civil Engineering",
            admission_year="2026-27",
            cap_round=4,
            category="OPEN",
            exam="MHT-CET",
            score_basis="rank",
            cutoff_score=150,
            source_url="https://example.com/official-cutoff.pdf",
        )

        results = get_recommendations(profile, admission_year="2026-27")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["cutoff"], preferred_cutoff)
        self.assertEqual(results[0]["margin"], 20)

        profile.mht_cet_score = 145
        profile.save()
        fallback_results = get_recommendations(profile, admission_year="2026-27")
        self.assertEqual(len(fallback_results), 1)
        self.assertEqual(fallback_results[0]["cutoff"].category, "OPEN")
        self.assertEqual(fallback_results[0]["margin"], 5)

    def test_results_page_renders_source_cutoff_for_signed_in_student(self):
        user = User.objects.create_user(username="resultsuser", password="secret")
        StudentProfile.objects.create(
            user=user,
            full_name="Results User",
            category="OPEN",
            hsc_percentage=75,
            mht_cet_score=93,
        )
        college = College.objects.create(
            institute_code="4001", name="Results College", city="Pune"
        )
        Cutoff.objects.create(
            college=college,
            course_name="Computer Engineering",
            admission_year="2026-27",
            cap_round=4,
            category="OPEN",
            exam="MHT-CET",
            score_basis="percentile",
            cutoff_score=90,
            source_url="https://example.com/official-cutoff.pdf",
        )
        self.client.login(username="resultsuser", password="secret")

        response = self.client.get(reverse("results"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Results College")
        self.assertContains(response, "official-cutoff.pdf")

    def test_filter_form_reports_invalid_score_ranges(self):
        form = RecommendationFilterForm(
            {"min_cutoff": "92", "max_cutoff": "80"}, years=["2026-27"]
        )
        self.assertFalse(form.is_valid())
        self.assertIn("Minimum cutoff", str(form.non_field_errors()))

    def test_cutoff_csv_import_is_atomic_and_updates_college_data(self):
        headers = [
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
        ]
        valid_row = [
            "3001",
            "Verified College",
            "Pune",
            "",
            "",
            "Computer Engineering",
            "2026-27",
            "4",
            "MH",
            "OPEN",
            "GOPENH",
            "MHT-CET",
            "percentile",
            "91.250",
            "https://example.com/cap-cutoff.pdf",
        ]
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", suffix=".csv", delete=False
        ) as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(headers)
            writer.writerow(valid_row)
            csv_path = csv_file.name
        self.addCleanup(os.unlink, csv_path)

        call_command("import_cutoffs", csv_path, stdout=StringIO())

        self.assertEqual(College.objects.get(institute_code="3001").name, "Verified College")
        cutoff = Cutoff.objects.get(college__institute_code="3001")
        self.assertEqual(cutoff.cutoff_score, Decimal("91.250"))
        self.assertEqual(cutoff.seat_type, "GOPENH")

        valid_row[1] = "Updated Verified College"
        valid_row[13] = "92.000"
        with open(csv_path, "w", encoding="utf-8", newline="") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(headers)
            writer.writerow(valid_row)
        call_command("import_cutoffs", csv_path, stdout=StringIO())
        self.assertEqual(College.objects.count(), 1)
        self.assertEqual(College.objects.get(institute_code="3001").name, "Updated Verified College")

        new_valid_row = valid_row.copy()
        new_valid_row[0] = "3002"
        invalid_row = new_valid_row.copy()
        invalid_row[9] = "NOT_A_CATEGORY"
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", suffix=".csv", delete=False
        ) as invalid_file:
            writer = csv.writer(invalid_file)
            writer.writerow(headers)
            writer.writerow(new_valid_row)
            writer.writerow(invalid_row)
            invalid_path = invalid_file.name
        self.addCleanup(os.unlink, invalid_path)
        with self.assertRaises(CommandError):
            call_command("import_cutoffs", invalid_path, stdout=StringIO())
        self.assertEqual(College.objects.count(), 1)


class MahacetCutoffParserTests(TestCase):
    def test_ai_parser_extracts_cutoff_rank_and_wrapped_course_name(self):
        page_items = [
            [
                (55.4, -140.1, "1"),
                (
                    231.8,
                    -138.4,
                    "01101 - Shri Sant Gajanan Maharaj College of Engineering,Shegaon"
                    "011012461018298 (84.8546239)",
                ),
                (784.2, -139.9, "AI"),
                (716.3, -142.2, "AI to AI"),
                (654.9, -142.8, "JEEElectronics and"),
                (520.2, -150.6, "Telecommunication Engg"),
            ]
        ]

        records = parse_ai_pages(page_items, "2026-27", 4)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["college_code"], "01101")
        self.assertEqual(
            records[0]["course_name"], "Electronics and Telecommunication Engg"
        )
        self.assertEqual(records[0]["exam"], "JEE Main")
        self.assertEqual(records[0]["score_basis"], "score")
        self.assertEqual(records[0]["cutoff_score"], 84.8546239)
        self.assertIn("All India merit 18298", records[0]["source_notes"])
        self.assertIn("JEE Main score 84.8546239", records[0]["source_notes"])

    def test_ai_parser_uses_mht_cet_percentile_instead_of_merit_rank(self):
        page_items = [
            [
                (55.4, -140.1, "1"),
                (
                    231.8,
                    -138.4,
                    "01101 - Example Engineering College"
                    "011012461018298 (91.2500000)",
                ),
                (784.2, -139.9, "AI"),
                (654.9, -142.8, "MHT-CETInformation Technology"),
            ]
        ]

        record = parse_ai_pages(page_items, "2026-27", 4)[0]

        self.assertEqual(record["exam"], "MHT-CET")
        self.assertEqual(record["score_basis"], "percentile")
        self.assertEqual(record["cutoff_score"], 91.25)

    def test_mh_layout_parser_maps_aligned_cells_and_skips_special_seats(self):
        headers = [
            ("GOPENS", 10, "OPEN"),
            ("GSEBCS", 30, "SEBC"),
            ("TFWS", 50, None),
        ]

        ranks = _layout_cells(
            "I       32404                 44969                 37480", 1, headers
        )
        scores = _layout_percentiles(
            "        (92.3369677)         (89.2656035)         (91.0694792)", headers
        )

        self.assertEqual(category_for_seat_type("GOPENS"), "OPEN")
        self.assertEqual(category_for_seat_type("GSEBCS"), "SEBC")
        self.assertIsNone(category_for_seat_type("TFWS"))
        self.assertEqual(ranks["GOPENS"], "32404")
        self.assertEqual(scores["GOPENS"], 92.3369677)

    def test_recommendations_match_official_jee_score_cutoffs(self):
        user = User.objects.create_user(
            username="jeescorestudent", password="Testpass-1234!"
        )
        profile = StudentProfile.objects.create(
            user=user,
            full_name="JEE Score Student",
            category="OPEN",
            admission_pool="AI",
            hsc_percentage=80,
            jee_score=Decimal("84.9000000"),
            jee_basis="score",
        )
        college = College.objects.create(
            institute_code="90001", name="JEE Score College", city="Pune"
        )
        cutoff = Cutoff.objects.create(
            college=college,
            course_name="Computer Engineering",
            admission_year="2026-27",
            cap_round=4,
            admission_pool="AI",
            category="OPEN",
            seat_type="AI",
            exam="JEE Main",
            score_basis="score",
            cutoff_score=Decimal("84.8546239"),
            source_url="https://example.com/ai-cutoff.pdf",
        )

        results = get_recommendations(profile, admission_year="2026-27")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["cutoff"], cutoff)
