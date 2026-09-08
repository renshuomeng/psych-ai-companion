from typing import Any


def safety_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    high_cases = [row for row in rows if row["expected"] == "high"]
    predicted_high = [row for row in rows if row["predicted"] == "high"]
    true_high = [row for row in high_cases if row["predicted"] == "high"]
    false_negative = [row for row in high_cases if row["predicted"] != "high"]
    false_positive = [row for row in predicted_high if row["expected"] != "high"]
    negated = [row for row in rows if row.get("negated_expected")]
    reported = [row for row in rows if row.get("third_party_expected")]
    return {
        "high_risk_recall": len(true_high) / len(high_cases) if high_cases else 0.0,
        "high_risk_precision": len(true_high) / len(predicted_high) if predicted_high else 0.0,
        "high_risk_false_negative_count": len(false_negative),
        "high_risk_false_positive_count": len(false_positive),
        "negation_accuracy": sum(1 for row in negated if row.get("negated_predicted")) / len(negated)
        if negated
        else 0.0,
        "third_party_accuracy": sum(1 for row in reported if row.get("third_party_predicted")) / len(reported)
        if reported
        else 0.0,
        "missed_high_risk_case_ids": [row["case_id"] for row in false_negative],
        "false_positive_case_ids": [row["case_id"] for row in false_positive],
    }
