// lib/models/models.dart
// ── All data models in one file for simplicity ───────────

// ══════════════════════════════════════════════════════════
//  USER
// ══════════════════════════════════════════════════════════
class UserModel {
  final int     id;
  final String  email;
  final String  name;
  final int     age;
  final String  gender;
  final double  weight;
  final double  height;
  final int     activityLevel;
  final String  goal;
  final bool    hasDiabetes;
  final bool    hasBp;
  final bool    hasCholesterol;
  final List<String> allergies;
  final List<String> dislikes;
  final List<String> favorites;
  final String  cuisineStyle;
  final bool    allowTreats;

  const UserModel({
    required this.id,
    required this.email,
    required this.name,
    required this.age,
    required this.gender,
    required this.weight,
    required this.height,
    required this.activityLevel,
    required this.goal,
    required this.hasDiabetes,
    required this.hasBp,
    required this.hasCholesterol,
    required this.allergies,
    this.dislikes = const [],
    this.favorites = const [],
    this.cuisineStyle = 'مزيج',
    this.allowTreats = false,
  });

  factory UserModel.fromJson(Map<String, dynamic> j) => UserModel(
    id:             j['id'] ?? 0,
    email:          j['email'] ?? '',
    name:           j['name'] ?? '',
    age:            j['age'] ?? 0,
    gender:         j['gender'] ?? 'male',
    weight:         (j['weight'] ?? 0).toDouble(),
    height:         (j['height'] ?? 0).toDouble(),
    activityLevel:  j['activity_level'] ?? 1,
    goal:           j['goal'] ?? 'maintain',
    hasDiabetes:    j['has_diabetes'] ?? false,
    hasBp:          j['has_bp'] ?? false,
    hasCholesterol: j['has_cholesterol'] ?? false,
    allergies:      List<String>.from(j['allergies'] ?? []),
    dislikes:       List<String>.from(j['dislikes'] ?? []),
    favorites:      List<String>.from(j['favorites'] ?? []),
    cuisineStyle:   j['cuisine_style'] ?? 'مزيج',
    allowTreats:    j['allow_treats'] ?? false,
  );

  double get bmi => weight / ((height / 100) * (height / 100));

  String get bmiCategory {
    if (bmi < 18.5) return 'نقص في الوزن';
    if (bmi < 25.0) return 'وزن طبيعي';
    if (bmi < 30.0) return 'زيادة في الوزن';
    return 'سمنة';
  }
}

// ══════════════════════════════════════════════════════════
//  NUTRITION TARGETS
// ══════════════════════════════════════════════════════════
class NutritionTargets {
  final double dailyCalories;
  final double proteinG;
  final double carbsG;
  final double fatG;
  final double bmi;
  final double bmr;
  final double tdee;
  final Map<String, MealTarget> mealTargets;

  const NutritionTargets({
    required this.dailyCalories,
    required this.proteinG,
    required this.carbsG,
    required this.fatG,
    required this.bmi,
    required this.bmr,
    required this.tdee,
    required this.mealTargets,
  });

  factory NutritionTargets.fromJson(Map<String, dynamic> j) =>
      NutritionTargets(
        dailyCalories: (j['daily_calories'] ?? 0).toDouble(),
        proteinG:      (j['protein_g'] ?? 0).toDouble(),
        carbsG:        (j['carbs_g'] ?? 0).toDouble(),
        fatG:          (j['fat_g'] ?? 0).toDouble(),
        bmi:           (j['bmi'] ?? 0).toDouble(),
        bmr:           (j['bmr'] ?? 0).toDouble(),
        tdee:          (j['tdee'] ?? 0).toDouble(),
        mealTargets: (j['meal_targets'] as Map<String, dynamic>?)?.map(
          (k, v) => MapEntry(k, MealTarget.fromJson(v)),
        ) ?? {},
      );
}

class MealTarget {
  final String label;
  final double calories;
  final double protein;
  final double carbs;
  final double fat;

  const MealTarget({
    required this.label,
    required this.calories,
    required this.protein,
    required this.carbs,
    required this.fat,
  });

  factory MealTarget.fromJson(Map<String, dynamic> j) => MealTarget(
    label:    j['label'] ?? '',
    calories: (j['calories'] ?? 0).toDouble(),
    protein:  (j['protein'] ?? 0).toDouble(),
    carbs:    (j['carbs'] ?? 0).toDouble(),
    fat:      (j['fat'] ?? 0).toDouble(),
  );
}

// ══════════════════════════════════════════════════════════
//  FOOD
// ══════════════════════════════════════════════════════════
class FoodItem {
  final String  fdcId;
  final String  name;
  final String  category;
  final String  foodGroup;
  final String  mealType;
  final double  calories;
  final double  protein;
  final double  carbs;
  final double  fat;
  final double  fiber;
  final double  healthScore;
  final bool    diabeticFriendly;
  final bool    lowSodium;

  const FoodItem({
    required this.fdcId,
    required this.name,
    required this.category,
    this.foodGroup = '',
    this.mealType = '',
    required this.calories,
    required this.protein,
    required this.carbs,
    required this.fat,
    required this.fiber,
    required this.healthScore,
    required this.diabeticFriendly,
    required this.lowSodium,
  });

