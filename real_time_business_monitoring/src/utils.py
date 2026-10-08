"""Small helper functions used in several places."""
import pandas as pd


def format_inr(amount) -> str:
    """185000 -> ₹1,85,000 (Indian digit grouping)."""
    try:
        value = float(amount)
    except (TypeError, ValueError):
        return "₹0"
    sign = "-" if value < 0 else ""
    digits = f"{abs(value):.0f}"
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join(groups + [tail])
    return f"{sign}₹{digits}"


def df_to_records(df: pd.DataFrame) -> list:
    """DataFrame -> list of dicts that is safe to send as JSON (NaN/NaT become None)."""
    if df.empty:
        return []
    cleaned = df.astype(object).where(df.notna(), None)
    return cleaned.to_dict(orient="records")