#!/usr/bin/env python3
"""Evaluate K-Means choices for food-diversity clustering.

This script evaluates the same nutrient space used by
``api.services.recommendation_policy.build_food_cluster_map``. It is an
unsupervised catalog-quality assessment for diversity only; it does not make
medical or clinical claims and it must not override hard food-eligibility rules.

Outputs:
  - reports/kmeans_cluster_evaluation_metrics.csv
  - reports/kmeans_cluster_evaluation.json
  - reports/kmeans_cluster_evaluation_ar.md
  - reports/kmeans_cluster_evaluation.png
"""

from __future__ import annotations

import argparse
import json
from itertools import combinations
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import (
    adjusted_rand_score,
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "data" / "processed" / "foods_clean.csv"
DEFAULT_REPORTS = ROOT / "reports"
FEATURES = ("calories", "protein", "carbs", "fat", "fiber", "sugar", "sodium")
BASE_SEED = 42
STABILITY_SEEDS = tuple(range(11, 21))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate K-Means cluster counts for the curated food catalog."
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORTS)
    parser.add_argument("--min-k", type=int, default=2)
    parser.add_argument("--max-k", type=int, default=12)
    return parser.parse_args()


def prepare_catalog(path: Path) -> tuple[pd.DataFrame, np.ndarray, list[str]]:
    if not path.exists():
        raise FileNotFoundError(f"Catalog not found: {path}")

    foods = pd.read_csv(path, encoding="utf-8-sig")
    available = [feature for feature in FEATURES if feature in foods.columns]
    if len(available) < 2:
        raise ValueError(
            "At least two cluster features are required; "
            f"available features: {available}"
        )

    if "fdc_id" in foods.columns:
        foods = foods.drop_duplicates(subset=["fdc_id"]).copy()
    else:
        foods = foods.drop_duplicates().copy()

    numeric = foods[available].apply(pd.to_numeric, errors="coerce")
    numeric = numeric.fillna(numeric.median(numeric_only=True)).fillna(0.0)
    matrix = StandardScaler().fit_transform(numeric)
    return foods, matrix, available


def mean_pairwise_ari(labels_by_seed: list[np.ndarray]) -> float:
    scores = [
        adjusted_rand_score(left, right)
        for left, right in combinations(labels_by_seed, 2)
    ]
    return float(np.mean(scores)) if scores else 1.0


def evaluate_k_values(matrix: np.ndarray, min_k: int, max_k: int) -> list[dict[str, Any]]:
    if min_k < 2:
        raise ValueError("min-k must be at least 2")

    rows: list[dict[str, Any]] = []
    maximum = min(max_k, len(matrix) - 1)
    if maximum < min_k:
        raise ValueError("Catalog is too small for the requested K range")

    for k in range(min_k, maximum + 1):
        primary = KMeans(n_clusters=k, random_state=BASE_SEED, n_init=20).fit(matrix)
        labels = primary.labels_
        cluster_sizes = np.bincount(labels, minlength=k)
        labels_by_seed = [
            KMeans(n_clusters=k, random_state=seed, n_init=20).fit_predict(matrix)
            for seed in STABILITY_SEEDS
        ]

        rows.append(
            {
                "k": k,
                "inertia": float(primary.inertia_),
                "silhouette": float(silhouette_score(matrix, labels)),
                "calinski_harabasz": float(calinski_harabasz_score(matrix, labels)),
                "davies_bouldin": float(davies_bouldin_score(matrix, labels)),
                "stability_ari": mean_pairwise_ari(labels_by_seed),
                "smallest_cluster": int(cluster_sizes.min()),
                "largest_cluster": int(cluster_sizes.max()),
                "largest_cluster_share": float(cluster_sizes.max() / len(matrix)),
                "cluster_sizes": [int(size) for size in cluster_sizes.tolist()],
            }
        )
    return rows


def add_rank_summary(metrics: pd.DataFrame) -> pd.DataFrame:
    ranked = metrics.copy()
    ranked["silhouette_rank"] = ranked["silhouette"].rank(ascending=False, method="min")
    ranked["calinski_harabasz_rank"] = ranked["calinski_harabasz"].rank(
        ascending=False, method="min"
    )
    ranked["davies_bouldin_rank"] = ranked["davies_bouldin"].rank(
        ascending=True, method="min"
    )
    ranked["stability_rank"] = ranked["stability_ari"].rank(ascending=False, method="min")
    ranked["balance_rank"] = ranked["largest_cluster_share"].rank(
        ascending=True, method="min"
    )
    ranked["mean_rank"] = ranked[
        [
            "silhouette_rank",
            "calinski_harabasz_rank",
            "davies_bouldin_rank",
            "stability_rank",
            "balance_rank",
        ]
    ].mean(axis=1)
    return ranked.sort_values(["mean_rank", "k"], ascending=[True, True]).reset_index(drop=True)