  factory FoodItem.fromJson(Map<String, dynamic> j) => FoodItem(
    fdcId:           j['fdc_id'] ?? '',
    name:            j['name'] ?? '',
    category:        j['category'] ?? '',
    foodGroup:       j['food_group'] ?? '',
    mealType:        j['meal_type'] ?? '',
    calories:        (j['calories'] ?? 0).toDouble(),
    protein:         (j['protein'] ?? 0).toDouble(),
    carbs:           (j['carbs'] ?? 0).toDouble(),
    fat:             (j['fat'] ?? 0).toDouble(),
    fiber:           (j['fiber'] ?? 0).toDouble(),
    healthScore:     (j['health_score'] ?? 0).toDouble(),
    diabeticFriendly: j['diabetic_friendly'] ?? false,
    lowSodium:        j['low_sodium'] ?? false,
  );
}

// ══════════════════════════════════════════════════════════
//  RECOMMENDATION
// ══════════════════════════════════════════════════════════
class FoodRecommendation {
  final String  fdcId;
  final String  name;
  final String  category;
  final String  foodGroup;
  final String  slot;
  final double  calories;
  final double  protein;
  final double  carbs;
  final double  fat;
  final double  portionG;
  final double  hybridScore;
  final int?    foodCluster;
  final String  recommendationReason;
  final List<String> recommendationReasons;
  final bool    diversityApplied;

  const FoodRecommendation({
    required this.fdcId,
    required this.name,
    required this.category,
    this.foodGroup = '',
    this.slot = '',
    required this.calories,
    required this.protein,
    required this.carbs,
    required this.fat,
    required this.portionG,
    required this.hybridScore,
    this.foodCluster,
    this.recommendationReason = '',
    this.recommendationReasons = const [],
    this.diversityApplied = false,
  });

  factory FoodRecommendation.fromJson(Map<String, dynamic> j) =>
      FoodRecommendation(
        fdcId:       j['fdc_id'] ?? '',
        name:        j['name'] ?? '',
        category:    j['category'] ?? '',
        foodGroup:   j['food_group'] ?? '',
        slot:        j['slot'] ?? '',
        calories:    (j['calories'] ?? 0).toDouble(),
        protein:     (j['protein'] ?? 0).toDouble(),
        carbs:       (j['carbs'] ?? 0).toDouble(),
        fat:         (j['fat'] ?? 0).toDouble(),
        portionG:    (j['portion_g'] ?? 100).toDouble(),
        hybridScore: (j['hybrid_score'] ?? 0).toDouble(),
        foodCluster: j['food_cluster'] == null
            ? null
            : (j['food_cluster'] as num).toInt(),
        recommendationReason: j['recommendation_reason'] ?? '',
        recommendationReasons: (j['recommendation_reasons'] as List? ?? [])
            .map((e) => e.toString())
            .toList(),
        diversityApplied: j['diversity_applied'] ?? false,
      );
}

class MealRecommendation {
  final String   meal;
  final String   mealLabel;
  final double   targetCalories;
  final List<FoodRecommendation> recommendations;
  final String rankingBasis;
  final double contentWeight;
  final double collaborativeWeight;

  const MealRecommendation({
    required this.meal,
    required this.mealLabel,
    required this.targetCalories,
    required this.recommendations,
    this.rankingBasis = 'content_based',
    this.contentWeight = 1.0,
    this.collaborativeWeight = 0.0,
  });

  factory MealRecommendation.fromJson(Map<String, dynamic> j) =>
      MealRecommendation(
        meal:           j['meal'] ?? '',
        mealLabel:      j['meal_label'] ?? '',
        targetCalories: (j['target_calories'] ?? 0).toDouble(),
        recommendations: (j['recommendations'] as List? ?? [])
            .map((e) => FoodRecommendation.fromJson(e))
            .toList(),
        rankingBasis: j['ranking_basis'] ?? 'content_based',
        contentWeight: (j['content_weight'] ?? 1).toDouble(),
        collaborativeWeight: (j['collaborative_weight'] ?? 0).toDouble(),
      );

class CollaborativeReadiness {
  final bool ready;
  final String reason;
  final int interactionCount;
  final int uniqueUsers;
  final int uniqueFoods;
  final int targetUserInteractions;

  const CollaborativeReadiness({
    required this.ready,
    required this.reason,
    required this.interactionCount,
    required this.uniqueUsers,
    required this.uniqueFoods,
    required this.targetUserInteractions,
  });

  factory CollaborativeReadiness.fromJson(Map<String, dynamic> j) =>
      CollaborativeReadiness(
        ready: j['ready'] ?? false,
        reason: j['reason'] ?? '',
        interactionCount: j['interaction_count'] ?? 0,
        uniqueUsers: j['unique_users'] ?? 0,
        uniqueFoods: j['unique_foods'] ?? 0,
        targetUserInteractions: j['target_user_interactions'] ?? 0,
      );
}
}