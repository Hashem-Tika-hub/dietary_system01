// lib/services/auth_service.dart

import '../core/api_client.dart';
import '../models/models.dart';

class AuthService {
  final _client = ApiClient();

  // ── Register ──────────────────────────────────────────
  Future<String> register(Map<String, dynamic> data) async {
    final res = await _client.dio.post('/auth/register', data: data);
    final token = res.data['access_token'] as String;
    await _client.saveToken(token);
    return token;
  }

  // ── Login ─────────────────────────────────────────────
  Future<String> login(String email, String password) async {
    final res = await _client.dio.post('/auth/login', data: {
      'email':    email,
      'password': password,
    });
    final token = res.data['access_token'] as String;
    await _client.saveToken(token);
    return token;
  }

  // ── Logout ────────────────────────────────────────────
  Future<void> logout() => _client.clearToken();

  // ── Current user ──────────────────────────────────────
  Future<UserModel> getMe() async {
    final res = await _client.dio.get('/auth/me');
    return UserModel.fromJson(res.data);
  }

  // ── Update profile ────────────────────────────────────
  Future<UserModel> updateProfile(Map<String, dynamic> data) async {
    final res = await _client.dio.put('/users/profile', data: data);
    return UserModel.fromJson(res.data);
  }

  // ── Nutrition targets ─────────────────────────────────
  Future<NutritionTargets> getNutritionTargets() async {
    final res = await _client.dio.get('/users/nutrition-targets');
    return NutritionTargets.fromJson(res.data);
  }

  Future<bool> isLoggedIn() => _client.hasToken();
}