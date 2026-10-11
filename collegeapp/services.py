from .models import Cutoff


def _profile_scores(profile):
    scores = []
    if profile.mht_cet_score is not None:
        scores.append(("MHT-CET", profile.mht_cet_basis, profile.mht_cet_score))
    if profile.jee_score is not None:
        scores.append(("JEE Main", profile.jee_basis, profile.jee_score))
    return scores


def _meets_cutoff(score, basis, cutoff_score):
    if basis == "rank":
        return score <= cutoff_score
    return score >= cutoff_score


def get_recommendations(
    profile,
    admission_year="",
    city="",
    branch="",
    min_cutoff=None,
    max_cutoff=None,
):
    score_options = _profile_scores(profile)
    cutoffs = Cutoff.objects.select_related("college").filter(
        category__iexact=profile.category,
        admission_pool=profile.admission_pool,
    )
    if profile.category != "OPEN":
        cutoffs = cutoffs | Cutoff.objects.select_related("college").filter(
            category__iexact="OPEN",
            admission_pool=profile.admission_pool,
        )
    if admission_year:
        cutoffs = cutoffs.filter(admission_year=admission_year)

    if city:
        cutoffs = cutoffs.filter(college__city__icontains=city)
    if branch:
        cutoffs = cutoffs.filter(course_name__icontains=branch)
    if min_cutoff is not None:
        cutoffs = cutoffs.filter(cutoff_score__gte=min_cutoff)
    if max_cutoff is not None:
        cutoffs = cutoffs.filter(cutoff_score__lte=max_cutoff)

    matches = {}
    for cutoff in cutoffs:
        if cutoff.college.city and profile.city:
            city_match = cutoff.college.city.casefold() == profile.city.casefold()
        else:
            city_match = False
        branch_match = (
            bool(profile.preferred_branch)
            and profile.preferred_branch.casefold() in cutoff.course_name.casefold()
        )
        for exam, score_basis, score in score_options:
            if cutoff.exam != exam or cutoff.score_basis != score_basis:
                continue
            if not _meets_cutoff(score, score_basis, cutoff.cutoff_score):
                continue
            key = (
                cutoff.college_id,
                cutoff.course_name,
                cutoff.admission_year,
                exam,
                score_basis,
                cutoff.seat_type,
            )
            result = {
                "cutoff": cutoff,
                "exam": exam,
                "score": score,
                "margin": (
                    cutoff.cutoff_score - score
                    if score_basis == "rank"
                    else score - cutoff.cutoff_score
                ),
                "city_match": city_match,
                "branch_match": branch_match,
                "exact_category": cutoff.category.casefold() == profile.category.casefold(),
            }
            current = matches.get(key)
            if current is None or (
                result["exact_category"],
                cutoff.cap_round,
            ) > (
                current["exact_category"],
                current["cutoff"].cap_round,
            ):
                matches[key] = result

    ordered_matches = list(matches.values())
    ordered_matches.sort(
        key=lambda item: (
            not item["city_match"],
            not item["branch_match"],
            not item["exact_category"],
            -item["cutoff"].cap_round,
            -item["margin"],
            item["cutoff"].college.name.casefold(),
            item["cutoff"].course_name.casefold(),
            item["cutoff"].seat_type.casefold(),
            item["exam"],
        )
    )
    return ordered_matches
