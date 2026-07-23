import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../../core/api/api_client.dart';
import '../../core/api/auth_interceptor.dart';
import 'auth_service.dart';
import 'token_storage.dart';

/// Провайдер HTTP-клиента (один на приложение).
final apiClientProvider = Provider<ApiClient>((ref) {
  final tokenStorage = ref.watch(tokenStorageProvider);
  return ApiClient(interceptors: [AuthInterceptor(tokenStorage)]);
});

/// Провайдер сервиса авторизации.
///
/// Берёт ApiClient из провайдера выше — так зависимости
/// связываются через Riverpod, а не создаются вручную.
final authServiceProvider = Provider<AuthService>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  return AuthService(apiClient);
});

/// Провайдер хранилища токенов (Keychain на iOS).
final tokenStorageProvider = Provider<TokenStorage>((ref) {
  return const TokenStorage(FlutterSecureStorage());
});
