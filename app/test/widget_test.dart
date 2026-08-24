import 'package:dietary_app/models/models.dart';
import 'package:dietary_app/providers/providers.dart';
import 'package:dietary_app/screens/home/home_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

class _DashboardAuthNotifier extends AuthNotifier {
  _DashboardAuthNotifier(UserModel user) : super() {
    state = AuthState(user: user);
  }
}

class _RouteProbe extends StatelessWidget {
  final String route;
  const _RouteProbe(this.route);

  @override
  Widget build(BuildContext context) => Scaffold(
        body: Center(child: Text('ROUTE:$route')),
      );
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

GoRouter _dashboardRouter() => GoRouter(
      initialLocation: '/home',
      routes: [
        GoRoute(path: '/home', builder: (_, __) => const HomeScreen()),
        GoRoute(
          path: '/recommendations',
          builder: (_, __) => const _RouteProbe('/recommendations'),
        ),
        GoRoute(path: '/weekly', builder: (_, __) => const _RouteProbe('/weekly')),
        GoRoute(path: '/foods', builder: (_, __) => const _RouteProbe('/foods')),
        GoRoute(path: '/profile', builder: (_, __) => const _RouteProbe('/profile')),
      ],
    );

Widget _dashboardUnderTest(
  DailyNutritionProgress progress, {
  GoRouter? router,
  int Function()? onTargetsLoad,
  int Function()? onProgressLoad,
  int Function()? onReadinessLoad,
}) {
  final dashboardRouter = router ?? _dashboardRouter();
  return ProviderScope(
    overrides: [
      authProvider.overrideWith((ref) => _DashboardAuthNotifier(_user)),
      nutritionTargetsProvider.overrideWith((ref) async {
        onTargetsLoad?.call();
        return _targets;
      }),
      dailyNutritionProgressProvider.overrideWith((ref) async {
        onProgressLoad?.call();
        return progress;
      }),
      collaborativeReadinessProvider.overrideWith((ref) async {
        onReadinessLoad?.call();
        return _coldStart;
      }),
    ],
    child: MaterialApp.router(
      routerConfig: dashboardRouter,
      builder: (context, child) => Directionality(
        textDirection: TextDirection.rtl,
        child: child!,
      ),
    ),
  );
}

Future<void> _scrollDashboardUntilVisible(
  WidgetTester tester,
  Finder finder,
) async {
  await tester.scrollUntilVisible(
    finder,
    240,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
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
    await _scrollDashboardUntilVisible(tester, find.text('توصية وجبة'));
    expect(find.text('توصية وجبة'), findsOneWidget);
    await _scrollDashboardUntilVisible(tester, find.text('خطة الأسبوع'));
    expect(find.text('خطة الأسبوع').first, findsOneWidget);
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

  testWidgets('Dashboard recommendation actions navigate to recommendations',
      (WidgetTester tester) async {
    await tester.pumpWidget(_dashboardUnderTest(_progress(loggedMeals: 2)));
    await tester.pumpAndSettle();

    await _scrollDashboardUntilVisible(tester, find.text('توصية وجبة'));
    await tester.tap(find.text('توصية وجبة'));
    await tester.pumpAndSettle();

    expect(find.text('ROUTE:/recommendations'), findsOneWidget);
  });

  testWidgets('Dashboard weekly and food actions navigate to their routes',
      (WidgetTester tester) async {
    final router = _dashboardRouter();
    await tester.pumpWidget(_dashboardUnderTest(_progress(loggedMeals: 2), router: router));
    await tester.pumpAndSettle();

    await _scrollDashboardUntilVisible(tester, find.text('خطة الأسبوع'));
    await tester.tap(find.text('خطة الأسبوع').first);
    await tester.pumpAndSettle();
    expect(find.text('ROUTE:/weekly'), findsOneWidget);

    router.go('/home');
    await tester.pumpAndSettle();
    await _scrollDashboardUntilVisible(tester, find.text('بحث الأطعمة'));
    await tester.tap(find.text('بحث الأطعمة'));
    await tester.pumpAndSettle();
    expect(find.text('ROUTE:/foods'), findsOneWidget);
  });

  testWidgets('Dashboard profile action navigates to the profile route',
      (WidgetTester tester) async {
    await tester.pumpWidget(_dashboardUnderTest(_progress(loggedMeals: 2)));
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('الملف الشخصي'));
    await tester.pumpAndSettle();

    expect(find.text('ROUTE:/profile'), findsOneWidget);
  });

  testWidgets('pull to refresh reloads all Dashboard data sources',
      (WidgetTester tester) async {
    var targetLoads = 0;
    var progressLoads = 0;
    var readinessLoads = 0;

    await tester.pumpWidget(
      _dashboardUnderTest(
        _progress(loggedMeals: 2),
        onTargetsLoad: () => targetLoads += 1,
        onProgressLoad: () => progressLoads += 1,
        onReadinessLoad: () => readinessLoads += 1,
      ),
    );
    await tester.pumpAndSettle();
    expect((targetLoads, progressLoads, readinessLoads), (1, 1, 1));

    await tester.drag(find.byType(ListView), const Offset(0, 300));
    await tester.pump();
    await tester.pumpAndSettle();

    expect(targetLoads, greaterThanOrEqualTo(2));
    expect(progressLoads, greaterThanOrEqualTo(2));
    expect(readinessLoads, greaterThanOrEqualTo(2));
  });
}
