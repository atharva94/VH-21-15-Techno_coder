# VH-21-15-Techno_coder

## Maharashtra College Finder

A Django web application for students exploring Maharashtra engineering admissions. Students create an account, save academic scores and preferences, and compare those details with CAP cutoff records maintained by the project administrators.

The application supports both MHT-CET and JEE Main score records. It compares percentiles (higher is better) and ranks (lower is better), then filters recommendations by admission year, city, course, and cutoff range. Each displayed result links back to its cited source. Results are indicative only and do not guarantee admission.

## Features

- Django account creation, login, logout, and authenticated student profiles.
- Profile storage for category, HSC percentage, city, preferred branch, MHT-CET score, and JEE Main score.
- Database-backed college and course cutoff records with CAP year/round, student category, official seat-type code, exam, score basis, and source URL.
- Separate Maharashtra state-CAP and All-India admission pools so unlike cutoffs are not compared.
- Recommendations using category cutoffs with Open-category fallback for reserved-category students.
- Filters for CAP year, city, branch, and cutoff range.
- College detail pages showing available courses and cited cutoff records.
- Django admin screens for staff to manage colleges, cutoff data, and student profiles.
- CSV import command for loading verified data in bulk.

## Official admissions data

This project targets Maharashtra first-year engineering admissions because its original form asks for MHT-CET/JEE scores and Maharashtra cities.

The State CET Cell's live **A.Y. 2026–27** engineering CAP portal links to round-wise documents, including:

- [CAP Round IV Maharashtra cutoff (PDF)](https://cappublicdocs2026.blob.core.windows.net/documents/2026ENGG_CAP4_MH_CutOff.pdf)
- [CAP Round IV All India cutoff (PDF)](https://cappublicdocs2026.blob.core.windows.net/documents/2026ENGG_CAP4_AI_CutOff.pdf)
- [Official 2026–27 Engineering CAP portal](https://fe2026.mahacet.org/StaticPages/HomePage)
- [Maharashtra State CET Cell CAP 2026–27 hub](https://cetcell.mahacet.org/cap-_2026-27/)

The CAP portal also provides institute-wise allotment information. The cutoff PDFs are the source for institute/course and round-specific admission thresholds; they should be treated as year- and round-specific historical guidance, not as promises about a future allotment. Check the portal for later rounds and revised files.

No cutoff figures are hard-coded or fabricated in this repository. The official documents are published as PDFs, so staff must verify/normalize the records and then import them. Keep the exact official seat-type in `seat_type`, map its applicable student group to `category`, and select the correct exam and score basis. Where the official source does not provide a comparable percentile or rank for the student's chosen score type, do not create a recommendation record from it.

## Data model

- **Student profile:** belongs to one Django user and is private to that logged-in user; records the student's admission pool.
- **College:** institute code, name, city, address, and website.
- **Cutoff:** college, course, admission year, CAP round, Maharashtra/All-India pool, normalized category, original seat-type (when known), exam, score basis, threshold, and official source URL. A uniqueness constraint prevents duplicate cutoff entries for the same college/course/year/round/pool/category/seat-type/exam/score basis.

Reserved-category students are compared with their category's cutoff and may also be compared with the Open cutoff. HSC percentage is stored but is not currently applied as an eligibility gate. The profile also does not collect gender or home-university eligibility; seat-type-specific allotment rules and the qualifying-exam requirements should therefore be reviewed in the official CAP brochure before interpreting a match.

## Setup

Requirements: Python 3.8+ and pip.

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open <http://127.0.0.1:8000/> to create a student account. The admin dashboard is at <http://127.0.0.1:8000/admin/>; use the superuser created above to add colleges and verified cutoff records.

The settings use a local-only development key while `DJANGO_DEBUG` is enabled. Before deployment, set a secret `DJANGO_SECRET_KEY`, set `DJANGO_DEBUG=False`, and set `DJANGO_ALLOWED_HOSTS` to a comma-separated list of the deployment's hostnames. The app refuses to start with debug disabled if no secret key is configured.

## Importing verified cutoff CSV data

Create a UTF-8 CSV with these columns:

```text
institute_code,college_name,city,address,website,course_name,admission_year,cap_round,admission_pool,category,seat_type,exam,score_basis,cutoff_score,source_url
```

Allowed `admission_pool` values: `MH` (Maharashtra state CAP) or `AI` (All India). Allowed `category` values: `OPEN`, `EWS`, `SC`, `ST`, `VJ`, `NT-B`, `NT-C`, `NT-D`, `OBC`, and `SEBC`. `seat_type` retains the exact label in the official source (for example a home-university or gender-specific seat code). `exam` must be `MHT-CET` or `JEE Main`; `score_basis` must be `percentile` or `rank`.

Import using:

```powershell
python manage.py import_cutoffs path\to\verified_cutoffs.csv
```

The import updates existing records by institute code and cutoff identity, so a corrected source file can be re-imported. The import is atomic: if a row is invalid, the command reports its CSV row number and rolls back the import. Only use cutoff values whose meaning is verified against the linked official document.

## Tests

Run the application tests with:

```powershell
python manage.py test collegeapp
```

## Project structure

```text
collegeapp/
├── management/commands/import_cutoffs.py
├── migrations/
├── templates/
├── admin.py
├── forms.py
├── models.py
├── services.py
├── tests.py
├── urls.py
└── views.py
collegepro/       Django project settings and root URL configuration
manage.py         Django management entry point
requirements.txt  Python dependencies
```

## Project team

Techno Coders
