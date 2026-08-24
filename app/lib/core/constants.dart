// lib/core/constants.dart
// ── Colors, API URL, and app-wide constants ──────────────

import 'package:flutter/material.dart';

class AppColors {
  // Brand palette
  static const primary    = Color(0xFF2A78D6);
  static const secondary  = Color(0xFF1BAF7A);
  static const accent     = Color(0xFFEDA100);
  static const danger     = Color(0xFFD85A30);
  static const purple     = Color(0xFF7F77DD);

  // Neutrals
  static const background = Color(0xFFF5F6FA);
  static const surface    = Color(0xFFFFFFFF);
  static const textDark   = Color(0xFF1A1A2E);
  static const textGrey   = Color(0xFF6B7280);
  static const border     = Color(0xFFE5E7EB);

  // Meal type colors
  static const breakfast  = Color(0xFFEDA100);
  static const lunch      = Color(0xFF2A78D6);
  static const dinner     = Color(0xFF7F77DD);
  static const snack      = Color(0xFF1BAF7A);
}

class AppConfig {
  // ── عنوان الـ API يتحدد تلقائيًا حسب المنصة ──────────────
  // كان مثبَّتًا على 10.0.2.2 (خاص بمحاكي أندرويد فقط) — هذا العنوان
  // غير قابل للوصول إطلاقًا من متصفح (Flutter Web)، وهو على الأغلب
  // سبب خطأ "DioException connection error / XMLHttpRequest onError"
  // لو تختبر بـ `flutter run -d chrome`.
  //
  // يستخدم APK عنوان الإنتاج الافتراضي الحالي، ويمكن بناء نسخة V2 بعنوان
  // مختلف من دون تعديل الشفرة، مثال:
  // flutter build apk --release --dart-define=API_BASE_URL=https://api-v2.example.com
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://dietarysystem-production.up.railway.app',
  );

  // Request timeout
  static const int timeoutSeconds = 15;

  // Meal types
  static const meals = ['breakfast', 'lunch', 'dinner', 'snack'];
  static const mealsAr = {
    'breakfast': 'الفطور',
    'lunch':     'الغداء',
    'dinner':    'العشاء',
    'snack':     'وجبة خفيفة',
  };

  // Activity levels
  static const activityLabels = [
    'خامل (لا رياضة)',
    'نشاط خفيف (1-3 أيام)',
    'نشاط متوسط (3-5 أيام)',
    'نشاط عالٍ (6-7 أيام)',
    'نشاط مكثّف (رياضي)',
  ];

  // Goals
  static const goalLabels = {
    'lose':     'خسارة وزن',
    'maintain': 'الحفاظ على الوزن',
    'gain':     'زيادة الكتلة',
    'sport':    'أداء رياضي',
  };

  // تفضيلات الطعام (dislikes/favorites) — نفس مفاتيح
  // meal_rules.FOOD_GROUP_TAGS بملف Python تمامًا، حتى تُفهَم بالـ API
  static const foodPrefLabels = {
    'بحريات':     'المأكولات البحرية والأسماك',
    'دواجن':      'الدجاج والدواجن',
    'لحوم_حمراء': 'اللحوم الحمراء',
    'بيض':        'البيض',
    'ألبان':      'الألبان',
    'مكسرات':     'المكسرات',
    'بقوليات':    'البقوليات (عدس، فول، حمص...)',
    'حلويات':     'الحلويات',
  };

  // الحساسيات التي يفهمها محرك القواعد من خلال رموز الكتالوج أو التوافق القديم.
  static const allergyLabels = {
    'حليب': 'الحليب ومشتقاته',
    'بيض': 'البيض',
    'مكسرات': 'المكسرات',
    'فول سوداني': 'الفول السوداني',
    'قمح': 'القمح',
    'جلوتين': 'الجلوتين',
  };

  // الطابع المفضّل للوجبات
  static const cuisineStyleLabels = {
    'تقليدي': 'تقليدي (أطباق محلية وعربية)',
    'عالمي':  'عالمي (أطباق أبسط وأعم)',
    'مزيج':   'مزيج من الاثنين',
  };
}
