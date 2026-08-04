// lib/core/api_client.dart
// ── Dio HTTP client — auto-injects JWT token ─────────────

import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'constants.dart';

class ApiClient {
  static final ApiClient _instance = ApiClient._internal();
  factory ApiClient() => _instance;

  late final Dio _dio;
  final _storage = const FlutterSecureStorage();

  ApiClient._internal() {
    _dio = Dio(BaseOptions(
      baseUrl:        AppConfig.baseUrl,
      connectTimeout: Duration(seconds: AppConfig.timeoutSeconds),
      receiveTimeout: Duration(seconds: AppConfig.timeoutSeconds),
      headers: {'Content-Type': 'application/json'},
    ));

    // ── Interceptor: attach JWT token to every request ──
    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        final token = await _storage.read(key: 'access_token');
        if (token != null) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        return handler.next(options);
      },
      onError: (error, handler) {
        // 401 = token expired → force logout (handled in providers)
        return handler.next(error);
      },
    ));
  }

  Dio get dio => _dio;

  // ── Token helpers ─────────────────────────────────────
  Future<void> saveToken(String token) async =>
      _storage.write(key: 'access_token', value: token);

  Future<void> clearToken() async =>
      _storage.delete(key: 'access_token');

  Future<String?> getToken() async =>
      _storage.read(key: 'access_token');

  Future<bool> hasToken() async =>
      (await _storage.read(key: 'access_token')) != null;
}

// ── Friendly error extractor ─────────────────────────────
String extractError(dynamic e) {
  if (e is DioException) {
    final data = e.response?.data;
    if (data is Map && data.containsKey('detail')) {
      return data['detail'].toString();
    }
    switch (e.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.receiveTimeout:
        return 'Connection timed out. Is the server running?';
      case DioExceptionType.connectionError:
        return 'Cannot reach server. Check your IP in constants.dart';
      default:
        return e.message ?? 'Unknown network error';
    }
  }
  return e.toString();
}