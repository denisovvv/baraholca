import 'package:dio/dio.dart';

import '../../features/auth/token_storage.dart';

/// Подставляет JWT в заголовок Authorization для каждого запроса.
///
/// Публичные эндпоинты (каталог, запрос SMS-кода) работают и без него —
/// backend просто игнорирует заголовок. Приватные (корзина, профиль,
/// заказы) без него вернут 401.
class AuthInterceptor extends Interceptor {
  const AuthInterceptor(this._tokenStorage);

  final TokenStorage _tokenStorage;

  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    final access = await _tokenStorage.readAccess();
    if (access != null && access.isNotEmpty) {
      options.headers['Authorization'] = 'Bearer $access';
    }
    // handler.next передаёт запрос дальше по цепочке — без этого
    // вызова запрос никогда не уйдёт.
    handler.next(options);
  }
}
