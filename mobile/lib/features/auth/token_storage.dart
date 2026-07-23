import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Безопасное хранилище JWT-токенов.
///
/// На iOS пишет в Keychain, на Android — в EncryptedSharedPreferences.
/// Обычные настройки приложения для токенов не годятся: это ключи
/// от аккаунта, их шифрует сама система.
class TokenStorage {
  const TokenStorage(this._storage);

  final FlutterSecureStorage _storage;

  static const String _accessKey = 'access_token';
  static const String _refreshKey = 'refresh_token';

  /// Сохранить пару токенов после успешного входа.
  Future<void> saveTokens({
    required String access,
    required String refresh,
  }) async {
    await _storage.write(key: _accessKey, value: access);
    await _storage.write(key: _refreshKey, value: refresh);
  }

  /// Access-токен для заголовка Authorization. null — не авторизован.
  Future<String?> readAccess() => _storage.read(key: _accessKey);

  /// Refresh-токен для обновления истёкшего access.
  Future<String?> readRefresh() => _storage.read(key: _refreshKey);

  /// Есть ли сохранённая сессия (проверка при старте приложения).
  Future<bool> hasSession() async {
    final access = await readAccess();
    return access != null && access.isNotEmpty;
  }

  /// Удалить токены (выход из аккаунта).
  Future<void> clear() async {
    await _storage.delete(key: _accessKey);
    await _storage.delete(key: _refreshKey);
  }
}
