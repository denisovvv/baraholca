import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../onboarding/onboarding_screen.dart';
import 'auth_providers.dart';

/// Стартовая развилка: есть сохранённая сессия — внутрь, нет — онбординг.
///
/// Чтение токена из Keychain асинхронное, поэтому на время проверки
/// показываем индикатор загрузки.
class SessionGate extends ConsumerStatefulWidget {
  const SessionGate({super.key});

  @override
  ConsumerState<SessionGate> createState() => _SessionGateState();
}

class _SessionGateState extends ConsumerState<SessionGate> {
  late Future<bool> _sessionCheck;

  @override
  void initState() {
    super.initState();
    // Future создаём один раз в initState, а не в build:
    // иначе при каждой перерисовке запускалась бы новая проверка.
    _sessionCheck = ref.read(tokenStorageProvider).hasSession();
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<bool>(
      future: _sessionCheck,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          );
        }
        final hasSession = snapshot.data ?? false;
        return hasSession ? const TempHomeScreen() : const OnboardingScreen();
      },
    );
  }
}

/// Временный экран после входа. Заменим на каталог.
class TempHomeScreen extends ConsumerWidget {
  const TempHomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Text('Вы вошли', style: TextStyle(fontSize: 24)),
            const SizedBox(height: 24),
            TextButton(
              onPressed: () async {
                await ref.read(tokenStorageProvider).clear();
                if (!context.mounted) return;
                Navigator.of(context).pushReplacement(
                  MaterialPageRoute<void>(
                    builder: (context) => const OnboardingScreen(),
                  ),
                );
              },
              child: const Text('Выйти'),
            ),
          ],
        ),
      ),
    );
  }
}
