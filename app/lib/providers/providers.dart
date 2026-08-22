// lib/providers/providers.dart
// ── All Riverpod providers in one file ───────────────────

import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/models.dart';
import '../services/auth_service.dart';
import '../services/recommendation_service.dart';
import '../core/api_client.dart' show extractError;

// ══════════════════════════════════════════════════════════
//  AUTH STATE
// ══════════════════════════════════════════════════════════
class AuthState {
  final UserModel?  user;
  final bool        isLoading;
  final String?     error;

  const AuthState({this.user, this.isLoading = false, this.error});

  bool get isLoggedIn => user != null;

  AuthState copyWith({UserModel? user, bool? isLoading, String? error}) =>
      AuthState(
        user:      user      ?? this.user,
        isLoading: isLoading ?? this.isLoading,
        error:     error,
      );
}

class AuthNotifier extends StateNotifier<AuthState> {
  final AuthService _service = AuthService();

  AuthNotifier() : super(const AuthState());

  Future<void> init() async {
    if (await _service.isLoggedIn()) {
      try {
        final user = await _service.getMe();
        state = AuthState(user: user);
      } catch (_) {
        await _service.logout();
      }
    }
  }

  Future<bool> login(String email, String password) async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      await _service.login(email, password);
      final user = await _service.getMe();
      state = AuthState(user: user);
      return true;
    } catch (e) {
      state = state.copyWith(isLoading: false, error: extractError(e));
      return false;
    }
  }

  Future<bool> register(Map<String, dynamic> data) async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      await _service.register(data);
      final user = await _service.getMe();
      state = AuthState(user: user);
      return true;
    } catch (e) {
      state = state.copyWith(isLoading: false, error: extractError(e));
      return false;
    }
  }

  Future<void> logout() async {
    await _service.logout();
    state = const AuthState();
  }

  Future<bool> updateProfile(Map<String, dynamic> data) async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final user = await _service.updateProfile(data);
      state = AuthState(user: user);
      return true;
    } catch (e) {
      state = state.copyWith(isLoading: false, error: extractError(e));
      return false;
    }
  }
}

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>(
  (ref) => AuthNotifier(),
);

// ══════════════════════════════════════════════════════════
//  NUTRITION TARGETS
// ══════════════════════════════════════════════════════════
final nutritionTargetsProvider =
    FutureProvider<NutritionTargets>((ref) async {
  final auth = ref.watch(authProvider);
  if (!auth.isLoggedIn) throw Exception('Not logged in');
  return AuthService().getNutritionTargets();
});

// ══════════════════════════════════════════════════════════
//  MEAL RECOMMENDATIONS
// ══════════════════════════════════════════════════════════
final selectedMealProvider = StateProvider<String>((ref) => 'lunch');

final mealRecommendationsProvider =
    FutureProvider.family<MealRecommendation, String>((ref, meal) async {
  final auth = ref.watch(authProvider);
  if (!auth.isLoggedIn) throw Exception('Not logged in');
  return RecommendationService().getMealRecommendations(meal, topK: 5);
});

// ══════════════════════════════════════════════════════════
//  EXPLICIT FEEDBACK AND CF READINESS
// ══════════════════════════════════════════════════════════
final collaborativeReadinessProvider =
    FutureProvider<CollaborativeReadiness>((ref) async {
  final auth = ref.watch(authProvider);
  if (!auth.isLoggedIn) throw Exception('Not logged in');
  return RecommendationService().getCollaborativeReadiness();
});

class FoodFeedbackNotifier extends StateNotifier<AsyncValue<void>> {
  FoodFeedbackNotifier() : super(const AsyncValue.data(null));

  Future<bool> submit({
    required String fdcId,
    required String eventType,
  }) async {
    state = const AsyncValue.loading();
    try {
      await RecommendationService().submitFoodFeedback(
        fdcId: fdcId,
        eventType: eventType,
      );
      state = const AsyncValue.data(null);
      return true;
    } catch (error, stackTrace) {
      state = AsyncValue.error(error, stackTrace);
      return false;
    }
  }
}

final foodFeedbackProvider =
    StateNotifierProvider<FoodFeedbackNotifier, AsyncValue<void>>(
  (ref) => FoodFeedbackNotifier(),
);

// ══════════════════════════════════════════════════════════
//  WEEKLY PLAN
// ══════════════════════════════════════════════════════════
class WeeklyPlanNotifier extends StateNotifier<AsyncValue<Map<String, dynamic>>> {
  WeeklyPlanNotifier() : super(const AsyncValue.loading());

  // يحمّل الخطة المحفوظة الحالية (يولّد مرة واحدة فقط أول استخدام) —
  // هذا ما يجب استدعاؤه عند دخول الشاشة، لا generate()
  Future<void> loadCurrent() async {
    state = const AsyncValue.loading();
    try {
      final plan = await RecommendationService().getCurrentWeeklyPlan();
      state = AsyncValue.data(plan);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }

  // توليد خطة جديدة كليًا صراحة (زر "خطة جديدة" فقط)
  Future<void> regenerate() async {
    state = const AsyncValue.loading();
    try {
      final plan = await RecommendationService().regenerateWeeklyPlan();
      state = AsyncValue.data(plan);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }

  // استبدال صنف واحد داخل الخطة الحالية وتحديث الحالة محليًا فورًا
  Future<bool> swapItem({
    required String day, required String meal, required String slot,
    required String newFdcId,
  }) async {
    final current = state.value;
    if (current == null) return false;
    try {
      final updated = await RecommendationService().swapMealItem(
        planId: current['id'], day: day, meal: meal, slot: slot,
        newFdcId: newFdcId,
      );
      state = AsyncValue.data(updated);
      return true;
    } catch (_) {
      return false;
    }
  }
}

final weeklyPlanProvider =
    StateNotifierProvider<WeeklyPlanNotifier, AsyncValue<Map<String, dynamic>>>(
  (ref) => WeeklyPlanNotifier(),
);