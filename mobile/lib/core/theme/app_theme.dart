import 'package:flutter/material.dart';

import 'app_colors.dart';

/// Тема приложения Baraxolka (тёмная).
///
/// Задаёт цвета фона, текста, кнопок для всех экранов.
/// Применяется один раз в MaterialApp.
class AppTheme {
  AppTheme._();

  static ThemeData get dark {
    return ThemeData(
      // Тёмная основа — Flutter правильно рассчитает контрасты.
      brightness: Brightness.dark,
      scaffoldBackgroundColor: AppColors.background,
      // Основная палитра из фирменных цветов.
      colorScheme: const ColorScheme.dark(
        primary: AppColors.primary,
        // Текст/иконки поверх жёлтого — чёрные (правило из дизайна).
        onPrimary: Colors.black,
        surface: AppColors.card,
        onSurface: AppColors.textPrimary,
        error: AppColors.accent,
      ),
      // Стиль основных кнопок: жёлтый фон, чёрный текст.
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.primary,
          foregroundColor: Colors.black,
          minimumSize: const Size.fromHeight(52),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          textStyle: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }
}
