# ============================================================
#  04_explore_data.py — استكشاف البيانات ورسم المخططات
#  الأمر: python 04_explore_data.py
#
#  يرسم مخططات توضيحية لفهم البيانات قبل بناء النموذج
#  المخرجات: data/outputs/analysis/charts/ (folder يحتوي على صور PNG)
# ============================================================

import pandas as pd
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from pathlib import Path
from config import CHARTS_DIR, PROCESSED_FOODS_PATH

# ── إعداد matplotlib ──────────────────────────────────────
matplotlib.rcParams["axes.unicode_minus"] = False
plt.rcParams.update({
    "figure.facecolor" : "white",
    "axes.facecolor"   : "#f9f9f7",
    "axes.grid"        : True,
    "grid.alpha"       : 0.4,
    "grid.linestyle"   : "--",
    "axes.spines.top"  : False,
    "axes.spines.right": False,
    "font.size"        : 11,
})

CLEAN_PATH = PROCESSED_FOODS_PATH

# ── ألوان المشروع ─────────────────────────────────────────
C_BLUE   = "#2a78d6"
C_TEAL   = "#1baf7a"
C_AMBER  = "#eda100"
C_CORAL  = "#D85A30"
C_PURPLE = "#7F77DD"
PALETTE  = [C_BLUE, C_TEAL, C_AMBER, C_CORAL, C_PURPLE]


def load() -> pd.DataFrame:
    if not CLEAN_PATH.exists():
        raise FileNotFoundError(
            "foods_clean.csv غير موجود! شغّل أولاً: python 03_clean_data.py"
        )
    return pd.read_csv(CLEAN_PATH, encoding="utf-8-sig")


# ── المخططات ──────────────────────────────────────────────

def plot_calorie_distribution(df: pd.DataFrame):
    """توزيع الcalories الحرارية"""
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
    fig.suptitle("توزيع الcalories الحرارية", fontsize=14, fontweight="bold", y=1.02)

    # يسار: Histogram
    ax = axes[0]
    ax.hist(df["calories"], bins=40, color=C_BLUE, alpha=0.85, edgecolor="white")
    ax.axvline(df["calories"].mean(), color=C_CORAL, lw=2, linestyle="--",
               label=f"المتوسط: {df['calories'].mean():.0f}")
    ax.axvline(df["calories"].median(), color=C_AMBER, lw=2, linestyle=":",
               label=f"الوسيط: {df['calories'].median():.0f}")
    ax.set_xlabel("الcalories (كيلوkcal / 100g)")
    ax.set_ylabel("count الأطعمة")
    ax.set_title("التوزيع الكامل")
    ax.legend(fontsize=9)

    # يمين: Pie مستوى الcalories
    ax = axes[1]
    counts = df["calorie_level"].value_counts()
    order  = [l for l in ["منخفض", "متوسط", "مرتفع", "عالي جداً"] if l in counts]
    wedge_colors = [C_TEAL, C_BLUE, C_AMBER, C_CORAL]
    ax.pie(counts[order], labels=order, autopct="%1.1f%%",
           colors=wedge_colors[:len(order)],
           startangle=90, textprops={"fontsize": 9})
    ax.set_title("توزيع مستوى الcalories")

    plt.tight_layout()
    path = CHARTS_DIR / "01_calorie_distribution.png"
    plt.savefig(path, dpi=140, bbox_inches="tight")
    plt.close()
    print(f"  ✓ {path.name}")


def plot_macronutrients(df: pd.DataFrame):
    """مقارنة المغذيات الكبرى"""
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    fig.suptitle("تحليل المغذيات الكبرى", fontsize=14, fontweight="bold")

    nutrients = [
        ("protein", "الprotein",       C_TEAL,   "g / 100g"),
        ("carbs",   "الcarbs",   C_AMBER,  "g / 100g"),
        ("fat",     "الfat",          C_CORAL,  "g / 100g"),
        ("fiber",   "الfiber الغذائية", C_PURPLE, "g / 100g"),
    ]

    for ax, (col, label, color, unit) in zip(axes.flat, nutrients):
        data = df[col].dropna()
        ax.hist(data, bins=35, color=color, alpha=0.82, edgecolor="white")
        ax.axvline(data.mean(), color="#333", lw=1.5, linestyle="--",
                   label=f"متوسط: {data.mean():.1f}{unit}")
        ax.set_title(label, fontweight="bold")
        ax.set_xlabel(unit)
        ax.set_ylabel("count الأطعمة")
        ax.legend(fontsize=9)

    plt.tight_layout()
    path = CHARTS_DIR / "02_macronutrients.png"
    plt.savefig(path, dpi=140, bbox_inches="tight")
    plt.close()
    print(f"  ✓ {path.name}")


def plot_top_categories(df: pd.DataFrame):
    """أكثر فئات الfoods شيوعاً"""
    if "category" not in df.columns:
        return

    counts = (df["category"]
              .dropna()
              .value_counts()
              .head(12))

    fig, ax = plt.subplots(figsize=(11, 5))
    bars = ax.barh(counts.index[::-1], counts.values[::-1],
                   color=C_BLUE, alpha=0.85, height=0.65)

    # أضف الأرقام على اليمين
    for bar, val in zip(bars, counts.values[::-1]):
        ax.text(val + 2, bar.get_y() + bar.get_height() / 2,
                str(val), va="center", fontsize=9, color="#333")

    ax.set_title("أكثر 12 فئة foods في قاعدة البيانات", fontweight="bold", fontsize=13)
    ax.set_xlabel("count الأطعمة")
    ax.set_xlim(0, counts.max() * 1.15)

    plt.tight_layout()
    path = CHARTS_DIR / "03_top_categories.png"
    plt.savefig(path, dpi=140, bbox_inches="tight")
    plt.close()
    print(f"  ✓ {path.name}")


