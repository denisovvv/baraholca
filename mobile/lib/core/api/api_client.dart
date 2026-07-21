import 'package:dio/dio.dart';

/// Базовый HTTP-клиент для общения с backend Baraxolka.
///
/// Обёртка над dio с настроенным базовым URL и таймаутами.
/// Пока backend работает локально (runserver), позже сменим
/// baseUrl на боевой домен baraxolkamarket.online.
class ApiClient {
  ApiClient() {
    _dio = Dio(
      BaseOptions(
        // Локальный backend. На симуляторе iOS localhost = Mac.
        baseUrl: 'http://127.0.0.1:8000/api/v1',
        connectTimeout: const Duration(seconds: 10),
        receiveTimeout: const Duration(seconds: 10),
        // Ответы с кодами 4xx не будут кидать исключение сразу —
        // обработаем статусы сами (чтобы читать тело ошибки).
        validateStatus: (status) => status != null && status < 500,
      ),
    );
  }

  late final Dio _dio;

  /// Доступ к настроенному dio для запросов.
  Dio get dio => _dio;
}
