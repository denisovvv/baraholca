import 'package:dio/dio.dart';

import '../../core/api/api_client.dart';
import 'models/product.dart';

/// Ошибка загрузки каталога с готовым текстом для UI.
class CatalogException implements Exception {
  const CatalogException(this.message);

  final String message;

  @override
  String toString() => message;
}

/// Загрузка товаров каталога.
class CatalogService {
  CatalogService(this._apiClient);

  final ApiClient _apiClient;

  /// Сколько товаров запрашиваем за раз.
  static const int pageSize = 20;

  /// Первая страница каталога.
  ///
  /// [search] — строка поиска, [categoryId] — фильтр по категории.
  Future<ProductPage> fetchProducts({
    String? search,
    int? categoryId,
  }) async {
    // Пустые параметры не отправляем, иначе backend отфильтрует по "".
    final params = <String, dynamic>{'limit': pageSize};
    if (search != null && search.isNotEmpty) {
      params['search'] = search;
    }
    if (categoryId != null) {
      params['category'] = categoryId;
    }
    return _request(() => _apiClient.dio.get<dynamic>(
          '/catalog/products/',
          queryParameters: params,
        ));
  }

  /// Следующая страница по ссылке из поля next.
  ///
  /// Backend отдаёт абсолютный URL, поэтому передаём его целиком —
  /// dio подставит baseUrl только для относительных путей.
  Future<ProductPage> fetchNextPage(String nextUrl) {
    return _request(() => _apiClient.dio.get<dynamic>(nextUrl));
  }

  /// Общая обвязка: выполнить запрос и разобрать ответ.
  Future<ProductPage> _request(
    Future<Response<dynamic>> Function() send,
  ) async {
    try {
      final response = await send();
      if (response.statusCode == 200) {
        return ProductPage.fromJson(response.data as Map<String, dynamic>);
      }
      throw const CatalogException('Не удалось загрузить товары');
    } on DioException {
      throw const CatalogException(
        'Нет соединения с сервером. Проверьте интернет.',
      );
    }
  }
}