def create_plot(metrics: pd.DataFrame, output: Path) -> None:
    ordered = metrics.sort_values("k")
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    fig.suptitle("K-Means food catalog evaluation (standardized nutrient features)", fontsize=14)

    chart_specs = [
        ("inertia", "Inertia / elbow", "lower is expected as K grows"),
        ("silhouette", "Silhouette score", "higher is better"),
        ("calinski_harabasz", "Calinski-Harabasz index", "higher is better"),
        ("davies_bouldin", "Davies-Bouldin index", "lower is better"),
    ]
    for axis, (column, title, note) in zip(axes.flat, chart_specs):
        axis.plot(ordered["k"], ordered[column], marker="o", linewidth=2, color="#1f6f8b")
        axis.set_title(title)
        axis.set_xlabel("Number of clusters (K)")
        axis.set_ylabel(column.replace("_", " ").title())
        axis.set_xticks(ordered["k"])
        axis.grid(alpha=0.25)
        axis.text(
            0.02,
            0.05,
            note,
            transform=axis.transAxes,
            fontsize=9,
            color="#4b5563",
        )
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def format_number(value: float) -> str:
    return f"{value:.4f}"


def write_arabic_report(
    output: Path,
    *,
    dataset: Path,
    food_count: int,
    features: list[str],
    ranked: pd.DataFrame,
) -> None:
    best = ranked.iloc[0]
    by_silhouette = ranked.loc[ranked["silhouette"].idxmax()]
    by_ch = ranked.loc[ranked["calinski_harabasz"].idxmax()]
    by_db = ranked.loc[ranked["davies_bouldin"].idxmin()]

    lines = [
        "# تقرير تقييم K-Means لاختيار مجموعات تنويع الأطعمة",
        "",
        "> هذا التقييم يختبر تجميع الأطعمة بحسب ملفها الغذائي بهدف تنويع الاقتراحات. لا يمثل تشخيصًا طبيًا، ولا يسمح لـK-Means بتجاوز الحساسية أو قيود الأهلية الصلبة.",
        "",
        "## 1. إعداد التجربة",
        "",
        f"استُخدم الكتالوج `{dataset.name}` بعد إزالة التكرار، بعدد **{food_count}** صنفًا. "
        f"استُخدمت الميزات العددية التالية بعد StandardScaler: `{', '.join(features)}`. "
        f"اختُبرت قيم K من {int(ranked['k'].min())} إلى {int(ranked['k'].max())} مع `n_init=20` وseed ثابت للنتيجة الأساسية، ثم 10 seeds إضافية لحساب استقرار التسميات عبر Adjusted Rand Index.",
        "",
        "## 2. المؤشرات",
        "",
        "| المؤشر | التفسير | الاتجاه المرغوب |",
        "|---|---|---|",
        "| Inertia | مقدار التشتت داخل المجموعات؛ يستخدم لرؤية نقطة الانعطاف. | لا يختار K منفردًا؛ ينخفض طبيعيًا مع زيادة K. |",
        "| Silhouette | تماسك الصنف داخل مجموعته وانفصاله عن المجموعات الأخرى. | الأعلى أفضل. |",
        "| Calinski–Harabasz | نسبة التشتت بين المجموعات إلى داخلها. | الأعلى أفضل. |",
        "| Davies–Bouldin | مقدار تشابه المجموعات ببعضها. | الأقل أفضل. |",
        "| Stability ARI | ثبات التجميع عند تغيير نقطة البدء. | الأعلى أفضل. |",
        "| Largest cluster share | مؤشر توازن تقريبي؛ يمنع مجموعات مهيمنة جدًا. | الأقل أفضل عمومًا. |",
        "",
        "## 3. النتائج",
        "",
        "| K | Inertia | Silhouette | Calinski–Harabasz | Davies–Bouldin | Stability ARI | أصغر مجموعة | أكبر مجموعة | حصة أكبر مجموعة | متوسط الرتبة |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for _, row in ranked.sort_values("k").iterrows():
        lines.append(
            "| {k} | {inertia} | {silhouette} | {ch} | {db} | {ari} | {smallest} | {largest} | {share} | {rank} |".format(
                k=int(row["k"]),
                inertia=format_number(row["inertia"]),
                silhouette=format_number(row["silhouette"]),
                ch=format_number(row["calinski_harabasz"]),
                db=format_number(row["davies_bouldin"]),
                ari=format_number(row["stability_ari"]),
                smallest=int(row["smallest_cluster"]),
                largest=int(row["largest_cluster"]),
                share=format_number(row["largest_cluster_share"]),
                rank=format_number(row["mean_rank"]),
            )
        )

    lines.extend(
        [
            "",
            "## 4. قراءة القرار",
            "",
            f"تعطي الرتبة المركبة غير الطبية أفضلية أولية لـ **K={int(best['k'])}** بمتوسط رتبة `{format_number(best['mean_rank'])}`. "
            "هذه ليست حقيقة مطلقة؛ هي طريقة شفافة لترتيب المرشحين بعد جمع عدة مؤشرات بدل اختيار رقم اعتباطي.",
            "",
            f"أعلى Silhouette ظهرت عند **K={int(by_silhouette['k'])}** (`{format_number(by_silhouette['silhouette'])}`)، "
            f"وأعلى Calinski–Harabasz عند **K={int(by_ch['k'])}** (`{format_number(by_ch['calinski_harabasz'])}`)، "
            f"وأقل Davies–Bouldin عند **K={int(by_db['k'])}** (`{format_number(by_db['davies_bouldin'])}`).",
            "",
            "يجب أن يكون القرار النهائي أصغر K يقع ضمن القيم الجيدة رياضيًا، ويعطي مجموعات مفهومة غذائيًا، ويزيد تنوع الخطة الأسبوعية دون أي خرق للقيود الصلبة. لذلك يجب توثيق فحص نوعي لأمثلة الأطعمة وحجم كل مجموعة قبل تغيير قيمة `n_clusters` الافتراضية في محرك التوصية.",
            "",
            "## 5. حدود التقييم",
            "",
            "لا تقيس هذه المؤشرات رضا مستخدمين حقيقيين أو فعالية صحية أو دقة سريرية. كما أنها لا تختبر زمن API. هي تقيس فقط جودة التجميع في فضاء المغذيات الموحّد وتدعمه بمؤشر استقرار. يجب الاحتفاظ بفلترة الحساسية ونوع الوجبة والتفضيلات قبل ترتيب أو تنويع المرشحين.",
            "",
            "## 6. مخرجات قابلة للإدراج في التقرير",
            "",
            "- `kmeans_cluster_evaluation_metrics.csv`: جدول النتائج الخام القابل للتحليل.",
            "- `kmeans_cluster_evaluation.json`: نسخة منظمة للنتائج والإعدادات.",
            "- `kmeans_cluster_evaluation.png`: رسوم Elbow وSilhouette وCalinski–Harabasz وDavies–Bouldin.",
            "",
        ]
    )
    output.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    foods, matrix, features = prepare_catalog(args.dataset)
    raw_rows = evaluate_k_values(matrix, args.min_k, args.max_k)
    metrics = add_rank_summary(pd.DataFrame(raw_rows))

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = output_dir / "kmeans_cluster_evaluation_metrics.csv"
    json_path = output_dir / "kmeans_cluster_evaluation.json"
    report_path = output_dir / "kmeans_cluster_evaluation_ar.md"
    plot_path = output_dir / "kmeans_cluster_evaluation.png"

    metrics.sort_values("k").to_csv(metrics_path, index=False)
    create_plot(metrics, plot_path)
    write_arabic_report(
        report_path,
        dataset=args.dataset,
        food_count=len(foods),
        features=features,
        ranked=metrics,
    )

    payload = {
        "dataset": str(args.dataset.relative_to(ROOT)),
        "food_count": int(len(foods)),
        "features": features,
        "base_seed": BASE_SEED,
        "stability_seeds": list(STABILITY_SEEDS),
        "recommended_candidate_by_mean_rank": int(metrics.iloc[0]["k"]),
        "metrics": json.loads(metrics.sort_values("k").to_json(orient="records")),
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    best = metrics.iloc[0]
    print(f"Evaluated {len(foods)} foods across K={args.min_k}..{args.max_k}.")
    print(
        "Best preliminary candidate by mean metric rank: "
        f"K={int(best['k'])} (mean_rank={best['mean_rank']:.3f})."
    )
    print(f"Wrote: {metrics_path.relative_to(ROOT)}")
    print(f"Wrote: {json_path.relative_to(ROOT)}")
    print(f"Wrote: {report_path.relative_to(ROOT)}")
    print(f"Wrote: {plot_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
