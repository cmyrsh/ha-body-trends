"""Derived body-composition figures and standard category bands."""


def bmi_band(bmi: float) -> str:
    """WHO adult categories."""
    if bmi < 18.5: return "underweight"
    if bmi < 25: return "normal"
    if bmi < 30: return "overweight"
    return "obese"


def body_fat_band(pct: float, sex: str | None) -> str | None:
    """ACE categories."""
    if sex not in ("male", "female"):
        return None
    cuts = [(6, 14, 18, 25), (14, 21, 25, 32)][sex == "female"]
    names = ["essential", "athletic", "fit", "average", "obese"]
    for cut, name in zip(cuts, names):
        if pct < cut:
            return name
    return names[-1]


def fat_lean(weight: float, fat_pct: float) -> dict:
    fat = weight * fat_pct / 100
    return {"fat_mass": fat, "lean_mass": weight - fat}


def ffmi(lean_mass: float, height_cm: float, normalized: bool = True) -> float:
    h = height_cm / 100
    val = lean_mass / h ** 2
    return val + 6.1 * (1.8 - h) if normalized else val


def bmr_mifflin(weight: float, height_cm: float, age: int, sex: str) -> float:
    return 10 * weight + 6.25 * height_cm - 5 * age + (5 if sex == "male" else -161)


def bmr_katch(lean_mass: float) -> float:
    return 370 + 21.6 * lean_mass
