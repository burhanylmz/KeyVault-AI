import 'package:flutter_test/flutter_test.dart';
import 'package:keyvault_ai_mobile/main.dart';
import 'package:keyvault_ai_mobile/services/api_service.dart';
import 'package:keyvault_ai_mobile/services/auth_storage.dart';

void main() {
  testWidgets('KeyVaultApp renders LoginLockScreen', (WidgetTester tester) async {
    final authStorage = AuthStorageService();
    final apiService = ApiService(storage: authStorage);

    await tester.pumpWidget(
      KeyVaultApp(apiService: apiService, authStorage: authStorage),
    );

    expect(find.text('KeyVault'), findsOneWidget);
  });
}
