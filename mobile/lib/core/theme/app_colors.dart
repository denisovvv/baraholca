import 'package:flutter/material.dart';

/// Фирменные цвета Baraxolka (тёмная тема).
///
/// Взяты из дизайна: тёмный фон, жёлтый акцент (primary),
/// красный для скидок, зелёный для успеха.
class AppColors {
  AppColors._(); // приватный конструктор — класс только для констант

  /// Основной фон приложения.
  static const Color background = Color(0xFF1A1A1A);

  /// Фон карточек (чуть светлее фона).
  static const Color card = Color(0xFF242424);

  /// Основной акцентный цвет (жёлтый). Текст на нём — чёрный.
  static const Color primary = Color(0xFFFFD500);

  /// Основной текст (белый).
  static const Color textPrimary = Color(0xFFFFFFFF);

  /// Второстепенный текст (серый).
  static const Color textSecondary = Color(0xFF9E9E9E);

  /// Красный акцент (скидки, ошибки).
  static const Color accent = Color(0xFFE63329);

  /// Зелёный (успех).
  static const Color success = Color(0xFF4CAF50);
}
