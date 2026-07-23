import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/theme/app_theme.dart';
import 'features/auth/session_gate.dart';

void main() {
  runApp(const ProviderScope(child: BaraxolkaApp()));
}

/// Корневой виджет приложения Baraxolka.
class BaraxolkaApp extends StatelessWidget {
  const BaraxolkaApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Барахолка',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.dark,
      home: const SessionGate(),
    );
  }
}
