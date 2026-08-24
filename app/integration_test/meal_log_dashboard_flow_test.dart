import 'package:dietary_app/core/api_client.dart';
import 'package:flutter/material.dart';
import 'package:dietary_app/main.dart' as app;
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

const _testEmail = String.fromEnvironment('INTEGRATION_TEST_EMAIL');
const _testPassword = String.fromEnvironment('INTEGRATION_TEST_PASSWORD');

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets(
    'user logs a recommended meal and Dashboard displays the updated daily count',
    (tester) async {
      if (_testEmail.isEmpty || _testPassword.isEmpty) {
        fail(
          'Provide INTEGRATION_TEST_EMAIL and INTEGRATION_TEST_PASSWORD via '
          '--dart-define. Use a dedicated test account with no meal logs today.',
        );
      }

      // Keep this flow independent from any previous device session.
      await ApiClient().clearToken();
      app.main();
      await tester.pumpAndSettle();

      // 1. Log in using a dedicated account on the isolated integration API.
      expect(find.text('دخول'), findsOneWidget);
      await tester.enterText(find.byType(TextFormField).at(0), _testEmail);
      await tester.enterText(find.byType(TextFormField).at(1), _testPassword);
      await tester.tap(find.text('دخول'));
      await tester.pumpAndSettle(const Duration(seconds: 8));

      // 2. A fresh test user must start with a truthful empty daily log.
      expect(find.text('متابعة اليوم'), findsOneWidget);
      expect(find.text('لا توجد وجبات مسجلة'), findsOneWidget);

      // 3. Open recommendations, confirm the user action, and save the meal log.
      await tester.tap(find.text('توصية وجبة'));
      await tester.pumpAndSettle(const Duration(seconds: 8));
      expect(find.text('توصيات الوجبات'), findsOneWidget);
      expect(find.text('سجّل كوجبة مأكولة').first, findsOneWidget);

      await tester.tap(find.text('سجّل كوجبة مأكولة').first);
      await tester.pumpAndSettle();
      expect(find.text('تسجيل وجبة'), findsOneWidget);
      await tester.tap(find.text('تسجيلها'));
      await tester.pump(const Duration(seconds: 2));
      expect(find.text('تمت إضافة الوجبة إلى سجل اليوم'), findsOneWidget);

      // 4. Return to Dashboard. The invalidated progress provider reloads the API data.
      await tester.pageBack();
      await tester.pumpAndSettle(const Duration(seconds: 5));
      expect(find.text('1 وجبات مسجلة'), findsOneWidget);
      expect(find.text('لا توجد وجبات مسجلة'), findsNothing);
    },
  );
}
