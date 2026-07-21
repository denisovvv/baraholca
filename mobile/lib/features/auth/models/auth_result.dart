/// Результат успешной проверки SMS-кода (ответ /auth/sms/verify/).
///
/// Повторяет структуру JSON от backend: токены + данные пользователя.
class AuthResult {
  const AuthResult({
    required this.access,
    required this.refresh,
    required this.isNewUser,
  });

  /// JWT access-токен (короткоживущий, для запросов).
  final String access;

  /// JWT refresh-токен (долгоживущий, для обновления access).
  final String refresh;

  /// true — пользователь только что зарегистрировался.
  final bool isNewUser;

  /// Создать из JSON-ответа backend.
  factory AuthResult.fromJson(Map<String, dynamic> json) {
    return AuthResult(
      access: json['access'] as String,
      refresh: json['refresh'] as String,
      isNewUser: json['is_new_user'] as bool? ?? false,
    );
  }
}
