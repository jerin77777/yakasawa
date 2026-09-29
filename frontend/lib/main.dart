import 'dart:async';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'param_explorer_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const YaskawaControllerApp());
}

class YaskawaControllerApp extends StatelessWidget {
  const YaskawaControllerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Yaskawa GA700 Parameter Explorer',
      debugShowCheckedModeBanner: false,
      themeMode: ThemeMode.light,
      theme: ThemeData(
        brightness: Brightness.light,
        scaffoldBackgroundColor: const Color(0xFFF8FAFC),
        colorScheme: const ColorScheme.light(
          primary: Color(0xFF2563EB), // Royal Blue
          secondary: Color(0xFF0284C7), // Sky Blue
          surface: Colors.white,
          error: Color(0xFFDC2626),
        ),
        fontFamily: 'Segoe UI',
        useMaterial3: true,
        appBarTheme: const AppBarTheme(
          backgroundColor: Colors.white,
          foregroundColor: Color(0xFF0F172A),
          elevation: 0,
          scrolledUnderElevation: 0,
        ),
      ),
      home: const MainParameterScreen(),
    );
  }
}

class MainParameterScreen extends StatefulWidget {
  const MainParameterScreen({super.key});

  @override
  State<MainParameterScreen> createState() => _MainParameterScreenState();
}

class _MainParameterScreenState extends State<MainParameterScreen> {
  final TextEditingController _ipController = TextEditingController(
    text: '192.168.4.1',
  );
  bool _isConnected = false;
  bool _isConnecting = false;
  int _lastLatencyMs = 0;

