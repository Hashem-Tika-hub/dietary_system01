# ============================================================
#  06_kmeans_model.py — تجميع الusersين بخوارزمية K-Means
#  الأمر: python 06_kmeans_model.py
#
#  ما الذي يفعله هذا File؟
#  1. يحمّل بيانات الusersين الاصطناعيين
#  2. يجد أفضل قيمة K باستخدام Elbow Method + Silhouette Score
#  3. يدرّب نموذج K-Means ويحفظه
#  4. يصف كل cluster بالأرقام
# ============================================================

import pickle
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.cluster      import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics       import silhouette_score
from pathlib import Path
from config  import DATA_DIR, MODEL_DIR

MODEL_DIR.mkdir(exist_ok=True)

# ── ميزات التجميع ─────────────────────────────────────────
CLUSTER_FEATURES = [
    "age", "bmi", "activity_level",
    "has_diabetes", "has_bp", "has_cholesterol",
]

# أسماء المجموعات المتوقعة (تُحدَّد بعد فحص النتائج)
CLUSTER_LABELS = {
    0: "usersون عامون (متوازنون)",
    1: "رياضيون وباحثون عن بناء العضلات",
    2: "مرضى مزمنون (سكري / ضغط)",
    3: "ساعون لخسارة الوزن",
    4: "نشطون بدنياً فوق المتوسط",
}


def load_users() -> pd.DataFrame:
    path = DATA_DIR / "synthetic_users.csv"
    if not path.exists():
        raise FileNotFoundError(
            "synthetic_users.csv غير موجود!\n"
            "شغّل أولاً: python 05_user_profiler.py"
        )
    return pd.read_csv(path, encoding="utf-8-sig")


def prepare_features(df: pd.DataFrame) -> tuple:
    """تجهيز مصفوفة الميزات وتطبيق التطبيع"""
    # أضف BMI إن لم يكن موجوداً
    if "bmi" not in df.columns:
        df["bmi"] = df["weight"] / (df["height"] / 100) ** 2

    X = df[CLUSTER_FEATURES].copy().astype(float)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    return X_scaled, scaler


def find_optimal_k(X_scaled: np.ndarray,
                   k_range: range = range(2, 9)) -> int:
    """Elbow + Silhouette لاختيار أفضل K"""
    inertias    = []
    silhouettes = []

    print("  Testing different K values:")
    for k in k_range:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(X_scaled)
        inertias.append(km.inertia_)
        sil = silhouette_score(X_scaled, labels)
        silhouettes.append(sil)
        print(f"    K={k} | Inertia={km.inertia_:>8.0f} | "
              f"Silhouette={sil:.4f}")

    # Optimal K = أعلى Silhouette Score
    best_idx = int(np.argmax(silhouettes))
    best_k   = list(k_range)[best_idx]

    # ── رسم Elbow ──────────────────────────────────────────
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    fig.suptitle("اختيار القيمة المثلى لـ K", fontsize=13, fontweight="bold")

    axes[0].plot(list(k_range), inertias, "o-", color="#2a78d6", lw=2)
    axes[0].axvline(best_k, linestyle="--", color="#D85A30", alpha=0.7)
    axes[0].set_title("Elbow Method — الانحدار في الـ Inertia")
    axes[0].set_xlabel("count المجموعات K")
    axes[0].set_ylabel("Inertia")

    axes[1].plot(list(k_range), silhouettes, "s-", color="#1baf7a", lw=2)
    axes[1].axvline(best_k, linestyle="--", color="#D85A30", alpha=0.7,
                    label=f"Optimal K = {best_k}")
    axes[1].set_title("Silhouette Score (كلما ارتفع كان أفضل)")
    axes[1].set_xlabel("count المجموعات K")
    axes[1].set_ylabel("Silhouette Score")
    axes[1].legend()

    plt.tight_layout()
    chart_path = DATA_DIR / "charts" / "07_kmeans_elbow.png"
    plt.savefig(chart_path, dpi=140, bbox_inches="tight")
    plt.close()
    print(f"\n  ✓ Elbow chart saved: {chart_path.name}")

    return best_k


def train_kmeans(X_scaled: np.ndarray, k: int) -> KMeans:
    """تدريب K-Means بالقيمة المثلى"""
    model = KMeans(
        n_clusters=k,
        random_state=42,
        n_init=20,          # عدة محاولات للوصول لأفضل نتيجة
        max_iter=500,
    )
    model.fit(X_scaled)
    return model


