/// Товар в списке каталога (ответ /catalog/products/).
///
/// Цены хранятся строками, как их отдаёт backend (Decimal).
/// Клиент их только показывает: любая арифметика с деньгами —
/// на стороне сервера, чтобы не терять точность.
class Product {
  const Product({
    required this.id,
    required this.nameShort,
    required this.sellerName,
    required this.categoryName,
    required this.basePrice,
    required this.effectivePrice,
    required this.productType,
    required this.reviewsCount,
    required this.variantsCount,
    this.mainImageUrl,
    this.discountPrice,
    this.ratingAvg,
  });

  final int id;
  final String nameShort;
  final String sellerName;
  final String categoryName;

  /// Полный URL картинки. null — товар без фото, нужна заглушка.
  final String? mainImageUrl;

  /// Цена без скидки.
  final String basePrice;

  /// Цена со скидкой. null — скидки нет.
  final String? discountPrice;

  /// Цена, по которой товар реально продаётся.
  final String effectivePrice;

  /// stock — со склада, print3d — под заказ (3D-печать).
  final String productType;

  /// Средний рейтинг. null — отзывов ещё нет.
  final double? ratingAvg;
  final int reviewsCount;

  /// Сколько вариантов (цветов/размеров) в группе. 0 — вариантов нет.
  final int variantsCount;

  bool get hasDiscount => discountPrice != null;
  bool get hasRating => ratingAvg != null && reviewsCount > 0;

  factory Product.fromJson(Map<String, dynamic> json) {
    return Product(
      id: json['id'] as int,
      nameShort: json['name_short'] as String,
      sellerName: json['seller_name'] as String? ?? '',
      categoryName: json['category_name'] as String? ?? '',
      mainImageUrl: json['main_image_url'] as String?,
      basePrice: json['base_price'] as String,
      discountPrice: json['discount_price'] as String?,
      effectivePrice: json['effective_price'] as String,
      productType: json['product_type'] as String? ?? 'stock',
      ratingAvg: (json['rating_avg'] as num?)?.toDouble(),
      reviewsCount: json['reviews_count'] as int? ?? 0,
      variantsCount: json['variants_count'] as int? ?? 0,
    );
  }
}

/// Страница результатов с пагинацией (формат DRF).
class ProductPage {
  const ProductPage({
    required this.count,
    required this.items,
    this.next,
  });

  /// Всего товаров по текущему фильтру.
  final int count;

  /// URL следующей страницы. null — больше нечего грузить.
  final String? next;

  final List<Product> items;

  factory ProductPage.fromJson(Map<String, dynamic> json) {
    final results = json['results'] as List<dynamic>;
    return ProductPage(
      count: json['count'] as int,
      next: json['next'] as String?,
      items: results
          .map((e) => Product.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}
