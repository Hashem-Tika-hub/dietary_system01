import 'package:dietary_app/models/models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('DailyNutritionProgress', () {
    test('parses API values and preserves remaining calories', () {
      final progress = DailyNutritionProgress.fromJson({
        'date': '2026-08-23',
        'logged_meals': 2,
        'calories': {
          'target': 2100.0,
          'consumed': 850.0,
          'remaining': 1250.0,
          'progress_ratio': 850 / 2100,
        },
        'protein': {
          'target': 130.0,
          'consumed': 55.0,
          'remaining': 75.0,
          'progress_ratio': 55 / 130,
        },
        'carbs': {
          'target': 260.0,
          'consumed': 95.0,
          'remaining': 165.0,
          'progress_ratio': 95 / 260,
        },
        'fat': {
          'target': 70.0,
          'consumed': 26.0,
          'remaining': 44.0,
          'progress_ratio': 26 / 70,
        },
      });

      expect(progress.date, DateTime(2026, 8, 23));
      expect(progress.loggedMeals, 2);
      expect(progress.calories.consumed, 850.0);
      expect(progress.calories.remaining, 1250.0);
      expect(progress.protein.remaining, 75.0);
      expect(progress.calories.isOverTarget, isFalse);
      expect(progress.calories.clampedProgress, closeTo(850 / 2100, 0.0001));
    });

    test('clamps display progress while retaining a real over-target state', () {
      const calories = NutrientProgress(
        target: 2000,
        consumed: 2300,
        remaining: -300,
        progressRatio: 1.15,
      );

      expect(calories.isOverTarget, isTrue);
      expect(calories.clampedProgress, 1.0);
      expect(calories.remaining, -300.0);
    });
  });
}
