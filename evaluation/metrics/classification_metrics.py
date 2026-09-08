from collections import Counter, defaultdict
from typing import Any


def classification_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    labels = sorted({row["expected"] for row in rows} | {row["predicted"] for row in rows})
    total = len(rows)
    correct = sum(1 for row in rows if row["expected"] == row["predicted"])
    per_label: dict[str, dict[str, float]] = {}
    for label in labels:
        tp = sum(1 for row in rows if row["expected"] == label and row["predicted"] == label)
        fp = sum(1 for row in rows if row["expected"] != label and row["predicted"] == label)
        fn = sum(1 for row in rows if row["expected"] == label and row["predicted"] != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_label[label] = {"precision": precision, "recall": recall, "f1": f1, "support": tp + fn}
    confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        confusion[row["expected"]][row["predicted"]] += 1
    return {
        "accuracy": correct / total if total else 0.0,
        "macro_precision": sum(item["precision"] for item in per_label.values()) / len(labels) if labels else 0,
        "macro_recall": sum(item["recall"] for item in per_label.values()) / len(labels) if labels else 0,
        "macro_f1": sum(item["f1"] for item in per_label.values()) / len(labels) if labels else 0,
        "per_label": per_label,
        "confusion_matrix": {key: dict(value) for key, value in confusion.items()},
        "support": dict(Counter(row["expected"] for row in rows)),
    }
