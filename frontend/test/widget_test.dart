// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility in the flutter_test package. For example, you can send tap and scroll
// gestures. You can also use WidgetTester to find child widgets in the widget
// tree, read text, and verify that the values of widget properties are correct.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:frontend/main.dart';

void main() {
  testWidgets('App loads dashboard and parameter navigation', (WidgetTester tester) async {
    // Set a large screen size for test environment
    tester.view.physicalSize = const Size(1280, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);

    await tester.pumpWidget(const YaskawaControllerApp());
    await tester.pump();

    // Verify main components are present
    expect(find.text('Yaskawa RS-485 Controller'), findsOneWidget);
    expect(find.text('VFD Dashboard'), findsOneWidget);
    expect(find.text('Parameter Explorer (1,003)'), findsOneWidget);
  });
}