def describe_clusters(df: pd.DataFrame,
                      labels: np.ndarray) -> pd.DataFrame:
    """وصف كل cluster بالإحصائيات"""
    df = df.copy()
    df["cluster"] = labels

    desc_cols = ["age", "bmi", "activity_level",
                 "has_diabetes", "has_bp", "daily_calories"]
    available  = [c for c in desc_cols if c in df.columns]

    summary = df.groupby("cluster")[available].mean().round(2)
    counts  = df["cluster"].value_counts().sort_index()
    summary["count"] = counts

    print("\n  Cluster descriptions:")
    print(f"  {'cluster':<6} {'count':<6} {'avg age':<12} "
          f"{'avg BMI':<12} {'avg activity':<12} {'سكري%':<8} {'ضغط%':<8}")
    print("  " + "-"*68)

    for i, row in summary.iterrows():
        label = CLUSTER_LABELS.get(i, f"cluster {i}")
        diab  = (df[df["cluster"]==i]["has_diabetes"].mean()*100)
        bp    = (df[df["cluster"]==i]["has_bp"].mean()*100)
        print(f"  {i:<6} {row['count']:<6.0f} "
              f"{row.get('age',0):<12.1f} "
              f"{row.get('bmi',0):<12.1f} "
              f"{row.get('activity_level',0):<12.1f} "
              f"{diab:<8.1f} {bp:<8.1f}")
        print(f"         → {label}")

    return summary


def plot_clusters(df: pd.DataFrame, labels: np.ndarray):
    """رسم المجموعات في فضاء BMI × Activity"""
    df = df.copy()
    df["cluster"] = labels

    colors = ["#2a78d6","#1baf7a","#eda100","#D85A30","#7F77DD"]
    fig, ax = plt.subplots(figsize=(9, 6))

    for i in range(labels.max() + 1):
        mask = df["cluster"] == i
        ax.scatter(
            df[mask]["bmi"],
            df[mask]["activity_level"],
            c=colors[i % len(colors)], alpha=0.6, s=40,
            label=f"C{i}: {CLUSTER_LABELS.get(i, '')} (n={mask.sum()})"
        )

    ax.set_xlabel("مؤشر كتلة الجسم BMI")
    ax.set_ylabel("مستوى Activity البدني (1-5)")
    ax.set_title("توزيع الusersين في المجموعات", fontweight="bold")
    ax.legend(fontsize=8, loc="upper right")

    chart_path = DATA_DIR / "charts" / "08_clusters_scatter.png"
    plt.tight_layout()
    plt.savefig(chart_path, dpi=140, bbox_inches="tight")
    plt.close()
    print(f"  ✓ Cluster scatter saved: {chart_path.name}")


def save_model(model: KMeans, scaler: StandardScaler, best_k: int):
    """حفظ النموذج والـ scaler"""
    bundle = {
        "model":          model,
        "scaler":         scaler,
        "k":              best_k,
        "features":       CLUSTER_FEATURES,
        "cluster_labels": CLUSTER_LABELS,
    }
    path = MODEL_DIR / "kmeans_model.pkl"
    with open(path, "wb") as f:
        pickle.dump(bundle, f)
    print(f"  ✓ Model saved: {path}")
    return path


def predict_cluster(user_features: list, model_path=None) -> int:
    """
    دالة مساعدة: تنبؤ cluster users جديد
    user_features = [age, bmi, activity, has_diabetes, has_bp, has_cholesterol]
    """
    if model_path is None:
        model_path = MODEL_DIR / "kmeans_model.pkl"

    with open(model_path, "rb") as f:
        bundle = pickle.load(f)

    X = np.array(user_features).reshape(1, -1)
    X_scaled = bundle["scaler"].transform(X)
    cluster  = int(bundle["model"].predict(X_scaled)[0])
    label    = bundle["cluster_labels"].get(cluster, f"cluster {cluster}")
    return cluster, label


# ── التشغيل الرئيسي ───────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*52)
    print("  نموذج K-Means لتجميع الusersين")
    print("="*52)

    # 1. تحميل البيانات
    print("\n[1/5] تحميل بيانات الusersين...")
    df = load_users()
    print(f"  {len(df)} users loaded")

    # 2. تجهيز الميزات
    print("\n[2/5] Preparing and normalizing features...")
    X_scaled, scaler = prepare_features(df)
    print(f"  Feature matrix: {X_scaled.shape[0]} users × {X_scaled.shape[1]} features")

    # 3. إيجاد أفضل K
    print("\n[3/5] Finding optimal K...")
    best_k = find_optimal_k(X_scaled)
    print(f"\n  ★ Optimal K = {best_k}")

    # 4. تدريب النموذج
    print(f"\n[4/5] Training K-Means with K={best_k}...")
    model  = train_kmeans(X_scaled, best_k)
    labels = model.labels_
    sil    = silhouette_score(X_scaled, labels)
    print(f"  Final Silhouette Score: {sil:.4f}")

    # 5. وصف وحفظ
    print("\n[5/5] Describing clusters and saving model...")
    describe_clusters(df, labels)
    plot_clusters(df, labels)
    save_model(model, scaler, best_k)

    # اختبار سريع
    print("\n  اختبار: تنبؤ cluster users جديد")
    test = [45, 29.0, 2, 1, 1, 0]   # age=45, bmi=29, activity=2, diabetes=True, bp=True
    cluster, label = predict_cluster(test)
    print(f"  الcluster: {cluster} → {label}")

    print(f"\n  Next: python 07_cbf_model.py")
