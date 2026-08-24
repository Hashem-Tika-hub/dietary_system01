import 'package:dietary_app/models/models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('MealRecommendation daily budget', () {
    test('parses an adjusted remaining-daily budget from the API', () {
      final recommendation = MealRecommendation.fromJson({
        'meal': 'dinner',
        'meal_label': 'Dinner',
        'target_calories': 300.0,
        'planned_target_calories': 600.0,
        'consumed_today_calories': 1700.0,
        'remaining_daily_calories': 300.0,
        'budget_adjusted': true,
        'daily_budget_exhausted': false,
        'recommendations': [],
      });

      expect(recommendation.targetCalories, 300.0);
      expect(recommendation.plannedTargetCalories, 600.0);
      expect(recommendation.consumedTodayCalories, 1700.0);
      expect(recommendation.remainingDailyCalories, 300.0);
      expect(recommendation.budgetAdjusted, isTrue);
      expect(recommendation.dailyBudgetExhausted, isFalse);
    });

    test('retains a truthful exhausted-budget state with no suggestions', () {
      final recommendation = MealRecommendation.fromJson({
        'meal': 'dinner',
        'meal_label': 'Dinner',
        'target_calories': 0.0,
        'planned_target_calories': 600.0,
        'consumed_today_calories': 2200.0,
        'remaining_daily_calories': 0.0,
        'budget_adjusted': true,
        'daily_budget_exhausted': true,
        'recommendations': [],
      });

      expect(recommendation.recommendations, isEmpty);
      expect(recommendation.targetCalories, 0.0);
      expect(recommendation.dailyBudgetExhausted, isTrue);
    });
  });
}
