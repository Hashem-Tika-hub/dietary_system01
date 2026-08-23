import 'package:dietary_app/models/models.dart';
import 'package:dietary_app/providers/providers.dart';
import 'package:dietary_app/screens/home/home_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class _DashboardAuthNotifier extends AuthNotifier {
  _DashboardAuthNotifier(UserModel user) : super() {
    state = AuthState(user: user);
  }
}

const _user = UserModel(
  id: 1,
  email: 'dashboard@example.com',
  name: 'هاشم تيكا',
  age: 25,
  gender: 'male',
  weight: 75,
  height: 175,
  activityLevel: 3,
  goal: 'maintain',
  hasDiabetes: false,
  hasBp: false,
  hasCholesterol: false,
  allergies: [],
);

const _targets = NutritionTargets(
  dailyCalories: 2100,
  proteinG: 130,
  carbsG: 260,
  fatG: 70,
  bmi: 24.5,
  bmr: 1700,
  tdee: 2100,
  mealTargets: {},
);

const _coldStart = CollaborativeReadiness(
  ready: false,
  reason: 'يلزم مزيد من التفاعلات الصريحة',
  interactionCount: 2,
  uniqueUsers: 1,
  uniqueFoods: 2,
  targetUserInteractions: 10,
);

DailyNutritionProgress _progress({required int loggedMeals}) {
  return DailyNutritionProgress(
    date: DateTime(2026, 8, 23),
    loggedMeals: loggedMeals,
    calories: NutrientProgress(
      target: 2100,
      consumed: loggedMeals == 0 ? 0 : 850,
      remaining: loggedMeals == 0 ? 2100 : 1250,
      progressRatio: loggedMeals == 0 ? 0 : 850 / 2100,
    ),
    protein: NutrientProgress(
      target: 130,
      consumed: loggedMeals == 0 ? 0 : 55,
      remaining: loggedMeals == 0 ? 130 : 75,
      progressRatio: loggedMeals == 0 ? 0 : 55 / 130,
    ),
    carbs: NutrientProgress(
      target: 260,
      consumed: loggedMeals == 0 ? 0 : 95,
      remaining: loggedMeals == 0 ? 260 : 165,
      progressRatio: loggedMeals == 0 ? 0 : 95 / 260,
    ),
    fat: NutrientProgress(
      target: 70,
      consumed: loggedMeals == 0 ? 0 : 26,
      remaining: loggedMeals == 0 ? 70 : 44,
      progressRatio: loggedMeals == 0 ? 0 : 26 / 70,
    ),
  );
}

Widget _dashboardUnderTest(DailyNutritionProgress progress) {
  return ProviderScope(
    overrides: [
      authProvider.overrideWith((ref) => _DashboardAuthNotifier(_user)),
      nutritionTargetsProvider.overrideWith((ref) async => _targets),
      dailyNutritionProgressProvider.overrideWith((ref) async => progress),
      collaborativeReadinessProvider.overrideWith((ref) async => _coldStart),
    ],
    child: const MaterialApp(home: HomeScreen()),
  );
}

void main() {
  testWidgets('Dashboard shows logged calories, target, remaining value and actions',
      (WidgetTester tester) async {
    await tester.pumpWidget(_dashboardUnderTest(_progress(loggedMeals: 2)));
    await tester.pumpAndSettle();

    expect(find.text('أهلاً، هاشم'), findsOneWidget);
    expect(find.text('متابعة اليوم'), findsOneWidget);
    expect(find.text('2 وجبات مسجلة'), findsOneWidget);
    expect(find.text('850 / 2100 كيلوكالوري'), findsOneWidget);
    expect(find.text('متبقٍ 1250 كيلوكالوري'), findsOneWidget);
    expect(find.text('55 / 130g'), findsOneWidget);
    expect(find.text('تخصيصك يتطور مع تفاعلك'), findsOneWidget);
    expect(find.text('توصية وجبة'), findsOneWidget);
    expect(find.text('خطة الأسبوع'), findsOneWidget);
    expect(find.byType(LinearProgressIndicator), findsOneWidget);
  });

  testWidgets('Dashboard truthfully renders the empty daily-log state',
      (WidgetTester tester) async {
    await tester.pumpWidget(_dashboardUnderTest(_progress(loggedMeals: 0)));
    await tester.pumpAndSettle();

    expect(find.text('لا توجد وجبات مسجلة'), findsOneWidget);
    expect(find.text('0 / 2100 كيلوكالوري'), findsOneWidget);
    expect(
      find.text('سيظهر التقدم بعد إضافة وجبة إلى سجل وجباتك الفعلي.'),
      findsOneWidget,
    );
    expect(find.text('استكشف وجبة لتسجيلها'), findsOneWidget);
  });
}