  final List<String> _logs = [];
  final ScrollController _logScrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    _addLog('App started. Default ESP32 SoftAP IP: 192.168.4.1');
    _checkConnection();
  }

  @override
  void dispose() {
    _ipController.dispose();
    _logScrollController.dispose();
    super.dispose();
  }

  void _addLog(String message) {
    final timeStr = DateTime.now().toIso8601String().substring(11, 19);
    setState(() {
      _logs.add('[$timeStr] $message');
      if (_logs.length > 100) {
        _logs.removeAt(0);
      }
    });

    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_logScrollController.hasClients) {
        _logScrollController.animateTo(
          _logScrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      }
    });
  }

  String get _baseUrl {
    var ip = _ipController.text.trim();
    if (ip.isEmpty) ip = '192.168.4.1';
    if (!ip.startsWith('http://') && !ip.startsWith('https://')) {
      ip = 'http://$ip';
    }
    return ip;
  }

  Future<void> _checkConnection() async {
    setState(() => _isConnecting = true);
    _addLog('Checking connection to ESP32 at $_baseUrl...');

    try {
      final sw = Stopwatch()..start();
      final response = await http
          .get(Uri.parse('$_baseUrl/api/status'))
          .timeout(const Duration(seconds: 3));
      sw.stop();

      if (response.statusCode == 200) {
        setState(() {
          _isConnected = true;
          _isConnecting = false;
          _lastLatencyMs = sw.elapsedMilliseconds;
        });
        _addLog('Connected to ESP32! Latency: ${_lastLatencyMs}ms');
      } else {
        throw Exception('HTTP ${response.statusCode}');
      }
    } catch (e) {
      setState(() {
        _isConnected = false;
        _isConnecting = false;
      });
      _addLog('Connection status: Offline ($e)');
    }
  }

  void _showConnectionDialog() {
    showDialog(
      context: context,
      builder: (dialogCtx) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              backgroundColor: Colors.white,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(14),
                side: const BorderSide(color: Color(0xFFE2E8F0)),
              ),
              title: const Row(
                children: [
                  Icon(Icons.wifi_rounded, color: Color(0xFF2563EB), size: 20),
                  SizedBox(width: 8),
                  Text(
                    'ESP32 Connection',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: Color(0xFF0F172A),
                    ),
                  ),
                ],
              ),
              content: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'ESP32 Wi-Fi / SoftAP IP Address:',
                    style: TextStyle(fontSize: 12.5, color: Color(0xFF475569)),
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _ipController,
                    autofocus: true,
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 15,
                      fontWeight: FontWeight.bold,
                      color: Color(0xFF1D4ED8),
                    ),
                    decoration: InputDecoration(
                      isDense: true,
                      filled: true,
                      fillColor: const Color(0xFFF8FAFC),
                      hintText: '192.168.4.1',
                      contentPadding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 10,
                      ),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                        borderSide: const BorderSide(color: Color(0xFFCBD5E1)),
                      ),
                      enabledBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                        borderSide: const BorderSide(color: Color(0xFFCBD5E1)),
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                        borderSide: const BorderSide(
                          color: Color(0xFF2563EB),
                          width: 1.5,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Container(
                        width: 8,
                        height: 8,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: _isConnected
                              ? const Color(0xFF059669)
                              : const Color(0xFFDC2626),
                        ),
                      ),
                      const SizedBox(width: 6),
                      Text(
                        _isConnected
                            ? 'Connected (${_lastLatencyMs}ms)'
                            : 'Offline / Disconnected',
                        style: TextStyle(
                          fontSize: 12,
                          color: _isConnected
                              ? const Color(0xFF059669)
                              : const Color(0xFFDC2626),
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.of(dialogCtx).pop(),
                  child: const Text(
                    'Close',
                    style: TextStyle(color: Color(0xFF64748B)),
                  ),
                ),
                ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF2563EB),
                    foregroundColor: Colors.white,
                    elevation: 0,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8),
                    ),
                  ),
                  icon: _isConnecting
                      ? const SizedBox(
                          width: 14,
                          height: 14,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : const Icon(Icons.refresh_rounded, size: 16),
                  label: Text(_isConnecting ? 'Connecting...' : 'Test Connection'),
                  onPressed: _isConnecting
                      ? null
                      : () async {
                          await _checkConnection();
                          setDialogState(() {});
                        },
                ),
              ],
            );
          },
        );
      },
    );
  }

  void _showLogsDialog() {
    showDialog(
      context: context,
      builder: (ctx) {
        return Dialog(
          backgroundColor: Colors.white,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
            side: const BorderSide(color: Color(0xFFE2E8F0)),
          ),
          insetPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 12),
                child: Row(
                  children: [
                    const Icon(Icons.history_rounded,
                        color: Color(0xFF2563EB), size: 20),
                    const SizedBox(width: 8),
                    const Text(
                      'Modbus Activity Log',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                        color: Color(0xFF0F172A),
                      ),
                    ),
                    const Spacer(),
                    IconButton(
                      icon: const Icon(Icons.close_rounded, size: 18),
                      onPressed: () => Navigator.of(ctx).pop(),
                    ),
                  ],
                ),
              ),
              const Divider(height: 1, color: Color(0xFFE2E8F0)),
              Container(
                height: 350,
                color: const Color(0xFF0F172A),
                padding: const EdgeInsets.all(12),
                child: _logs.isEmpty
                    ? const Center(
                        child: Text(
                          'No communication logs yet.',
                          style: TextStyle(
                              color: Color(0xFF64748B), fontSize: 13),
                        ),
                      )
                    : SafeArea(
                        top: false,
                        child: ListView.builder(
                        controller: _logScrollController,
                        itemCount: _logs.length,
                        itemBuilder: (context, index) {
                          final line = _logs[index];
                          Color color = const Color(0xFFE2E8F0);
                          if (line.contains('TX ->')) {
                            color = const Color(0xFF60A5FA);
                          } else if (line.contains('RX <-') ||
                              line.contains('Connected')) {
                            color = const Color(0xFF4ADE80);
                          } else if (line.contains('Error') ||
                              line.contains('Offline')) {
                            color = const Color(0xFFF87171);
                          }
                          return Padding(
                            padding: const EdgeInsets.symmetric(vertical: 2),
                            child: Text(
                              line,
                              style: TextStyle(
                                fontFamily: 'monospace',
                                fontSize: 11.5,
                                color: color,
                              ),
                            ),
                          );
                        },
                      ),
                      ),
              ),
              const Divider(height: 1, color: Color(0xFFE2E8F0)),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      '${_logs.length} entries',
                      style: const TextStyle(
                          fontSize: 12, color: Color(0xFF64748B)),
                    ),
                    TextButton.icon(
                      icon: const Icon(Icons.delete_outline_rounded,
                          size: 16, color: Color(0xFF64748B)),
                      label: const Text('Clear',
                          style: TextStyle(
                              color: Color(0xFF64748B), fontSize: 12)),
                      onPressed: () {
                        setState(() => _logs.clear());
                        Navigator.of(ctx).pop();
                      },
                    ),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        titleSpacing: 12,
        bottom: const PreferredSize(
          preferredSize: Size.fromHeight(1),
          child: Divider(height: 1, color: Color(0xFFE2E8F0)),
        ),
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2.5),
              decoration: BoxDecoration(
                color: const Color(0xFFEFF6FF),
                borderRadius: BorderRadius.circular(6),
                border: Border.all(color: const Color(0xFFBFDBFE)),
              ),
              child: const Text(
                'GA700',
                style: TextStyle(
                  color: Color(0xFF1D4ED8),
                  fontWeight: FontWeight.bold,
                  fontSize: 11,
                  letterSpacing: 0.6,
                ),
              ),
            ),
            const SizedBox(width: 6),
            const Flexible(
              child: Text(
                'Parameter Explorer',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.bold,
                  color: Color(0xFF0F172A),
                ),
              ),
            ),
          ],
        ),
        actions: [
          // Compact Connection Chip
          InkWell(
            onTap: _showConnectionDialog,
            borderRadius: BorderRadius.circular(16),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: const Color(0xFFF1F5F9),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: const Color(0xFFE2E8F0)),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    width: 7,
                    height: 7,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: _isConnected
                          ? const Color(0xFF059669)
                          : const Color(0xFFDC2626),
                    ),
                  ),
                  const SizedBox(width: 5),
                  Text(
                    _ipController.text.trim().isEmpty
                        ? '192.168.4.1'
                        : _ipController.text.trim(),
                    style: TextStyle(
                      fontSize: 11,
                      fontFamily: 'monospace',
                      fontWeight: FontWeight.bold,
                      color: _isConnected
                          ? const Color(0xFF0F172A)
                          : const Color(0xFF64748B),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(width: 4),

          // Logs Button
          IconButton(
            tooltip: 'Activity Logs',
            icon: const Icon(
              Icons.history_rounded,
              color: Color(0xFF475569),
              size: 20,
            ),
            onPressed: _showLogsDialog,
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: ParamExplorerScreen(
        baseUrl: _baseUrl,
        isConnected: _isConnected,
        onLog: _addLog,
      ),
    );
  }
}
