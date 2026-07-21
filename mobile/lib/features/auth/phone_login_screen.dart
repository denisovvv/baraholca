import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme/app_colors.dart';
import 'auth_providers.dart';
import 'auth_service.dart';
import 'sms_code_screen.dart';

/// Экран входа по номеру телефона («Вход — 1a» из дизайна).
///
/// ConsumerStatefulWidget — StatefulWidget с доступом к Riverpod
/// (нужен для чтения провайдеров и хранения состояния поля/загрузки).
class PhoneLoginScreen extends ConsumerStatefulWidget {
  const PhoneLoginScreen({super.key});

  @override
  ConsumerState<PhoneLoginScreen> createState() => _PhoneLoginScreenState();
}

class _PhoneLoginScreenState extends ConsumerState<PhoneLoginScreen> {
  // Контроллер поля ввода — хранит и даёт доступ к введённому тексту.
  final TextEditingController _phoneController = TextEditingController();
  // Идёт ли сейчас запрос (для блокировки кнопки и спиннера).
  bool _isLoading = false;

  @override
  void dispose() {
    _phoneController.dispose();
    super.dispose();
  }

  /// Собрать полный номер в формате +7XXXXXXXXXX.
  String get _fullPhone {
    // Оставляем только цифры из введённого, добавляем +7.
    final digits = _phoneController.text.replaceAll(RegExp(r'[^0-9]'), '');
    return '+7$digits';
  }

  /// Валиден ли номер (10 цифр после +7).
  bool get _isPhoneValid {
    final digits = _phoneController.text.replaceAll(RegExp(r'[^0-9]'), '');
    return digits.length == 10;
  }

  Future<void> _onRequestCode() async {
    if (!_isPhoneValid || _isLoading) return;

    setState(() => _isLoading = true);
    final authService = ref.read(authServiceProvider);

    try {
      await authService.requestCode(_fullPhone);
      if (!mounted) return;
      // Код отправлен — переходим на экран ввода кода с номером.
      Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (context) => SmsCodeScreen(phone: _fullPhone),
        ),
      );
    } on AuthException catch (e) {
      if (!mounted) return;
      // Показываем ошибку от backend.
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.message)),
      );
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF1C1C1E),
      body: Stack(
        children: [
          // Свечение сверху.
          Positioned(
            top: -80,
            left: 0,
            right: 0,
            child: Center(
              child: Container(
                width: 340,
                height: 340,
                decoration: const BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: RadialGradient(
                    colors: [Color(0x24FFD500), Color(0x00FFD500)],
                    stops: [0.0, 0.7],
                  ),
                ),
              ),
            ),
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24),
              child: Column(
                children: [
                  // Логотип.
                  Padding(
                    padding: const EdgeInsets.only(top: 40, bottom: 8),
                    child: Image.asset('assets/logo-no-sub.png', width: 230),
                  ),
                  const SizedBox(height: 40),
                  // Заголовок + подзаголовок.
                  const Text(
                    'Вход в аккаунт',
                    style: TextStyle(
                      fontSize: 26,
                      fontWeight: FontWeight.w700,
                      color: AppColors.textPrimary,
                      letterSpacing: -0.3,
                    ),
                  ),
                  const SizedBox(height: 10),
                  const Text(
                    'Введите номер телефона — пришлём код в SMS',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 15,
                      height: 1.45,
                      color: Color(0xFF98989E),
                    ),
                  ),
                  const SizedBox(height: 32),
                  // Поле телефона.
                  _PhoneField(
                    controller: _phoneController,
                    onChanged: (_) => setState(() {}),
                  ),
                  const SizedBox(height: 16),
                  // Кнопка "Получить код".
                  SizedBox(
                    width: double.infinity,
                    height: 56,
                    child: ElevatedButton(
                      onPressed:
                          (_isPhoneValid && !_isLoading) ? _onRequestCode : null,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.primary,
                        foregroundColor: const Color(0xFF1A1A1A),
                        disabledBackgroundColor:
                            AppColors.primary.withValues(alpha: 0.4),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(14),
                        ),
                        textStyle: const TextStyle(
                          fontSize: 17,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      child: _isLoading
                          ? const SizedBox(
                              width: 22,
                              height: 22,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Color(0xFF1A1A1A),
                              ),
                            )
                          : const Text('Получить код'),
                    ),
                  ),
                  const Spacer(),
                  // Оферта.
                  const Padding(
                    padding: EdgeInsets.only(bottom: 34, left: 12, right: 12),
                    child: Text(
                      'Нажимая кнопку, вы соглашаетесь с условиями '
                      'использования и политикой конфиденциальности',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 12,
                        height: 1.5,
                        color: Color(0xFF6E6E73),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Поле ввода телефона с префиксом +7.
class _PhoneField extends StatelessWidget {
  const _PhoneField({required this.controller, required this.onChanged});

  final TextEditingController controller;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 60,
      padding: const EdgeInsets.symmetric(horizontal: 18),
      decoration: BoxDecoration(
        color: const Color(0xFF2A2A2D),
        border: Border.all(color: const Color(0xFF444448), width: 1.5),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        children: [
          const Text(
            '+7',
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w600,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(width: 12),
          Container(width: 1, height: 24, color: const Color(0xFF444448)),
          const SizedBox(width: 12),
          Expanded(
            child: TextField(
              controller: controller,
              onChanged: onChanged,
              keyboardType: TextInputType.phone,
              maxLength: 10,
              inputFormatters: [FilteringTextInputFormatter.digitsOnly],
              style: const TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w600,
                color: AppColors.textPrimary,
                letterSpacing: 0.5,
              ),
              decoration: const InputDecoration(
                counterText: '', // убрать счётчик символов
                border: InputBorder.none,
                hintText: '900 000-00-00',
                hintStyle: TextStyle(
                  color: Color(0xFF6E6E73),
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
