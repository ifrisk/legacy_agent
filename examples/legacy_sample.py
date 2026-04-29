def normalize_score(score: int) -> int:
    if score < 0:
        return 0
    if score > 100:
        return 100
    return score


def classify_age(age: int) -> str:
    if age < 0:
        raise ValueError("age must be non-negative")
    if age < 18:
        return "minor"
    if age >= 65:
        return "senior"
    return "adult"
