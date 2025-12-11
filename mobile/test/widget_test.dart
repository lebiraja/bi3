import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:incident_agent/main.dart';

void main() {
  testWidgets('App builds without crashing', (WidgetTester tester) async {
    await tester.pumpWidget(const IncidentAgentApp());
    expect(find.text('BI3 Incident Agent'), findsOneWidget);
  });
}
