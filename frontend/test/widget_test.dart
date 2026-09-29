import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:visibility_detector/visibility_detector.dart';
import 'package:frontend/main.dart';
import 'package:frontend/generated_params_data.dart';

void main() {
  testWidgets('App loads parameter explorer on mobile viewport (384x800) with zero overflow',
      (WidgetTester tester) async {
    // Set mobile phone screen size (384x800)
    tester.view.physicalSize = const Size(384, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);

    VisibilityDetectorController.instance.updateInterval = Duration.zero;
    await tester.pumpWidget(const YaskawaControllerApp());
    await tester.pump();

    // Verify main components are present
    expect(find.text('Parameter Explorer'), findsOneWidget);
    expect(find.text('SECTIONS (OUTER LAYER)'), findsOneWidget);
    expect(find.text('GA700'), findsWidgets);

    // Tap first section (10.4) to test drill-down navigation
    await tester.tap(find.text('10.4'));
    await tester.pumpAndSettle();

    // Verify we navigated to Level 2 (SectionParamsScreen)
    expect(find.text('A: Initialization Parameters'), findsOneWidget);
    expect(find.text('A1-00'), findsOneWidget);
    expect(find.text('EDIT'), findsWidgets);
    expect(find.text('READ'), findsNothing);

    // Tap back button
    await tester.tap(find.byTooltip('Back to Sections'));
    await tester.pumpAndSettle();

    // Verify we are back on Level 1
    expect(find.text('SECTIONS (OUTER LAYER)'), findsOneWidget);
  });

  test('d1-01 frequency scaling: entering 40 converts to raw 4000, raw 4000 formats as 40.00 Hz', () {
    final d101 = kParamsByCode['d1-01'];
    expect(d101, isNotNull);
    expect(d101!.decimals, 2);
    expect(d101.multiplier, 0.01);
    expect(d101.unit, 'Hz');

    // User enters 40 (meaning 40 Hz) -> Modbus raw register must be 4000 so drive shows 40.00 Hz
    expect(d101.parseUserInputToRaw('40'), 4000);
    expect(d101.parseUserInputToRaw('40.00'), 4000);
    expect(d101.parseUserInputToRaw('50'), 5000);
    expect(d101.parseUserInputToRaw('25.5'), 2550);

    // Reading raw 4000 from drive -> formats as 40.00 Hz
    expect(d101.formatLiveValue(4000), '40.00 Hz');
  });

  test('U1-01 frequency monitor scaling: raw 4000 formats as 40.00 Hz matching VFD keypad', () {
    final u101 = kParamsByCode['U1-01'];
    expect(u101, isNotNull);
    expect(u101!.decimals, 2);
    expect(u101.multiplier, 0.01);
    expect(u101.unit, 'Hz');

    // Raw 4000 returned by ESP32 Modbus read -> displays 40.00 Hz instead of 4000
    expect(u101.formatLiveValue(4000), '40.00 Hz');
  });

  test('U1-06 voltage monitor scaling: raw 2300 formats as 230.0 V', () {
    final u106 = kParamsByCode['U1-06'];
    expect(u106, isNotNull);
    expect(u106!.decimals, 1);
    expect(u106.multiplier, 0.1);
    expect(u106.unit, 'V');

    expect(u106.formatLiveValue(2300), '230.0 V');
  });
}
