import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme/app_colors.dart';
import '../auth/auth_providers.dart';
import '../auth/session_gate.dart';
import 'catalog_providers.dart';
import 'models/product.dart';

/// Главный экран — каталог товаров («Каталог — 1d» из дизайна).
class CatalogScreen extends ConsumerStatefulWidget {
  const CatalogScreen({super.key});

  @override
  ConsumerState<CatalogScreen> createState() => _CatalogScreenState();
}

class _CatalogScreenState extends ConsumerState<CatalogScreen> {
  final ScrollController _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  /// Догружаем следующую страницу заранее — за 400px до конца,
  /// чтобы пользователь не упирался в пустоту и спиннер.
  void _onScroll() {
    final position = _scrollController.position;
    if (position.pixels >= position.maxScrollExtent - 400) {
      ref.read(catalogProvider.notifier).loadMore();
    }
  }

  @override
  Widget build(BuildContext context) {
    final catalog = ref.watch(catalogProvider);

    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Column(
          children: [
            const _CatalogHeader(),
            const _SearchField(),
            Expanded(
              // AsyncValue сам разводит три состояния — руками
              // флаги загрузки держать не нужно.
              child: catalog.when(
                loading: () => const Center(
                  child: CircularProgressIndicator(color: AppColors.primary),
                ),
                error: (error, _) => _ErrorView(
                  message: error.toString(),
                  onRetry: () => ref.read(catalogProvider.notifier).refresh(),
                ),
                data: (state) => RefreshIndicator(
                  color: AppColors.primary,
                  backgroundColor: AppColors.card,
                  onRefresh: () =>
                      ref.read(catalogProvider.notifier).refresh(),
                  child: _ProductGrid(
                    state: state,
                    controller: _scrollController,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Шапка: город и иконки уведомлений/избранного.
class _CatalogHeader extends ConsumerWidget {
  const _CatalogHeader();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: SizedBox(
        height: 44,
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            // TODO: выбор города, когда появится список складов.
            const Row(
              children: [
                Icon(Icons.location_on_outlined,
                    size: 16, color: AppColors.textSecondary),
                SizedBox(width: 6),
                Text(
                  'Воронеж',
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: AppColors.textPrimary,
                  ),
                ),
                SizedBox(width: 4),
                Icon(Icons.keyboard_arrow_down,
                    size: 18, color: AppColors.textSecondary),
              ],
            ),
            Row(
              children: [
                IconButton(
                  onPressed: () {},
                  icon: const Icon(Icons.notifications_none,
                      color: AppColors.textPrimary, size: 22),
                ),
                IconButton(
                  onPressed: () {},
                  icon: const Icon(Icons.favorite_border,
                      color: AppColors.textPrimary, size: 22),
                ),
                // TODO: временный выход, уедет в профиль.
                IconButton(
                  onPressed: () async {
                    await ref.read(tokenStorageProvider).clear();
                    if (!context.mounted) return;
                    await Navigator.of(context).pushAndRemoveUntil(
                      MaterialPageRoute<void>(
                        builder: (context) => const SessionGate(),
                      ),
                      (route) => false,
                    );
                  },
                  icon: const Icon(Icons.logout,
                      color: AppColors.textSecondary, size: 20),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// Поле поиска. Логику подключим вместе с автодополнением.
class _SearchField extends StatelessWidget {
  const _SearchField();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
      child: Container(
        height: 46,
        padding: const EdgeInsets.symmetric(horizontal: 14),
        decoration: BoxDecoration(
          color: AppColors.card,
          borderRadius: BorderRadius.circular(13),
        ),
        child: const Row(
          children: [
            Icon(Icons.search, size: 18, color: AppColors.textSecondary),
            SizedBox(width: 10),
            Expanded(
              child: Text(
                'Поиск товаров',
                style: TextStyle(fontSize: 15, color: AppColors.textSecondary),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Сетка товаров в две колонки.
class _ProductGrid extends StatelessWidget {
  const _ProductGrid({required this.state, required this.controller});

  final CatalogState state;
  final ScrollController controller;

  @override
  Widget build(BuildContext context) {
    if (state.items.isEmpty) {
      return ListView(
        controller: controller,
        physics: const AlwaysScrollableScrollPhysics(),
        children: const [
          SizedBox(height: 120),
          Center(
            child: Text(
              'Товаров пока нет',
              style: TextStyle(color: AppColors.textSecondary, fontSize: 15),
            ),
          ),
        ],
      );
    }

    return CustomScrollView(
      controller: controller,
      // Список из пары товаров короче экрана: без этой физики
      // его нельзя оттянуть, и RefreshIndicator не сработает.
      physics: const AlwaysScrollableScrollPhysics(),
      slivers: [
        const SliverToBoxAdapter(
          child: Padding(
            padding: EdgeInsets.fromLTRB(16, 20, 16, 12),
            child: Text(
              'Товары',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w700,
                color: AppColors.textPrimary,
              ),
            ),
          ),
        ),
        SliverPadding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          sliver: SliverGrid(
            gridDelegate:
                const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 2,
              mainAxisSpacing: 12,
              crossAxisSpacing: 12,
              // Подобрано под макет: картинка почти квадратная
              // плюс блок с названием, ценой и рейтингом.
              childAspectRatio: 0.62,
            ),
            delegate: SliverChildBuilderDelegate(
              (context, index) => _ProductCard(product: state.items[index]),
              childCount: state.items.length,
            ),
          ),
        ),
        SliverToBoxAdapter(
          child: SizedBox(
            height: state.isLoadingMore ? 60 : 20,
            child: state.isLoadingMore
                ? const Center(
                    child: SizedBox(
                      width: 22,
                      height: 22,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: AppColors.primary,
                      ),
                    ),
                  )
                : null,
          ),
        ),
      ],
    );
  }
}

/// Карточка товара.
class _ProductCard extends StatelessWidget {
  const _ProductCard({required this.product});

  final Product product;

  /// "1400.00" -> "1 400 ₽". Копейки отбрасываем: в каталоге
  /// они только мешают, а точные расчёты всё равно на сервере.
  String _formatPrice(String raw) {
    final whole = raw.split('.').first;
    final buffer = StringBuffer();
    for (var i = 0; i < whole.length; i++) {
      if (i > 0 && (whole.length - i) % 3 == 0) {
        buffer.write(' ');
      }
      buffer.write(whole[i]);
    }
    return '${buffer.toString()} \u20BD';
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(14),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Stack(
              children: [
                Positioned.fill(child: _ProductImage(url: product.mainImageUrl)),
                if (product.hasDiscount)
                  Positioned(
                    top: 8,
                    left: 8,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: AppColors.accent,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: const Text(
                        'Скидка',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                          color: Colors.white,
                        ),
                      ),
                    ),
                  ),
                Positioned(
                  top: 6,
                  right: 6,
                  child: Container(
                    width: 32,
                    height: 32,
                    decoration: BoxDecoration(
                      color: AppColors.background.withValues(alpha: 0.55),
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(Icons.favorite_border,
                        size: 17, color: Colors.white),
                  ),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SizedBox(
                  height: 35,
                  child: Text(
                    product.nameShort,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 13,
                      height: 1.35,
                      color: AppColors.textPrimary,
                    ),
                  ),
                ),
                const SizedBox(height: 6),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.baseline,
                  textBaseline: TextBaseline.alphabetic,
                  children: [
                    Text(
                      _formatPrice(product.effectivePrice),
                      style: const TextStyle(
                        fontSize: 17,
                        fontWeight: FontWeight.w800,
                        color: AppColors.primary,
                      ),
                    ),
                    if (product.hasDiscount) ...[
                      const SizedBox(width: 7),
                      Flexible(
                        child: Text(
                          _formatPrice(product.basePrice),
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            fontSize: 13,
                            color: AppColors.textSecondary,
                            decoration: TextDecoration.lineThrough,
                          ),
                        ),
                      ),
                    ],
                  ],
                ),
                if (product.hasRating) ...[
                  const SizedBox(height: 6),
                  Row(
                    children: [
                      const Text('\u2605',
                          style: TextStyle(
                              fontSize: 12, color: AppColors.primary)),
                      const SizedBox(width: 4),
                      Text(
                        product.ratingAvg!.toStringAsFixed(1),
                        style: const TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: AppColors.textPrimary,
                        ),
                      ),
                    ],
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Картинка товара с заглушкой: фото есть не у всех позиций,
/// а битая ссылка не должна ронять карточку.
class _ProductImage extends StatelessWidget {
  const _ProductImage({required this.url});

  final String? url;

  @override
  Widget build(BuildContext context) {
    const placeholder = ColoredBox(
      color: Color(0xFF2E2E30),
      child: Center(
        child: Icon(Icons.image_outlined, size: 36, color: Color(0xFF4A4A4E)),
      ),
    );

    if (url == null || url!.isEmpty) {
      return placeholder;
    }
    return Image.network(
      url!,
      fit: BoxFit.cover,
      errorBuilder: (context, error, stackTrace) => placeholder,
    );
  }
}

/// Ошибка загрузки с возможностью повторить.
class _ErrorView extends StatelessWidget {
  const _ErrorView({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              message,
              textAlign: TextAlign.center,
              style: const TextStyle(
                  color: AppColors.textSecondary, fontSize: 15),
            ),
            const SizedBox(height: 20),
            TextButton(
              onPressed: onRetry,
              child: const Text('Повторить',
                  style: TextStyle(color: AppColors.primary, fontSize: 15)),
            ),
          ],
        ),
      ),
    );
  }
}
