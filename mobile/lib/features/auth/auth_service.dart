import 'package:dio/dio.dart';

import '../../core/api/api_client.dart';
import 'models/auth_result.dart';

/// Исключение авторизации с кодом и сообщением от backend.
///
/// Backend отдаёт ошибки в формате {"error": {"code", "message"}}.
/// Пробрасываем их сюда, чтобы UI показал понятный текст.
class AuthException implements Exception {
  const AuthException(this.code, this.message);

  final String code;
  final String message;

  @override
  String toString() => message;
}

/// Сервис авторизации по SMS.
///
/// Общается с backend endpoints /auth/sms/request/ и /auth/sms/verify/.
class AuthService {
  AuthService(this._apiClient);

  final ApiClient _apiClient;

  /// Запросить SMS-код на номер телефона.
  ///
  /// [phone] — номер в формате +7XXXXXXXXXX.
  /// При успехе backend отправляет SMS. Кидает AuthException при ошибке.
  Future<void> requestCode(String phone) async {
    try {
      final response = await _apiClient.dio.post(
        '/auth/sms/request/',
        data: {'phone': phone},
      );

      if (response.statusCode == 200) {
        return; // код отправлен
      }
      // Не 200 — разбираем ошибку от backend.
      throw _parseError(response);
    } on DioException catch (e) {
      // Сетевая ошибка (нет соединения, таймаут).
      throw _networkError(e);
    }
  }

  /// Проверить SMS-код. При успехе возвращает токены.
  ///
  /// [phone] — номер, [code] — 4 цифры.
  Future<AuthResult> verifyCode(String phone, String code) async {
    try {
      final response = await _apiClient.dio.post(
        '/auth/sms/verify/',
        data: {'phone': phone, 'code': code},
      );

      if (response.statusCode == 200) {
        return AuthResult.fromJson(response.data as Map<String, dynamic>);
      }
      throw _parseError(response);
    } on DioException catch (e) {
      throw _networkError(e);
    }
  }

  /// Разобрать ошибку из ответа backend ({"error": {"code", "message"}}).
  AuthException _parseError(Response<dynamic> response) {
    final data = response.data;
    if (data is Map && data['error'] is Map) {
      final error = data['error'] as Map;
      return AuthException(
        error['code'] as String? ?? 'unknown',
        error['message'] as String? ?? 'Произошла ошибка',
      );
    }
    // Ответ без стандартной обёртки (например, 503 с {"detail": ...}).
    if (data is Map && data['detail'] != null) {
      return AuthException('service_error', data['detail'] as String);
    }
    return const AuthException('unknown', 'Произошла ошибка');
  }

  /// Ошибка сети (нет соединения с backend).
  AuthException _networkError(DioException e) {
    return const AuthException(
      'network_error',
      'Нет соединения с сервером. Проверьте интернет.',
    );
  }
}
