import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from pypdf import PdfReader

from collegeapp.models import College, Cutoff


MH_SOURCE = (
    "https://cappublicdocs2026.blob.core.windows.net/documents/"
    "2026ENGG_CAP4_MH_CutOff.pdf"
)
AI_SOURCE = (
    "https://cappublicdocs2026.blob.core.windows.net/documents/"
    "2026ENGG_CAP4_AI_CutOff.pdf"
)
ROMAN_STAGES = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
    "IX": 9,
    "X": 10,
}
CITY_NAMES = (
    "Chhatrapati Sambhajinagar",
    "Navi Mumbai",
    "Ahilyanagar",
    "Mumbai",
    "Pune",
    "Nagpur",
    "Nashik",
    "Thane",
    "Kolhapur",
    "Amravati",
    "Solapur",
    "Jalgaon",
    "Akola",
    "Sangli",
    "Satara",
    "Latur",
    "Nanded",
    "Parbhani",
    "Jalna",
    "Beed",
    "Dhule",
    "Wardha",
    "Yavatmal",
    "Chandrapur",
    "Gondia",
    "Bhandara",
    "Ratnagiri",
    "Sindhudurg",
    "Washim",
    "Buldhana",
    "Osmanabad",
    "Palghar",
)


def category_for_seat_type(seat_type):
    code = seat_type.upper()
    if any(marker in code for marker in ("ORPHAN", "TFWS", "PWD", "DEF")):
        return None
    if code.startswith("L"):
        return None
    if code == "AI" or "OPEN" in code:
        return "OPEN"
    if "EWS" in code:
        return "EWS"
    if "SEBC" in code:
        return "SEBC"
    if "OBC" in code:
        return "OBC"
    if re.search(r"NT1", code):
        return "NT-B"
    if re.search(r"NT2", code):
        return "NT-C"
    if re.search(r"NT3", code):
        return "NT-D"
    if "VJ" in code:
        return "VJ"
    if "SCS" in code or "SC" in code:
        return "SC"
    if "STS" in code or "ST" in code:
        return "ST"
    return None


def _city_from_college_name(name):
    normalized_name = name.casefold()
    for city in CITY_NAMES:
        if re.search(r"\b{}\b".format(re.escape(city.casefold())), normalized_name):
            return city
    if re.search(r"\b(?:aurangabad|sambhajinagar)\b", normalized_name):
        return "Chhatrapati Sambhajinagar"
    if re.search(r"\bahmednagar\b", normalized_name):
        return "Ahilyanagar"
    if re.search(r"\bosmanabad\b", normalized_name):
        return "Dharashiv"
    return ""


def parse_ai_pages(page_items, year, cap_round):
    records = []
    for items in page_items:
        serials = [
            (y, text)
            for x, y, text in items
            if x < 70 and re.fullmatch(r"\d{1,4}", text.strip())
        ]
        for row_y, _ in serials:
            nearby = [
                (x, y, text)
                for x, y, text in items
                if row_y - 4 <= y <= row_y + 4
            ]
            source_cells = [
                (x, y, text)
                for x, y, text in nearby
                if x >= 70 and x < 650
            ]
            choice_match = None
            rank_score_match = None
            for _, _, text in source_cells:
                combined_row = re.search(
                    r"(?<!\d)(\d{10})(\d+)\s*\(\s*([\d.]+)\s*\)", text
                )
                if combined_row:
                    choice_match = choice_match or combined_row
                    rank_score_match = rank_score_match or combined_row
            exam_cell = next(
                (
                    (x, y, text)
                    for x, y, text in nearby
                    if 600 <= x < 710
                    and re.match(r"^(?:JEE|MHT-CET)", text.strip())
                ),
                None,
            )
            seat_cell = next(
                (text for x, _, text in nearby if x >= 750 and re.fullmatch(r"[A-Z0-9]+", text)),
                None,
            )
            if not choice_match or not rank_score_match or not exam_cell or not seat_cell:
                continue

            choice_code = choice_match.group(1)
            college_code = choice_code[:5]
            college_segments = []
            for x, y, text in items:
                if not 180 <= x < 600 or not row_y - 16 <= y <= row_y + 4:
                    continue
                if re.match(r"^\d{5}\s*-\s*", text) or (
                    college_segments and not re.search(r"\d{5}\s*-", text)
                ):
                    college_segments.append((y, text))
            college_segments.sort(key=lambda item: item[0], reverse=True)
            college_name = " ".join(text for _, text in college_segments)
            college_name = re.sub(r"^\d{5}\s*-\s*", "", college_name)
            college_name = re.sub(
                r"\d{10}\d+\s*\([\d.]+\).*$", "", college_name
            ).strip()

            exam_and_course = re.match(r"^(JEE|MHT-CET)\s*(.*)$", exam_cell[2].strip())
            if not exam_and_course:
                continue
            exam = "JEE Main" if exam_and_course.group(1) == "JEE" else "MHT-CET"
            course_parts = [exam_and_course.group(2).strip()]
            continuations = [
                (y, text.strip())
                for x, y, text in items
                if 500 <= x < 650
                and row_y - 20 <= y < exam_cell[1]
                and text.strip()
            ]
            course_parts.extend(text for _, text in sorted(continuations, reverse=True))
            parsed_course = " ".join(part for part in course_parts if part).strip()
            seat_type = seat_cell.strip()
            category = category_for_seat_type(seat_type)
            if not category or not parsed_course:
                continue
            try:
                merit_rank = int(rank_score_match.group(2))
                exam_value = float(rank_score_match.group(3))
            except ValueError:
                continue
            if merit_rank < 1:
                continue
            if exam == "JEE Main":
                score_basis = "score"
                cutoff_score = round(exam_value, 7)
                score_note = "JEE Main score {}; All India merit {}".format(
                    exam_value, merit_rank
                )
            else:
                if not 0 <= exam_value <= 100:
                    continue
                score_basis = "percentile"
                cutoff_score = round(exam_value, 7)
                score_note = "MHT-CET percentile {}".format(exam_value)

            notes = "CAP Round IV; {}; {}".format(
                score_note,
                next((text for x, _, text in nearby if 700 <= x < 750), ""),
            )
            records.append(
                {
                    "college_code": college_code,
                    "college_name": college_name or "Institute {}".format(college_code),
                    "course_name": parsed_course[:200],
                    "admission_year": year,
                    "cap_round": cap_round,
                    "admission_pool": "AI",
                    "category": category,
                    "seat_type": seat_type,
                    "exam": exam,
                    "score_basis": score_basis,
                    "cutoff_score": cutoff_score,
                    "source_url": AI_SOURCE,
                    "source_notes": notes[:255],
                }
            )
    return records


