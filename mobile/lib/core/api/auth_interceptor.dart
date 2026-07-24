import 'dart:async';

import 'package:dio/dio.dart';

import '../../features/auth/token_storage.dart';

/// Подставляет JWT в запросы и обновляет его при истечении.
///
/// Публичные эндпоинты (каталог) работают и без токена, но DRF
/// отвергает НЕВАЛИДНЫЙ заголовок раньше, чем доходит до проверки
/// прав — поэтому протухший токен ломает даже открытые данные.
class AuthInterceptor extends Interceptor {
  AuthInterceptor(this._tokenStorage, this._baseUrl);

  final TokenStorage _tokenStorage;

  /// Обновление делаем сами, отдельным чистым dio: обращаться
  /// к сервису из клиента, который этот сервис же и создаёт,
  /// оказалось ненадёжно.
  final String _baseUrl;

  /// Идущее обновление. Пока оно не завершилось, параллельные
  /// запросы ждут его результат, а не запускают своё — иначе
  /// одноразовый refresh сгорит на первом же обмене.
  Future<String?>? _refreshInFlight;

  /// Путь обновления не перехватываем, чтобы не зациклиться.
  static const String _refreshPath = '/auth/token/refresh/';

  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    if (options.path.contains(_refreshPath)) {
      handler.next(options);
      return;
    }
    final access = await _tokenStorage.readAccess();
    if (access != null && access.isNotEmpty) {
      options.headers['Authorization'] = 'Bearer $access';
    }
    handler.next(options);
  }

  @override
  Future<void> onResponse(
    Response<dynamic> response,
    ResponseInterceptorHandler handler,
  ) async {
    // validateStatus пропускает 4xx как обычный ответ, поэтому
    // 401 ловим здесь, а не в onError.
    if (response.statusCode != 401) {
      handler.next(response);
      return;
    }

    final options = response.requestOptions;
    // Повторяем запрос только один раз: если и после обновления
    // прилетела 401, дело не в сроке токена.
    if (options.extra['retried'] == true ||
        options.path.contains(_refreshPath)) {
      handler.next(response);
      return;
    }

    final newAccess = await _ensureRefreshed();
    if (newAccess == null) {
      // Восстановить сессию не вышло — токены уже очищены,
      // отдаём исходную 401 наверх.
      handler.next(response);
      return;
    }

    try {
      final retried = await _retry(options, newAccess);
      handler.next(retried);
    } on DioException {
      handler.next(response);
    }
  }

  /// Обновляет токен, объединяя параллельные попытки в одну.
  Future<String?> _ensureRefreshed() {
    return _refreshInFlight ??= _doRefresh().whenComplete(() {
      _refreshInFlight = null;
    });
  }

  Future<String?> _doRefresh() async {
    final refresh = await _tokenStorage.readRefresh();
    if (refresh == null || refresh.isEmpty) {
      return null;
    }
    // Ловим ВСЁ: любое необработанное исключение здесь роняет
    // onResponse и превращается в "нет соединения" на экране.
    try {
      final plainDio = Dio(
        BaseOptions(
          baseUrl: _baseUrl,
          connectTimeout: const Duration(seconds: 10),
          receiveTimeout: const Duration(seconds: 10),
          validateStatus: (status) => status != null && status < 500,
        ),
      );
      final response = await plainDio.post<dynamic>(
        _refreshPath,
        data: {'refresh': refresh},
      );
      if (response.statusCode != 200) {
        await _tokenStorage.clear();
        return null;
      }
      final data = response.data as Map<String, dynamic>;
      final access = data['access'] as String;
      await _tokenStorage.saveTokens(
        access: access,
        // ROTATE_REFRESH_TOKENS на бэкенде: старый refresh уходит
        // в чёрный список, сохранять нужно пришедший.
        refresh: data['refresh'] as String? ?? refresh,
      );
      return access;
    } catch (_) {
      // Обновиться не вышло: пусть запрос вернёт исходную 401,
      // а SessionGate при следующем старте отправит на вход.
      return null;
    }
  }

  /// Повторяет исходный запрос с новым токеном.
  Future<Response<dynamic>> _retry(
    RequestOptions options,
    String access,
  ) {
    final retryDio = Dio(
      BaseOptions(
        baseUrl: options.baseUrl,
        connectTimeout: options.connectTimeout,
        receiveTimeout: options.receiveTimeout,
        validateStatus: options.validateStatus,
      ),
    );
    return retryDio.fetch<dynamic>(
      options
        ..headers['Authorization'] = 'Bearer $access'
        ..extra['retried'] = true,
    );
  }
}
