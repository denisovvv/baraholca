import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/auth_providers.dart';
import 'catalog_service.dart';
import 'models/product.dart';

/// Провайдер сервиса каталога.
final catalogServiceProvider = Provider<CatalogService>((ref) {
  return CatalogService(ref.watch(apiClientProvider));
});

/// Состояние списка товаров: сами товары плюс данные для пагинации.
class CatalogState {
  const CatalogState({
    required this.items,
    required this.total,
    this.nextUrl,
    this.isLoadingMore = false,
  });

  final List<Product> items;

  /// Всего товаров по текущему фильтру (для счётчика в UI).
  final int total;

  /// Ссылка на следующую страницу. null — всё загружено.
  final String? nextUrl;

  /// Идёт догрузка следующей страницы (спиннер внизу списка).
  final bool isLoadingMore;

  bool get hasMore => nextUrl != null;

  CatalogState copyWith({
    List<Product>? items,
    int? total,
    String? nextUrl,
    bool? isLoadingMore,
    bool clearNext = false,
  }) {
    return CatalogState(
      items: items ?? this.items,
      total: total ?? this.total,
      nextUrl: clearNext ? null : (nextUrl ?? this.nextUrl),
      isLoadingMore: isLoadingMore ?? this.isLoadingMore,
    );
  }
}

/// Управляет списком товаров каталога.
///
/// AsyncNotifier сам переводит состояние в loading/data/error —
/// вручную флаги загрузки держать не нужно.
class CatalogNotifier extends AsyncNotifier<CatalogState> {
  @override
  Future<CatalogState> build() async {
    return _loadFirstPage();
  }

  Future<CatalogState> _loadFirstPage() async {
    final service = ref.read(catalogServiceProvider);
    final page = await service.fetchProducts();
    return CatalogState(
      items: page.items,
      total: page.count,
      nextUrl: page.next,
    );
  }

  /// Обновление списка (свайп вниз). Показывает загрузку заново.
  Future<void> refresh() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(_loadFirstPage);
  }

  /// Догрузить следующую страницу при прокрутке до конца.
  Future<void> loadMore() async {
    final current = state.value;
    // Выходим, если данных ещё нет, страницы кончились
    // или догрузка уже идёт — иначе словим дубли товаров.
    if (current == null || !current.hasMore || current.isLoadingMore) {
      return;
    }

    state = AsyncValue.data(current.copyWith(isLoadingMore: true));
    try {
      final service = ref.read(catalogServiceProvider);
      final page = await service.fetchNextPage(current.nextUrl!);
      state = AsyncValue.data(
        CatalogState(
          items: [...current.items, ...page.items],
          total: page.count,
          nextUrl: page.next,
        ),
      );
    } on CatalogException {
      // Догрузка не удалась — оставляем уже показанные товары,
      // просто снимаем индикатор. Терять список из-за одной
      // неудачной страницы нельзя.
      state = AsyncValue.data(current.copyWith(isLoadingMore: false));
    }
  }
}

final catalogProvider =
    AsyncNotifierProvider<CatalogNotifier, CatalogState>(CatalogNotifier.new);
