import re


ORDER_PATTERNS = {
    "order_number": [
        r"(?:受注番号|注文番号|ORDER\s*NO\.?)\s*[:\uFF1A]?\s*(P-\d{4,8})",
        r"\b(P-\d{4,8})\b",
    ],
    "machine_number": [
        r"(?:機械番号|機番|MACHINE\s*NO\.?)\s*[:\uFF1A]?\s*([A-Z0-9\-]{2,20})",
    ],
    "model": [
        r"(?:型式|型番|MODEL)\s*[:\uFF1A]?\s*([A-Z0-9\-/]{2,30})",
    ],
    "customer_name": [
        r"(?:客先名|納入先名|納入先|CUSTOMER)\s*[:\uFF1A]?\s*([^\n]{2,40})",
    ],
    "requested_lead_days": [
        r"(?:希望所要日数|所要日数)\s*[:\uFF1A]?\s*([0-9]{1,3})\s*(?:日|DAY|DAYS)?",
    ],
}


def parse_order_sheet(text: str) -> dict:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    result = {
        "order_number": None,
        "machine_number": None,
        "model": None,
        "customer_name": None,
        "requested_lead_days": None,
    }

    for key, patterns in ORDER_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, normalized, re.IGNORECASE)
            if match:
                result[key] = match.group(1).strip()
                break

    return result
