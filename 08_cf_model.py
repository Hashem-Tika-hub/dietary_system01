# ============================================================
#  08_cf_model.py — Collaborative Filtering (CF) Model
#  الأمر: python 08_cf_model.py
#
#  الفكرة:
#  "الusersون المتشابهون يحبون نفس الأطعمة"
#  1. ننشئ مصفوفة (usersين × أطعمة) بتقييمات اصطناعية
#  2. لكل users جديد نجد الusersين الأشبه به
#  3. نقترح الأطعمة التي أحبّها المشابهون له
# ============================================================

import pickle
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing    import MinMaxScaler
from pathlib import Path
from config import CHARTS_DIR, MODEL_DIR, PROCESSED_FOODS_PATH, SYNTHETIC_USERS_PATH

import importlib.util

def _import_user_profiler():
    spec = importlib.util.spec_from_file_location(
        "up", Path(__file__).parent / "05_user_profiler.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def _import_meal_rules():
    spec = importlib.util.spec_from_file_location(
        "mr", Path(__file__).parent / "meal_rules.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

meal_rules = _import_meal_rules()


class CollaborativeFilter:
    """
    نموذج التصفية التعاونية (User-Based CF)

    الاستخدام:
        cf = CollaborativeFilter()
        cf.fit(ratings_matrix, users_df, foods_df)
        recs = cf.recommend(new_user, top_k=10)
    """

    def __init__(self, n_neighbors: int = 20):
        self.n_neighbors   = n_neighbors
        self.ratings       = None   # مصفوفة التقييمات (n_users × n_foods)
        self.user_sim      = None   # مصفوفة تشابه الusersين
        self.users_df      = None
        self.foods_df      = None
        self.feature_scaler = MinMaxScaler()
        self.is_fitted     = False

    def fit(self, ratings: np.ndarray,
            users_df: pd.DataFrame,
            foods_df: pd.DataFrame) -> "CollaborativeFilter":
        """
        تدريب النموذج
        ratings : مصفوفة (n_users × n_foods) - القيم بين 0 و 5
        """
        self.ratings  = ratings
        self.users_df = users_df.reset_index(drop=True)
        self.foods_df = foods_df.reset_index(drop=True)

        # احسب تشابه الusersين (Cosine Similarity)
        print("  حساب تشابه الusersين...")
        self.user_sim = cosine_similarity(ratings)
        np.fill_diagonal(self.user_sim, 0)  # لا نقارن الusers بنفسه

        self.is_fitted = True
        print(f"  CF trained: {ratings.shape[0]} users × "
              f"{ratings.shape[1]} foods")
        return self

    def _get_user_vector(self, new_user: "UserProfile") -> np.ndarray:
        """
        حوّل ملف users جديد إلى متجه ميزات
        لإيجاد الusersين الأشبه به في cluster التدريب
        """
        feats = np.array([
            new_user.age / 100,
            new_user.bmi / 40,
            new_user.activity_level / 5,
            float(new_user.has_diabetes),
            float(new_user.has_bp),
            float(new_user.has_cholesterol),
            ["lose","maintain","gain","sport"].index(new_user.goal) / 3,
        ])
        return feats

    def _find_similar_users(self,
                             new_user_vec: np.ndarray) -> list:
        """
        إيجاد أقرب N users للusers الجديد
        نستخدم الميزات الديموغرافية بدلاً من التقييمات
        لأن الusers جديد ولا تقييمات له بعد (Cold Start)
        """
        # بناء مصفوفة ميزات الusersين المدرَّبين
        feat_cols = ["age","bmi","activity_level",
                     "has_diabetes","has_bp","has_cholesterol"]
        avail = [c for c in feat_cols if c in self.users_df.columns]

        if not avail:
            # fallback: خذ usersين عشوائيين
            return list(range(min(self.n_neighbors, len(self.users_df))))

        X = self.users_df[avail].fillna(0).values.astype(float)
        # طبّق نفس التطبيع
        X_norm  = self.feature_scaler.fit_transform(X)
        u_norm  = self.feature_scaler.transform(
            new_user_vec[:len(avail)].reshape(1,-1)
        )
        sims    = cosine_similarity(u_norm, X_norm)[0]
        top_idx = np.argsort(sims)[::-1][:self.n_neighbors]
        return top_idx.tolist()

    def recommend(self,
                  new_user: "UserProfile",
                  meal: str = None,
                  top_k: int = 10,
                  exclude_ids: list = None) -> pd.DataFrame:
        """
        اقتراح أطعمة للusers الجديد

        خطوات العمل:
        1. إيجاد الusersين المشابهين
        2. حساب متوسط تقييماتهم للأطعمة (مرجَّح بدرجة التشابه)
        3. إرجاع أعلى K foods لم يقيّمه الusers بعد، بعد فلترة صارمة
           حسب نوع الوجبة والحساسية وعدم الرغبة (كان مفقودًا سابقًا —
           CF لم يكن يستقبل meal إطلاقًا)
        """
        assert self.is_fitted

        user_vec     = self._get_user_vector(new_user)
        similar_idxs = self._find_similar_users(user_vec)

        # مصفوفة تقييمات الusersين المشابهين فقط
        sim_ratings = self.ratings[similar_idxs]   # (n_neighbors × n_foods)

        # متوسط مرجَّح (الأشبه له وزن أكبر)
        # نستخدم مجرد المتوسط هنا للبساطة
        avg_scores = sim_ratings.mean(axis=0)       # (n_foods,)

        # أضف الدرجات للـ DataFrame
        df = self.foods_df.copy()
        df["cf_score"] = avg_scores

        # ── فلترة صارمة موحّدة (نفس المستخدمة في CBF) ──────
        df = meal_rules.apply_hard_filters(df, new_user, meal=meal)
        if exclude_ids:
            df = df[~df["fdc_id"].isin(exclude_ids)]

        df = meal_rules.apply_soft_boosts(df, new_user, score_col="cf_score")

        result = (df.sort_values("cf_score", ascending=False)
                    .head(top_k)
                    .reset_index(drop=True))

        cols = ["fdc_id","name","category","food_group",
                "calories","protein","carbs","fat",
                "health_score","cf_score"]
        return result[[c for c in cols if c in result.columns]]

    def save(self, path=None):
        if path is None:
            path = MODEL_DIR / "cf_model.pkl"
        with open(path, "wb") as f:
            pickle.dump({
                "ratings":          self.ratings,
                "user_sim":         self.user_sim,
                "users_df":         self.users_df,
                "foods_df":         self.foods_df,
                "n_neighbors":      self.n_neighbors,
                "feature_scaler":   self.feature_scaler,
            }, f)
        print(f"  ✓ CF saved: {path}")

    @classmethod
    def load(cls, path=None) -> "CollaborativeFilter":
        if path is None:
            path = MODEL_DIR / "cf_model.pkl"
        with open(path, "rb") as f:
            data = pickle.load(f)
        obj                 = cls(n_neighbors=data["n_neighbors"])
        obj.ratings         = data["ratings"]
        obj.user_sim        = data["user_sim"]
        obj.users_df        = data["users_df"]
        obj.foods_df        = data["foods_df"]
        obj.feature_scaler  = data["feature_scaler"]
        obj.is_fitted       = True
        return obj


# ── Generating التقييمات الاصطناعية ────────────────────────────

def generate_ratings_matrix(users_df: pd.DataFrame,
                             foods_df: pd.DataFrame,
                             sparsity: float = 0.85,
                             seed: int = 42) -> np.ndarray:
    """
    Generating مصفوفة تقييمات اصطناعية واقعية

    المبدأ:
    - الusers ذو الـ BMI المرتفع وهدف الخسارة يُعطي
      تقييمات أعلى للأطعمة منخفضة الcalories/عالية الprotein
    - مريض السكري يُعطي تقييمات أعلى لـ diabetic_friendly
    - 85% من الخلايا فارغة (= 0) محاكاةً للواقع
    """
    rng      = np.random.default_rng(seed)
    n_users  = len(users_df)
    n_foods  = len(foods_df)
    ratings  = np.zeros((n_users, n_foods), dtype=np.float32)

    for i, user in users_df.iterrows():
        # كم foods يقيّمه هذا الusers
        n_rated = int(n_foods * (1 - sparsity))
        food_idxs = rng.choice(n_foods, size=n_rated, replace=False)

        for j in food_idxs:
            food  = foods_df.iloc[j]
            score = 3.0  # قيمة افتراضية

            # رفع الدرجة للأطعمة المناسبة للusers
            bmi  = user.get("bmi", 25)
            goal = user.get("goal", "maintain")

            if goal in ["lose"] and food["calories"] < 150:
                score += rng.uniform(0.5, 1.5)
            if goal in ["gain","sport"] and food.get("protein",0) > 15:
                score += rng.uniform(0.5, 2.0)
            if user.get("has_diabetes",False) and food.get("diabetic_friendly",False):
                score += rng.uniform(0.3, 1.0)
            if user.get("has_bp",False) and food.get("low_sodium",False):
                score += rng.uniform(0.2, 0.8)
            if food.get("health_score",50) > 70:
                score += rng.uniform(0, 0.5)

            # أضف ضوضاء عشوائية
            score += rng.normal(0, 0.3)
            ratings[i, j] = float(np.clip(score, 1, 5))

    return ratings


def plot_ratings_heatmap(ratings: np.ndarray):
    """رسم Heatmap للتقييمات (عينة)"""
    sample = ratings[:30, :40]    # عيّنة صغيرة للرسم
    fig, ax = plt.subplots(figsize=(13, 6))
    im = ax.imshow(sample, aspect="auto", cmap="YlOrRd",
                   vmin=0, vmax=5)
    plt.colorbar(im, ax=ax, label="التقييم (0-5)")
    ax.set_title("مصفوفة التقييمات (30 users × 40 foods) — الأصفر = غير مُقيَّم",
                 fontweight="bold")
    ax.set_xlabel("الfoods (رقم)")
    ax.set_ylabel("الusers (رقم)")
    path = CHARTS_DIR / "10_ratings_heatmap.png"
    plt.tight_layout()
    plt.savefig(path, dpi=140, bbox_inches="tight")
    plt.close()
    print(f"  ✓ Ratings heatmap saved: {path.name}")


# ── التشغيل الرئيسي ───────────────────────────────────────
if __name__ == "__main__":
    up_mod = _import_user_profiler()
    UserProfile = up_mod.UserProfile

    print("\n" + "="*52)
    print("  Collaborative Filtering (CF) Model")
    print("="*52)

    # 1. تحميل البيانات
    print("\n[1/5] Loading data...")
    users_path = SYNTHETIC_USERS_PATH
    foods_path = PROCESSED_FOODS_PATH
    if not users_path.exists():
        raise FileNotFoundError("شغّل أولاً: python 05_user_profiler.py")
    if not foods_path.exists():
        raise FileNotFoundError("شغّل أولاً: python 03_clean_data.py")

    users_df = pd.read_csv(users_path, encoding="utf-8-sig")
    foods_df = pd.read_csv(foods_path, encoding="utf-8-sig")
    print(f"  {len(users_df)} users | {len(foods_df)} foods")

    # 2. Generating مصفوفة التقييمات
    print("\n[2/5] Generating مصفوفة التقييمات الاصطناعية...")
    ratings = generate_ratings_matrix(users_df, foods_df, sparsity=0.85)
    density = (ratings > 0).sum() / ratings.size * 100
    print(f"  Matrix: {ratings.shape[0]} × {ratings.shape[1]}")
    print(f"  Rating density: {density:.1f}% (rest are zero)")
    plot_ratings_heatmap(ratings)

    # 3. تدريب النموذج
    print("\n[3/5] Training CF model...")
    cf = CollaborativeFilter(n_neighbors=20)
    cf.fit(ratings, users_df, foods_df)

    # 4. اختبار
    print("\n[4/5] Testing recommendations...")
    test_user = UserProfile(
        name="عمر", age=28, gender="male",
        weight=85, height=178, activity_level=3, goal="lose"
    )
    print(f"\n  الusers: {test_user.name}")
    recs = cf.recommend(test_user, top_k=7)
    print(f"  Top 7 recommendations:")
    for _, r in recs.iterrows():
        print(f"    • {r['name'][:35]:<37} "
              f"[CF: {r['cf_score']:.2f}] "
              f"{r['calories']:.0f}cal")

    # 5. حفظ
    print("\n[5/5] Saving model...")
    cf.save()
    print(f"\n  Next: python 09_hybrid_recommender.py")