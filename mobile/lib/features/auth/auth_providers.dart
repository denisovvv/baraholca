import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';
import 'auth_service.dart';

/// Провайдер HTTP-клиента (один на приложение).
final apiClientProvider = Provider<ApiClient>((ref) {
  return ApiClient();
});

/// Провайдер сервиса авторизации.
///
/// Берёт ApiClient из провайдера выше — так зависимости
/// связываются через Riverpod, а не создаются вручную.
final authServiceProvider = Provider<AuthService>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  return AuthService(apiClient);
});
