/// Форматирование цен, приходящих с backend строками ("1400.00").
///
/// Никакой арифметики: строку только разбираем и красиво выводим.
/// Переводить деньги в double нельзя — теряется точность.
String formatPrice(String raw) {
  // Отбрасываем копейки, если они нулевые: "1400.00" -> "1400".
  final parts = raw.split('.');
  final whole = parts.first;
  final fraction = parts.length > 1 ? parts[1] : '';

  final grouped = _groupThousands(whole);
  if (fraction.isEmpty || int.tryParse(fraction) == 0) {
    return '$grouped ₽';
  }
  return '$grouped,$fraction ₽';
}

/// Разбивает число на разряды неразрывным пробелом: 1400 -> 1 400.
String _groupThousands(String digits) {
  final buffer = StringBuffer();
  for (var i = 0; i < digits.length; i++) {
    // Отступаем от конца строки: каждые 3 цифры вставляем разделитель.
    final positionFromEnd = digits.length - i;
    if (i > 0 && positionFromEnd % 3 == 0) {
      buffer.write('\u00A0');
    }
    buffer.write(digits[i]);
  }
  return buffer.toString();
}
