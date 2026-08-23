// lib/services/recommendation_service.dart

import '../core/api_client.dart';
import '../models/models.dart';

class RecommendationService {
  final _client = ApiClient();

  // ── Single meal recommendations ───────────────────────
  Future<MealRecommendation> getMealRecommendations(
      String meal, {int topK = 5}) async {
    final res = await _client.dio.post(
      '/recommendations/meal',
      data: {'meal': meal, 'top_k': topK},
    );
    return MealRecommendation.fromJson(res.data);
  }

  // ── Weekly plan ───────────────────────────────────────
  // يرجع الخطة المحفوظة الحالية (يولّد مرة واحدة فقط لو ما فيه خطة بعد)
  // — لا يولّد خطة جديدة عشوائية في كل مرة تُفتح الشاشة
  Future<Map<String, dynamic>> getCurrentWeeklyPlan() async {
    final res = await _client.dio.get('/recommendations/weekly');
    return res.data as Map<String, dynamic>;
  }

  // توليد خطة جديدة كليًا صراحة (زر "خطة جديدة")
  Future<Map<String, dynamic>> regenerateWeeklyPlan() async {
    final res = await _client.dio.post('/recommendations/weekly');
    return res.data as Map<String, dynamic>;
  }

  // بدائل ممكنة لصنف معيّن داخل خطة محفوظة
  Future<List<FoodRecommendation>> getSwapAlternatives({
    required int planId, required String day,
    required String meal, required String slot,
  }) async {
    final res = await _client.dio.post('/recommendations/weekly/alternatives', data: {
      'plan_id': planId, 'day': day, 'meal': meal, 'slot': slot,
    });
    return (res.data as List).map((e) => FoodRecommendation.fromJson(e)).toList();
  }

  // تنفيذ الاستبدال وحفظه
  Future<Map<String, dynamic>> swapMealItem({
    required int planId, required String day, required String meal,
    required String slot, required String newFdcId,
  }) async {
    final res = await _client.dio.post('/recommendations/weekly/swap', data: {
      'plan_id': planId, 'day': day, 'meal': meal, 'slot': slot,
      'new_fdc_id': newFdcId,
    });
    return res.data as Map<String, dynamic>;
  }

  // ── Logged meals ──────────────────────────────────────
  Future<void> createMealLog({
    required String mealType,
    required String foodName,
    required String fdcId,
    required double portionG,
    required double calories,
    required double protein,
    required double carbs,
    required double fat,
  }) async {
    await _client.dio.post('/users/meal-logs', data: {
      'meal_type': mealType,
      'food_name': foodName,
      'fdc_id': fdcId,
      'portion_g': portionG,
      'calories': calories,
      'protein': protein,
      'carbs': carbs,
      'fat': fat,
    });
  }

  // ── Daily logged-meal progress for Dashboard ───────────
  Future<DailyNutritionProgress> getDailyNutritionProgress({
    DateTime? day,
  }) async {
    final params = <String, dynamic>{};
    if (day != null) {
      final yyyy = day.year.toString().padLeft(4, '0');
      final mm = day.month.toString().padLeft(2, '0');
      final dd = day.day.toString().padLeft(2, '0');
      params['day'] = '$yyyy-$mm-$dd';
    }
    final res = await _client.dio.get(
      '/users/meal-logs/daily-progress',
      queryParameters: params,
    );
    return DailyNutritionProgress.fromJson(res.data as Map<String, dynamic>);
  }

  // ── Explicit feedback and collaborative-readiness ──────
  Future<void> submitFoodFeedback({
    required String fdcId,
    required String eventType,
  }) async {
    await _client.dio.post('/users/food-feedback', data: {
      'fdc_id': fdcId,
      'event_type': eventType,
    });
  }

  Future<CollaborativeReadiness> getCollaborativeReadiness() async {
    final res = await _client.dio.get('/users/food-feedback/readiness');
    return CollaborativeReadiness.fromJson(res.data as Map<String, dynamic>);
  }

  // ── History ───────────────────────────────────────────
  Future<List<dynamic>> getHistory() async {
    final res = await _client.dio.get('/recommendations/history');
    return res.data as List;
  }
}

// ── Food search service ───────────────────────────────────
class FoodService {
  final _client = ApiClient();

  Future<List<FoodItem>> searchFoods({
    String?  query,
    String?  category,
    double?  maxCalories,
    double?  minProtein,
    bool?    diabeticFriendly,
    int      limit  = 20,
    int      offset = 0,
  }) async {
    final params = <String, dynamic>{
      'limit':  limit,
      'offset': offset,
    };
    if (query           != null) params['q']                 = query;
    if (category        != null) params['category']          = category;
    if (maxCalories     != null) params['max_calories']      = maxCalories;
    if (minProtein      != null) params['min_protein']       = minProtein;
    if (diabeticFriendly != null) params['diabetic_friendly'] = diabeticFriendly;

    final res = await _client.dio.get('/foods', queryParameters: params);
    return (res.data['foods'] as List)
        .map((e) => FoodItem.fromJson(e))
        .toList();
  }
}