class Command(BaseCommand):
    help = "Import official Maharashtra engineering CAP cutoff PDFs."

    def add_arguments(self, parser):
        parser.add_argument("--mh-pdf", help="Downloaded official Maharashtra CAP cutoff PDF.")
        parser.add_argument("--ai-pdf", help="Downloaded official All India CAP cutoff PDF.")

    def handle(self, *args, **options):
        year = "2026-27"
        cap_round = 4
        if not options["mh_pdf"] and not options["ai_pdf"]:
            raise CommandError("Provide --mh-pdf, --ai-pdf, or both.")

        cutoff_rows = []
        if options["mh_pdf"]:
            cutoff_rows.extend(self._read_mh_pdf(options["mh_pdf"], year, cap_round))
        if options["ai_pdf"]:
            cutoff_rows.extend(self._read_ai_pdf(options["ai_pdf"], year, cap_round))
        if not cutoff_rows:
            raise CommandError(
                "No comparable percentile records were found in the PDFs; no database rows were changed."
            )

        unique_rows = {}
        colleges = {}
        for row in cutoff_rows:
            code = row.pop("college_code")
            colleges[code] = row["college_name"]
            key = (
                code,
                row["course_name"],
                row["admission_year"],
                row["cap_round"],
                row["admission_pool"],
                row["category"],
                row["seat_type"],
                row["exam"],
                row["score_basis"],
            )
            unique_rows[key] = row

        with transaction.atomic():
            College.objects.bulk_create(
                [
                    College(
                        institute_code=code,
                        name=name,
                        city=_city_from_college_name(name),
                    )
                    for code, name in colleges.items()
                ],
                update_conflicts=True,
                unique_fields=["institute_code"],
                update_fields=["name", "city"],
                batch_size=500,
            )
            college_ids = dict(
                College.objects.filter(institute_code__in=colleges).values_list(
                    "institute_code", "id"
                )
            )
            objects = []
            for key, row in unique_rows.items():
                code = key[0]
                objects.append(
                    Cutoff(
                        college_id=college_ids[code],
                        course_name=row["course_name"],
                        admission_year=row["admission_year"],
                        cap_round=row["cap_round"],
                        admission_pool=row["admission_pool"],
                        category=row["category"],
                        seat_type=row["seat_type"],
                        exam=row["exam"],
                        score_basis=row["score_basis"],
                        cutoff_score=row["cutoff_score"],
                        source_url=row["source_url"],
                        source_notes=row["source_notes"],
                    )
                )
            Cutoff.objects.bulk_create(
                objects,
                update_conflicts=True,
                unique_fields=[
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
                update_fields=["cutoff_score", "source_url", "source_notes"],
                batch_size=500,
            )
        self.stdout.write(
            self.style.SUCCESS(
                "Imported or updated {} official cutoff record(s) for {} college(s).".format(
                    len(unique_rows), len(colleges)
                )
            )
        )

    def _read_mh_pdf(self, path, year, cap_round):
        reader = _open_pdf(path)
        rows = []
        current_college = ""
        current_name = ""
        current_course = ""
        header = []
        latest_by_key = {}

        for page in reader.pages:
            text = page.extract_text(extraction_mode="layout")
            if not text:
                continue
            lines = text.splitlines()
            index = 0
            while index < len(lines):
                line = lines[index]
                college_match = re.match(r"^\s*(\d{5})\s*-\s*(.+?)\s*$", line)
                if college_match:
                    current_college, current_name = college_match.groups()
                    current_course = ""
                    header = []
                    index += 1
                    continue
                course_match = re.match(r"^\s*\d{10}\s*-\s*(.*?)\s*$", line)
                if course_match:
                    current_course = course_match.group(1).strip()
                    header = []
                    index += 1
                    continue

                if "Stage" in line:
                    header = [
                        (token, line.find(token), category_for_seat_type(token))
                        for token in re.findall(r"\b[A-Z][A-Z0-9]{1,14}\b", line)
                        if token != "Stage"
                    ]
                    index += 1
                    continue

                stage_match = re.match(
                    r"^\s*(I|II|III|IV|V|VI|VII|VIII|IX|X)\s+", line
                )
                special_stage_match = re.match(
                    r"^\s*(I|II|III|IV|V|VI|VII|VIII|IX|X)-Non\b", line
                )
                if (
                    not current_college
                    or not current_course
                    or not header
                    or not (stage_match or special_stage_match)
                ):
                    index += 1
                    continue

                stage_match = stage_match or special_stage_match
                stage = stage_match.group(1)
                rank_cells = _layout_cells(line, stage_match.end(), header)
                score_cells = {}
                next_index = index + 1
                score_line_found = False
                while next_index < len(lines):
                    score_line = lines[next_index]
                    if re.match(
                        r"^\s*(I|II|III|IV|V|VI|VII|VIII|IX|X)(?:\s+|-Non\b)",
                        score_line,
                    ) or "Stage" in score_line or re.match(
                        r"^\s*\d{10}\s*-", score_line
                    ):
                        break
                    percentile_cells = _layout_percentiles(score_line, header)
                    if percentile_cells:
                        score_cells = percentile_cells
                        score_line_found = True
                        break
                    next_index += 1

                for seat_type, percentile in score_cells.items():
                    category = next(
                        (known_category for token, _, known_category in header if token == seat_type),
                        None,
                    )
                    rank = rank_cells.get(seat_type)
                    if (
                        not category
                        or not rank
                        or not 0 <= percentile <= 100
                    ):
                        continue
                    key = (
                        current_college,
                        current_course,
                        "MH",
                        category,
                        seat_type,
                        "MHT-CET",
                        "percentile",
                    )
                    candidate = {
                        "college_code": current_college,
                        "college_name": current_name,
                        "course_name": current_course[:200],
                        "admission_year": year,
                        "cap_round": cap_round,
                        "admission_pool": "MH",
                        "category": category,
                        "seat_type": seat_type,
                        "exam": "MHT-CET",
                        "score_basis": "percentile",
                        "cutoff_score": round(percentile, 7),
                        "source_url": MH_SOURCE,
                        "source_notes": "CAP Round {}; Stage {}; State merit number {}".format(
                            cap_round, stage, rank
                        ),
                    }
                    existing = latest_by_key.get(key)
                    if existing is None or ROMAN_STAGES[stage] > existing[0]:
                        latest_by_key[key] = (ROMAN_STAGES[stage], candidate)
                index = next_index + 1 if score_line_found else index + 1

        rows.extend(candidate for _, candidate in latest_by_key.values())
        if not rows:
            raise CommandError("No comparable records could be parsed from MH PDF '{}'.".format(path))
        return rows

    def _read_ai_pdf(self, path, year, cap_round):
        reader = _open_pdf(path)
        page_items = []
        for page in reader.pages:
            items = []

            def capture(text, current_matrix, text_matrix, font, font_size):
                if text.strip():
                    items.append(
                        (
                            round(text_matrix[4], 1),
                            round(text_matrix[5], 1),
                            text.strip(),
                        )
                    )

            page.extract_text(visitor_text=capture)
            page_items.append(items)
        rows = parse_ai_pages(page_items, year, cap_round)
        if not rows:
            raise CommandError("No comparable records could be parsed from AI PDF '{}'.".format(path))
        return rows


def _open_pdf(path):
    try:
        pdf_path = Path(path)
        if not pdf_path.is_file():
            raise CommandError("PDF file does not exist: {}".format(path))
        return PdfReader(str(pdf_path))
    except CommandError:
        raise
    except Exception as exc:
        raise CommandError("Unable to read PDF '{}': {}".format(path, exc))


def _layout_cells(line, data_start, columns):
    cells = {}
    for match in re.finditer(r"\d+", line[data_start:]):
        position = data_start + match.start()
        column = min(columns, key=lambda item: abs(item[1] - position))
        cells[column[0]] = match.group()
    return cells


def _layout_percentiles(line, columns):
    cells = {}
    for match in re.finditer(r"\(([\d.]+)\)", line):
        position = match.start()
        column = min(columns, key=lambda item: abs(item[1] - position))
        cells[column[0]] = float(match.group(1))
    return cells
