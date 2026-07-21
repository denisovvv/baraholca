import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme/app_colors.dart';
import 'auth_providers.dart';
import 'auth_service.dart';

/// Экран ввода SMS-кода («Код из SMS — 1c» из дизайна).
///
/// Принимает номер телефона (на него отправлен код), даёт ввести
/// 4 цифры, проверяет через backend и при успехе получает токены.
class SmsCodeScreen extends ConsumerStatefulWidget {
  const SmsCodeScreen({required this.phone, super.key});

  /// Номер, на который отправлен код (формат +7XXXXXXXXXX).
  final String phone;

  @override
  ConsumerState<SmsCodeScreen> createState() => _SmsCodeScreenState();
}

class _SmsCodeScreenState extends ConsumerState<SmsCodeScreen> {
  // Контроллер общего ввода кода (4 цифры).
  final TextEditingController _codeController = TextEditingController();
  // Фокус для скрытого поля ввода.
  final FocusNode _focusNode = FocusNode();
  bool _isLoading = false;

  // Таймер повторной отправки.
  static const int _resendSeconds = 60;
  int _secondsLeft = _resendSeconds;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _startTimer();
    // Автофокус на поле, чтобы клавиатура появилась сразу.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _focusNode.requestFocus();
    });
  }

  @override
  void dispose() {
    _codeController.dispose();
    _focusNode.dispose();
    _timer?.cancel();
    super.dispose();
  }

  void _startTimer() {
    setState(() => _secondsLeft = _resendSeconds);
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (_secondsLeft <= 1) {
        timer.cancel();
        setState(() => _secondsLeft = 0);
      } else {
        setState(() => _secondsLeft--);
      }
    });
  }

  String get _code => _codeController.text;
  bool get _isCodeComplete => _code.length == 4;

  /// Формат номера для показа: +7 900 123-45-67.
  String get _phoneFormatted {
    final d = widget.phone.replaceAll(RegExp(r'[^0-9]'), '');
    // d = 7XXXXXXXXXX
    if (d.length == 11) {
      return '+7 ${d.substring(1, 4)} ${d.substring(4, 7)}-'
          '${d.substring(7, 9)}-${d.substring(9, 11)}';
    }
    return widget.phone;
  }

  Future<void> _onVerify() async {
    if (!_isCodeComplete || _isLoading) return;

    setState(() => _isLoading = true);
    final authService = ref.read(authServiceProvider);

    try {
      final result = await authService.verifyCode(widget.phone, _code);
      if (!mounted) return;
      // Успех — получили токены.
      // TODO: сохранить токены, перейти в каталог (следующий этап).
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            result.isNewUser ? 'Добро пожаловать!' : 'С возвращением!',
          ),
        ),
      );
    } on AuthException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.message)),
      );
      // Очищаем поле для повторного ввода.
      _codeController.clear();
      setState(() {});
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _onResend() async {
    final authService = ref.read(authServiceProvider);
    try {
      await authService.requestCode(widget.phone);
      _startTimer();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Код отправлен повторно')),
      );
    } on AuthException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.message)),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF1C1C1E),
      body: Stack(
        children: [
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
                  // Назад.
                  SizedBox(
                    height: 44,
                    child: Align(
                      alignment: Alignment.centerLeft,
                      child: GestureDetector(
                        onTap: () => Navigator.of(context).pop(),
                        child: const Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.arrow_back_ios_new,
                                size: 16, color: Color(0xFF98989E)),
                            SizedBox(width: 6),
                            Text('Назад',
                                style: TextStyle(
                                    color: Color(0xFF98989E), fontSize: 16)),
                          ],
                        ),
                      ),
                    ),
                  ),
                  // Логотип.
                  Padding(
                    padding: const EdgeInsets.only(top: 28, bottom: 8),
                    child: Image.asset('assets/logo-no-sub.png', width: 180),
                  ),
                  const SizedBox(height: 36),
                  const Text(
                    'Введите код',
                    style: TextStyle(
                      fontSize: 26,
                      fontWeight: FontWeight.w700,
                      color: AppColors.textPrimary,
                      letterSpacing: -0.3,
                    ),
                  ),
                  const SizedBox(height: 10),
                  // Номер + изменить.
                  Text.rich(
                    TextSpan(
                      children: [
                        const TextSpan(
                          text: 'Отправили SMS с кодом на номер\n',
                          style: TextStyle(
                              fontSize: 15,
                              height: 1.45,
                              color: Color(0xFF98989E)),
                        ),
                        TextSpan(
                          text: _phoneFormatted,
                          style: const TextStyle(
                            fontSize: 15,
                            color: AppColors.textPrimary,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 32),
                  // 4 ячейки кода (визуал) поверх скрытого поля.
                  _CodeCells(
                    code: _code,
                    controller: _codeController,
                    focusNode: _focusNode,
                    onChanged: (value) {
                      setState(() {});
                      if (value.length == 4) {
                        _onVerify();
                      }
                    },
                  ),
                  const SizedBox(height: 28),
                  // Таймер / повторная отправка.
                  if (_secondsLeft > 0)
                    Text(
                      'Отправить код повторно через 0:'
                      '${_secondsLeft.toString().padLeft(2, '0')}',
                      style: const TextStyle(
                          fontSize: 15, color: Color(0xFF6E6E73)),
                    )
                  else
                    GestureDetector(
                      onTap: _onResend,
                      child: const Text(
                        'Отправить код повторно',
                        style: TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w600,
                          color: AppColors.primary,
                        ),
                      ),
                    ),
                  const Spacer(),
                  // Кнопка "Войти".
                  Padding(
                    padding: const EdgeInsets.only(bottom: 34),
                    child: SizedBox(
                      width: double.infinity,
                      height: 56,
                      child: ElevatedButton(
                        onPressed:
                            (_isCodeComplete && !_isLoading) ? _onVerify : null,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppColors.primary,
                          foregroundColor: const Color(0xFF1A1A1A),
                          disabledBackgroundColor:
                              const Color(0xFF2A2A2D),
                          disabledForegroundColor: const Color(0xFF6E6E73),
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
                            : const Text('Войти'),
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

/// 4 ячейки кода: визуальные квадраты + скрытое поле ввода.
class _CodeCells extends StatelessWidget {
  const _CodeCells({
    required this.code,
    required this.controller,
    required this.focusNode,
    required this.onChanged,
  });

  final String code;
  final TextEditingController controller;
  final FocusNode focusNode;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return Stack(
      alignment: Alignment.center,
      children: [
        // Визуальные ячейки.
        GestureDetector(
          onTap: () => focusNode.requestFocus(),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: List.generate(4, (index) {
              final filled = index < code.length;
              final isCurrent = index == code.length;
              return Container(
                width: 64,
                height: 72,
                margin: const EdgeInsets.symmetric(horizontal: 6),
                decoration: BoxDecoration(
                  color: const Color(0xFF2A2A2D),
                  border: Border.all(
                    color: isCurrent
                        ? AppColors.primary
                        : const Color(0xFF444448),
                    width: 1.5,
                  ),
                  borderRadius: BorderRadius.circular(14),
                ),
                alignment: Alignment.center,
                child: Text(
                  filled ? code[index] : '',
                  style: const TextStyle(
                    fontSize: 30,
                    fontWeight: FontWeight.w700,
                    color: AppColors.textPrimary,
                  ),
                ),
              );
            }),
          ),
        ),
        // Скрытое поле ввода (ловит клавиатуру).
        Positioned.fill(
          child: Opacity(
            opacity: 0,
            child: TextField(
              controller: controller,
              focusNode: focusNode,
              keyboardType: TextInputType.number,
              maxLength: 4,
              inputFormatters: [FilteringTextInputFormatter.digitsOnly],
              onChanged: onChanged,
              decoration: const InputDecoration(counterText: ''),
            ),
          ),
        ),
      ],
    );
  }
}
