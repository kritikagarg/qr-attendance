from rapidfuzz import process, fuzz

SCORE_THRESHOLD = 70  # 0-100, higher = stricter


def find_match(input_name, students):
    """
    Fuzzy-matches input_name against the student roster.
    Returns one of:
      {"student": dict, "score": float}          — confident match
      {"suggestions": [name, name, ...]}         — low confidence, show alternatives
      {"noMatch": True}                          — nothing close at all
    """
    if not students:
        return {"noMatch": True}

    normalized = input_name.strip().upper()
    names = [s['name'] for s in students]

    best = process.extractOne(normalized, names, scorer=fuzz.WRatio, score_cutoff=SCORE_THRESHOLD)

    if best:
        matched_name, score, idx = best
        return {"student": students[idx], "score": score}

    # No confident match — return up to 3 closest names as suggestions
    top = process.extract(normalized, names, scorer=fuzz.WRatio, limit=3)
    suggestions = [r[0] for r in top if r[1] > 30]

    return {"suggestions": suggestions} if suggestions else {"noMatch": True}
