// lib/main.dart
// ── App entry point + routing ─────────────────────────────

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'core/theme.dart';
import 'providers/providers.dart';

import 'screens/splash_screen.dart';
import 'screens/auth/login_screen.dart';
import 'screens/auth/register_screen.dart';
import 'screens/home/home_screen.dart';
import 'screens/recommendations/recommendations_screen.dart';
import 'screens/recommendations/weekly_plan_screen.dart';
import 'screens/profile/profile_screen.dart';
import 'screens/foods/food_search_screen.dart';

// ── Router ────────────────────────────────────────────────
final _router = GoRouter(
  initialLocation: '/splash',
  redirect: (context, state) {
    // No redirect needed — SplashScreen handles auth check
    return null;
  },
  routes: [
    GoRoute(
      path:    '/splash',
      builder: (_, __) => const SplashScreen(),
    ),
    GoRoute(
      path:    '/login',
      builder: (_, __) => const LoginScreen(),
    ),
    GoRoute(
      path:    '/register',
      builder: (_, __) => const RegisterScreen(),
    ),
    GoRoute(
      path:    '/home',
      builder: (_, __) => const HomeScreen(),
    ),
    GoRoute(
      path:    '/recommendations',
      builder: (_, __) => const RecommendationsScreen(),
    ),
    GoRoute(
      path:    '/weekly',
      builder: (_, __) => const WeeklyPlanScreen(),
    ),
    GoRoute(
      path:    '/profile',
      builder: (_, __) => const ProfileScreen(),
    ),
    GoRoute(
      path:    '/foods',
      builder: (_, __) => const FoodSearchScreen(),
    ),
  ],
  errorBuilder: (context, state) => Scaffold(
    body: Center(
      child: Text('Page not found: ${state.uri}'),
    ),
  ),
);

// ── Main ──────────────────────────────────────────────────
void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(
    // ProviderScope enables Riverpod throughout the app
    const ProviderScope(
      child: DietaryApp(),
    ),
  );
}

class DietaryApp extends ConsumerWidget {
  const DietaryApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp.router(
      title:            'نظام التوصية الغذائية',
      theme:            AppTheme.light,
      routerConfig:     _router,
      debugShowCheckedModeBanner: false,

      // RTL layout for Arabic
      builder: (context, child) => Directionality(
        textDirection: TextDirection.rtl,
        child: child!,
      ),
    );
  }
}