def plot_protein_vs_calories(df: pd.DataFrame):
    """علاقة الprotein بالcalories مع تلوين حسب الفئة"""
    fig, ax = plt.subplots(figsize=(10, 6))

    # نقاط مبعثرة مع تلوين بالـ health_score
    sc = ax.scatter(
        df["calories"], df["protein"],
        c=df["health_score"], cmap="RdYlGn",
        alpha=0.45, s=18, linewidths=0
    )
    plt.colorbar(sc, ax=ax, label="نقاط الصحة (0-100)")

    # أضف خطوط تلقائية
    ax.axvline(200, color=C_AMBER, lw=1, linestyle=":", alpha=0.7, label="200 كيلوkcal")
    ax.axhline(15,  color=C_TEAL,  lw=1, linestyle=":", alpha=0.7, label="15g protein")

    ax.set_xlabel("الcalories الحرارية (كيلوkcal / 100g)")
    ax.set_ylabel("الprotein (g / 100g)")
    ax.set_title("علاقة الprotein بالcalories الحرارية", fontweight="bold", fontsize=13)
    ax.legend(fontsize=9)

    # علّم بعض الأطعمة المحلية
    local = df[df["source"] == "local"]
    for _, row in local.head(8).iterrows():
        ax.annotate(row["name"], (row["calories"], row["protein"]),
                    fontsize=7, color=C_PURPLE, alpha=0.8,
                    xytext=(4, 4), textcoords="offset points")

    plt.tight_layout()
    path = CHARTS_DIR / "04_protein_vs_calories.png"
    plt.savefig(path, dpi=140, bbox_inches="tight")
    plt.close()
    print(f"  ✓ {path.name}")


def plot_health_flags(df: pd.DataFrame):
    """نسبة الأطعمة الصحية حسب العلامات"""
    flags = {
        "عالي الprotein\n(≥15g)":       df["is_high_protein"].sum(),
        "Diabetic friendly\n(سكر<5g)": df["diabetic_friendly"].sum(),
        "Low sodium\n(<140mg)":    df["low_sodium"].sum(),
    }
    total = len(df)

    fig, ax = plt.subplots(figsize=(9, 4))
    bars = ax.bar(flags.keys(), flags.values(),
                  color=[C_TEAL, C_PURPLE, C_BLUE],
                  alpha=0.85, width=0.5, edgecolor="white")

    for bar, val in zip(bars, flags.values()):
        pct = val / total * 100
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + total * 0.01,
                f"{val:,}\n({pct:.1f}%)",
                ha="center", va="bottom", fontsize=10, fontweight="bold")

    ax.set_ylim(0, max(flags.values()) * 1.2)
    ax.set_title(f"count الأطعمة لكل فئة صحية (من {total:,} foods)", fontweight="bold")
    ax.set_ylabel("count الأطعمة")

    plt.tight_layout()
    path = CHARTS_DIR / "05_health_flags.png"
    plt.savefig(path, dpi=140, bbox_inches="tight")
    plt.close()
    print(f"  ✓ {path.name}")


def plot_local_vs_usda(df: pd.DataFrame):
    """مقارنة الأطعمة المحلية مقابل USDA"""
    local = df[df["source"] == "local"]
    usda  = df[df["source"] != "local"]

    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5))
    fig.suptitle("مقارنة الأطعمة المحلية مقابل USDA", fontweight="bold")

    metrics = [
        ("calories", "الcalories"),
        ("protein",  "الprotein"),
        ("fiber",    "الfiber"),
    ]

    for ax, (col, label) in zip(axes, metrics):
        data = [local[col].dropna(), usda[col].dropna()]
        bp = ax.boxplot(data, patch_artist=True, widths=0.5,
                        medianprops=dict(color="white", lw=2))
        bp["boxes"][0].set_facecolor(C_TEAL)
        bp["boxes"][1].set_facecolor(C_BLUE)
        ax.set_xticklabels(["محلي", "USDA"])
        ax.set_title(label, fontweight="bold")
        ax.set_ylabel("g / 100g" if col != "calories" else "كيلوkcal")

    plt.tight_layout()
    path = CHARTS_DIR / "06_local_vs_usda.png"
    plt.savefig(path, dpi=140, bbox_inches="tight")
    plt.close()
    print(f"  ✓ {path.name}")


# ── التشغيل الرئيسي ───────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  Data Exploration — Generating Charts")
    print("=" * 50)

    print("\n  Loading data...")
    df = load()
    print(f"  {len(df):,} foods loaded")

    print("\n  Generating charts:")
    plot_calorie_distribution(df)
    plot_macronutrients(df)
    plot_top_categories(df)
    plot_protein_vs_calories(df)
    plot_health_flags(df)
    plot_local_vs_usda(df)

    print(f"\n  Charts saved to: {CHARTS_DIR}")
    print(f"  افتح الfolder لرؤية الصور: start {CHARTS_DIR}")
    print("\n  Phase 1 completed successfully!")
    print("  Next: Phase 2 — Build ML model")
