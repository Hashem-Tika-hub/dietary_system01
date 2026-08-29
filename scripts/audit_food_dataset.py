"""Audit the processed food catalog without mutating source data."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = ROOT / "data" / "processed" / "foods_clean.csv"
REPORT_DIR = ROOT / "reports"
NUMERIC_COLUMNS = [
    "calories",
    "protein",
    "carbs",
    "fat",
    "fiber",
    "sugar",
    "sodium",
    "calcium",
    "iron",
]
MACRO_COLUMNS = ["calories", "protein", "carbs", "fat"]
FEATURE_COLUMNS = ["fiber", "sugar", "sodium"]
TEXT_COLUMNS = ["fdc_id", "name", "category", "food_group", "meal_type", "source"]


def _json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(v) for v in value]
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _series_stats(frame: pd.DataFrame) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for column in frame.columns:
        series = frame[column]
        result[column] = {
            "dtype": str(series.dtype),
            "missing": int(series.isna().sum()),
            "missing_percentage": round(float(series.isna().mean() * 100), 2),
            "unique": int(series.nunique(dropna=True)),
        }
        if pd.api.types.is_numeric_dtype(series):
            result[column].update(
                {
                    "minimum": _json_value(series.min()),
                    "maximum": _json_value(series.max()),
                    "mean": _json_value(series.mean()),
                }
            )
    return result


def main() -> None:
    frame = pd.read_csv(DATASET_PATH, encoding="utf-8-sig")
    numeric_conversion: dict[str, int] = {}
    for column in NUMERIC_COLUMNS:
        converted = pd.to_numeric(frame[column], errors="coerce")
        numeric_conversion[column] = int(converted.isna().sum())
        frame[column] = converted

    duplicate_names = frame[frame["name"].duplicated(keep=False)].copy()
    duplicate_name_groups = []
    for name, group in duplicate_names.groupby("name", dropna=False):
        nutrient_rows = group[NUMERIC_COLUMNS].drop_duplicates()
        duplicate_name_groups.append(
            {
                "name": str(name),
                "records": int(len(group)),
                "same_nutrition": len(nutrient_rows) == 1,
                "fdc_ids": [str(value) for value in group["fdc_id"].tolist()],
            }
        )

    exact_duplicates = int(frame.duplicated(keep=False).sum())
    negative_values = {
        column: int((frame[column] < 0).fillna(False).sum()) for column in NUMERIC_COLUMNS
    }
    impossible_values = {
        "calories_above_900_per_100g": int((frame["calories"] > 900).fillna(False).sum()),
        "protein_above_100g_per_100g": int((frame["protein"] > 100).fillna(False).sum()),
        "carbs_above_100g_per_100g": int((frame["carbs"] > 100).fillna(False).sum()),
        "fat_above_100g_per_100g": int((frame["fat"] > 100).fillna(False).sum()),
    }

    estimated_calories = (
        frame["protein"] * 4 + frame["carbs"] * 4 + frame["fat"] * 9
    )
    residual = (frame["calories"] - estimated_calories).abs()
    calorie_consistency = {
        "formula": "protein_g * 4 + carbs_g * 4 + fat_g * 9",
        "rows_evaluated": int(residual.notna().sum()),
        "rows_within_20_kcal": int((residual <= 20).fillna(False).sum()),
        "rows_outside_20_kcal": int((residual > 20).fillna(False).sum()),
        "rows_outside_20_percent": int(
            (residual > (frame["calories"].abs() * 0.2).clip(lower=20)).fillna(False).sum()
        ),
        "maximum_absolute_residual_kcal": _json_value(residual.max()),
    }

    whitespace_issues: dict[str, int] = {}
    for column in TEXT_COLUMNS:
        values = frame[column].dropna().astype(str)
        whitespace_issues[column] = int(
            values.map(lambda value: value != value.strip() or bool(re.search(r"\\s{2,}", value))).sum()
        )

    category_values = sorted(str(value) for value in frame["category"].dropna().unique())
    meal_type_values = sorted(str(value) for value in frame["meal_type"].dropna().unique())
    source_values = sorted(str(value) for value in frame["source"].dropna().unique())
    feature_coverage = {}
    for column in FEATURE_COLUMNS:
        available = int(frame[column].notna().sum())
        feature_coverage[column] = {
            "total_records": int(len(frame)),
            "available_values": available,
            "missing_values": int(len(frame) - available),
            "coverage_percentage": round(available / len(frame) * 100, 2),
        }

    report: dict[str, Any] = {
        "dataset": str(DATASET_PATH.relative_to(ROOT)),
        "rows": int(len(frame)),
        "columns": int(len(frame.columns)),
        "column_names": [str(column) for column in frame.columns],
        "column_stats": _series_stats(frame),
        "numeric_conversion_failures": numeric_conversion,
        "duplicates": {
            "exact_duplicate_rows": exact_duplicates,
            "duplicate_name_groups": duplicate_name_groups,
            "duplicate_name_group_count": len(duplicate_name_groups),
            "same_name_same_nutrition_groups": sum(
                bool(group["same_nutrition"]) for group in duplicate_name_groups
            ),
            "same_name_conflicting_nutrition_groups": sum(
                not bool(group["same_nutrition"]) for group in duplicate_name_groups
            ),
        },
        "negative_nutritional_values": negative_values,
        "impossible_nutritional_values": impossible_values,
        "calorie_consistency": calorie_consistency,
        "feature_coverage": feature_coverage,
        "serving_information": {
            "serving_columns_present": [
                column for column in frame.columns if "serv" in column.lower() or "portion" in column.lower()
            ],
            "basis_assumed_by_processed_schema": "100 grams",
            "missing_serving_metadata": True,
        },
        "unit_consistency": {
            "standard_basis": "per 100 grams",
            "explicit_unit_columns_present": False,
            "note": "Nutrient columns are interpreted as per 100 grams by the importer; explicit unit metadata is added in the normalized database layer.",
        },
        "text_formatting": {
            "whitespace_issues": whitespace_issues,
            "category_count": len(category_values),
            "categories": category_values,
            "meal_type_count": len(meal_type_values),
            "meal_types": meal_type_values,
            "source_count": len(source_values),
            "sources": source_values,
        },
        "decisions": {
            "exact_duplicates": "No records are deleted by this audit. Any future removal must be documented and tested.",
            "duplicate_names": "Duplicate names are reported; identical and conflicting nutrition are not silently merged.",
            "nutrition": "Suspicious values are flagged only. Existing source values are not overwritten.",
            "missing_values": "Missing values remain missing and are not replaced with fabricated numbers.",
        },
        "limitations": [
            "The processed CSV does not contain explicit serving-size and serving-unit columns.",
            "The processed CSV stores category and meal type as text; normalized lookup tables are required for controlled values.",
            "Nutritional consistency against macronutrient energy is a plausibility signal, not a laboratory validation.",
            "Allergen evidence is separate from this numeric dataset and missing evidence is not treated as safety.",
        ],
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_DIR / "food_dataset_audit.json"
    md_path = REPORT_DIR / "food_dataset_audit.md"
    json_path.write_text(json.dumps(_json_value(report), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = [
        "# تقرير تدقيق مجموعة بيانات الأطعمة",
        "",
        f"> المصدر المدقق: `{report['dataset']}`. هذا التقرير وصفي ولا يعدّل أي قيمة في المصدر.",
        "",
        "## ملخص الأرقام",
        "",
        "| المؤشر | القيمة |",
        "|---|---:|",
        f"| عدد السجلات | {report['rows']} |",
        f"| عدد الأعمدة | {report['columns']} |",
        f"| الصفوف المتطابقة تمامًا | {exact_duplicates} |",
        f"| مجموعات الأسماء المكررة | {len(duplicate_name_groups)} |",
        f"| قيم غذائية سالبة | {sum(negative_values.values())} |",
        f"| إخفاقات تحويل رقمية | {sum(numeric_conversion.values())} |",
        "",
        "## التغطية الغذائية",
        "",
        "| الميزة | إجمالي السجلات | القيم المتاحة | القيم المفقودة | نسبة التغطية |",
        "|---|---:|---:|---:|---:|",
    ]
    for column, values in feature_coverage.items():
        md.append(
            f"| `{column}` | {values['total_records']} | {values['available_values']} | {values['missing_values']} | {values['coverage_percentage']}% |"
        )
    md.extend(
        [
            "",
            "## التكرارات والقرارات",
            "",
            "لم يحذف التدقيق أي سجل. التكرارات التامة ومجموعات الأسماء المتشابهة تُسجل للمراجعة؛ وعند وجود اختلاف غذائي لا يجوز الدمج الصامت لأن الاختلاف قد يمثل طريقة تحضير أو أساس حصة مختلفًا.",
            "",
            "## القيم الغذائية",
            "",
            f"بلغ عدد الصفوف التي تتجاوز 900 سعرة لكل 100 غرام {impossible_values['calories_above_900_per_100g']}، وعدد الصفوف التي تتجاوز حدود البروتين أو الكربوهيدرات أو الدهون النظرية هو {sum(impossible_values.values()) - impossible_values['calories_above_900_per_100g']}. هذه مؤشرات تدقيق فقط ولا تعني حذف السجل.",
            "",
            f"اختبار الاتساق التقريبي استخدم المعادلة `{calorie_consistency['formula']}`. عدد الصفوف خارج هامش 20 سعرة هو {calorie_consistency['rows_outside_20_kcal']} من أصل {calorie_consistency['rows_evaluated']}. يتأثر هذا المؤشر بالألياف والتقريب وطرق القياس، ولذلك لم تُستبدل أي قيمة.",
            "",
            "## حدود المصدر",
            "",
            "لا يحتوي CSV المعالج على أعمدة صريحة لحجم الحصة ووحدتها، ولذلك تفسر طبقة الاستيراد المغذيات على أساس 100 غرام وتخزن هذا الأساس في قاعدة البيانات. كما أن التصنيفات وأنواع الوجبات نصية في المصدر وستدعمها طبقة lookup normalized دون حذف الحقول القديمة المستخدمة في API.",
            "",
            "## ملف قابل للمعالجة آليًا",
            "",
            "التفاصيل الكاملة والأرقام الخام موجودة في `reports/food_dataset_audit.json`.",
        ]
    )
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    nutrition_md = [
        "# تقرير التحقق من القيم الغذائية",
        "",
        "> هذا التقرير يحدد القيم المشبوهة أو غير المتسقة إحصائيًا، ولا يستبدل مراجعة المصدر ولا يعدّل البيانات.",
        "",
        "## قواعد التحقق",
        "",
        "تم فحص عدم السلبية، وإمكانية التحويل الرقمي، والحدود القصوى النظرية لكل 100 غرام، واتساق تقريبي للسعرات مع البروتين والكربوهيدرات والدهون عبر المعادلة `protein_g × 4 + carbs_g × 4 + fat_g × 9`.",
        "",
        "| الفحص | النتيجة |",
        "|---|---:|",
        f"| الصفوف المفحوصة | {len(frame)} |",
        f"| قيم غذائية سالبة | {sum(negative_values.values())} |",
        f"| إخفاقات التحويل الرقمي | {sum(numeric_conversion.values())} |",
        f"| سعرات أعلى من 900 لكل 100 غرام | {impossible_values['calories_above_900_per_100g']} |",
        f"| بروتين/كربوهيدرات/دهون أعلى من 100 غرام لكل 100 غرام | {sum(impossible_values.values()) - impossible_values['calories_above_900_per_100g']} |",
        f"| صفوف خارج هامش 20 سعرة في اختبار الاتساق | {calorie_consistency['rows_outside_20_kcal']} |",
        f"| صفوف خارج هامش 20% بحد أدنى 20 سعرة | {calorie_consistency['rows_outside_20_percent']} |",
        "",
        "## القرار",
        "",
        "لم تُعدّل القيم الغذائية ولم تُحذف السجلات. الصفوف المخالفة لهامش الاتساق تُعامل كإشارات مراجعة؛ فقد تتأثر بالألياف والتقريب وطريقة القياس. ولا يكفي هذا الفحص لإثبات الجودة المخبرية أو السلامة الطبية.",
        "",
        "## التغطية",
        "",
        "| الميزة | الإجمالي | المتاح | المفقود | التغطية |",
        "|---|---:|---:|---:|---:|",
    ]
    for column, values in feature_coverage.items():
        nutrition_md.append(
            f"| `{column}` | {values['total_records']} | {values['available_values']} | {values['missing_values']} | {values['coverage_percentage']}% |"
        )
    nutrition_md.extend(
        [
            "",
            "## حدود التحقق",
            "",
            "المصدر لا يحمل أعمدة صريحة لحجم الحصة ووحدتها؛ طبقة الاستيراد تفسر المغذيات لكل 100 غرام وتحتفظ بهذا الأساس في النموذج. كما لا يجوز اعتبار عدم وجود قيمة حساسية دليلًا على خلو الطعام من المسبب.",
        ]
    )
    (REPORT_DIR / "nutrition_validation_report.md").write_text("\n".join(nutrition_md) + "\n", encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
