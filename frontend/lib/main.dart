import 'dart:async';
import 'dart:convert';
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
      title: 'Yaskawa GA700 VFD Controller',
      debugShowCheckedModeBanner: false,
      themeMode: ThemeMode.dark,
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF0D1117),
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFF00F0FF), // Neon Cyan
          secondary: Color(0xFF10B981), // Emerald Green
          surface: Color(0xFF161B22),
          error: Color(0xFFEF4444),
        ),
        fontFamily: 'Segoe UI',
        useMaterial3: true,
      ),
      home: const DashboardScreen(),
    );
  }
}

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  // Connection state
  final TextEditingController _ipController =
      TextEditingController(text: '192.168.4.1');
  bool _isConnected = false;
  bool _isConnecting = false;
  bool _autoPoll = true;
  Timer? _pollTimer;
  final int _pollIntervalSeconds = 1;
  int _selectedNavIndex = 0;

  // Telemetry data
  double _readFreqU1_01 = 0.0;
  int _readRawU1_01 = 0;
  double _outputFreqU1_02 = 0.0;
  double _outputCurrentU1_03 = 0.0;
  double _voltageV = 0.0;
  bool _isDriveRunning = false;
  bool _isDriveReady = false;
  DateTime? _lastReadTime;
  int _lastLatencyMs = 0;

  // Write controls
  final TextEditingController _writeFreqController =
      TextEditingController(text: '50.00');
  double _sliderFreq = 50.0;
  bool _isWritingFreq = false;
  bool _isSendingCmd = false;

  // Activity logs
  final List<String> _logs = [];
  final ScrollController _logScrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    _addLog('App started. Default ESP32 SoftAP IP: 192.168.4.1');
    // Start auto-connect check
    _checkConnection();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _ipController.dispose();
    _writeFreqController.dispose();
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
    _addLog('Connecting to ESP32 at $_baseUrl...');

    try {
      final sw = Stopwatch()..start();
      final response = await http
          .get(Uri.parse('$_baseUrl/api/status'))
          .timeout(const Duration(seconds: 3));
      sw.stop();

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _isConnected = true;
          _isConnecting = false;
          _lastLatencyMs = sw.elapsedMilliseconds;
          _parseStatusData(data);
        });
        _addLog('Connected to ESP32! Latency: ${_lastLatencyMs}ms');
        _startPolling();
      } else {
        throw Exception('HTTP ${response.statusCode}');
      }
    } catch (e) {
      setState(() {
        _isConnected = false;
        _isConnecting = false;
      });
      _addLog('Connection failed: $e');
    }
  }

  void _startPolling() {
    _pollTimer?.cancel();
    if (!_autoPoll || !_isConnected) return;

    _pollTimer = Timer.periodic(
      Duration(seconds: _pollIntervalSeconds),
      (_) => _pollStatus(),
    );
  }

  void _stopPolling() {
    _pollTimer?.cancel();
    _pollTimer = null;
  }

  Future<void> _pollStatus() async {
    if (!_isConnected) return;
    try {
      final sw = Stopwatch()..start();
      final response = await http
          .get(Uri.parse('$_baseUrl/api/status'))
          .timeout(const Duration(seconds: 2));
      sw.stop();

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _lastLatencyMs = sw.elapsedMilliseconds;
          _parseStatusData(data);
        });
      }
    } catch (_) {
      // Quiet fail on periodic poll; consecutive fails will reflect status
    }
  }

  void _parseStatusData(Map<String, dynamic> data) {
    if (data.containsKey('u1_01_freq_ref_hz')) {
      _readFreqU1_01 = (data['u1_01_freq_ref_hz'] as num).toDouble();
    }
    if (data.containsKey('u1_01_raw')) {
      _readRawU1_01 = (data['u1_01_raw'] as num).toInt();
    }
    if (data.containsKey('u1_02_output_freq_hz')) {
      _outputFreqU1_02 = (data['u1_02_output_freq_hz'] as num).toDouble();
    }
    if (data.containsKey('u1_03_current_a')) {
      _outputCurrentU1_03 = (data['u1_03_current_a'] as num).toDouble();
    }
    if (data.containsKey('voltage_v')) {
      _voltageV = (data['voltage_v'] as num).toDouble();
    }
    if (data.containsKey('is_running')) {
      _isDriveRunning = data['is_running'] == true;
    }
    if (data.containsKey('is_ready')) {
      _isDriveReady = data['is_ready'] == true;
    }
    _lastReadTime = DateTime.now();
  }

  // ==========================================================================
  // Direct Read U1-01 (0x0040)
  // ==========================================================================
  Future<void> _readFrequencyU1_01() async {
    _addLog('TX -> GET /api/frequency (Reading U1-01 / 0x0040)...');
    try {
      final sw = Stopwatch()..start();
      final response = await http
          .get(Uri.parse('$_baseUrl/api/frequency'))
          .timeout(const Duration(seconds: 3));
      sw.stop();

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final freq = (data['frequency_hz'] as num).toDouble();
        final raw = (data['raw_value'] as num).toInt();

        setState(() {
          _readFreqU1_01 = freq;
          _readRawU1_01 = raw;
          _lastReadTime = DateTime.now();
          _lastLatencyMs = sw.elapsedMilliseconds;
          _isConnected = true;
        });

        _addLog(
            'RX <- U1-01 (0x0040) = ${freq.toStringAsFixed(2)} Hz (Raw: $raw / 0x${raw.toRadixString(16).toUpperCase()})');
        _showSnackbar('Read U1-01: ${freq.toStringAsFixed(2)} Hz',
            isSuccess: true);
      } else {
        throw Exception('Status ${response.statusCode}: ${response.body}');
      }
    } catch (e) {
      _addLog('RX Error reading U1-01: $e');
      _showSnackbar('Failed to read U1-01: $e', isSuccess: false);
    }
  }

  // ==========================================================================
  // Direct Write d1-01 (0x0280)
  // ==========================================================================
  Future<void> _writeFrequencyD1_01(double targetFreq) async {
    setState(() => _isWritingFreq = true);
    final rawVal = (targetFreq * 100.0).round();
    _addLog(
        'TX -> POST /api/frequency target=${targetFreq.toStringAsFixed(2)} Hz (d1-01 & Active Ref -> U1-01)...');

    try {
      final sw = Stopwatch()..start();
      final response = await http
          .post(
            Uri.parse('$_baseUrl/api/frequency'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({
              'frequency': targetFreq,
              'raw': rawVal,
            }),
          )
          .timeout(const Duration(seconds: 3));
      sw.stop();

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        _addLog(
            'RX <- Frequency Write SUCCESS: ${data['frequency_hz']} Hz (d1-01 & Active Ref updated)');
        _showSnackbar(
            'Set ${targetFreq.toStringAsFixed(2)} Hz to d1-01 & updated U1-01!',
            isSuccess: true);
        // Refresh reading
        await _readFrequencyU1_01();
      } else {
        throw Exception('Status ${response.statusCode}: ${response.body}');
      }
    } catch (e) {
      _addLog('RX Error writing d1-01: $e');
      _showSnackbar('Failed to write d1-01: $e', isSuccess: false);
    } finally {
      setState(() => _isWritingFreq = false);
    }
  }

  // ==========================================================================
  // Drive RUN / STOP Controls
  // ==========================================================================
  Future<void> _sendDriveCommand(String cmd) async {
    setState(() => _isSendingCmd = true);
    _addLog('TX -> POST /api/$cmd...');

    try {
      final response = await http
          .post(Uri.parse('$_baseUrl/api/$cmd'))
          .timeout(const Duration(seconds: 3));

      if (response.statusCode == 200) {
        setState(() {
          _isDriveRunning = (cmd == 'run');
        });
        _addLog('RX <- Drive command $cmd executed successfully!');
        _showSnackbar('Drive command: ${cmd.toUpperCase()}', isSuccess: true);
        await _pollStatus();
      } else {
        throw Exception('Status ${response.statusCode}: ${response.body}');
      }
    } catch (e) {
      _addLog('RX Error sending $cmd: $e');
      _showSnackbar('Command $cmd failed: $e', isSuccess: false);
    } finally {
      setState(() => _isSendingCmd = false);
    }
  }

  void _showSnackbar(String message, {required bool isSuccess}) {
    ScaffoldMessenger.of(context).hideCurrentSnackBar();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            Icon(
              isSuccess ? Icons.check_circle : Icons.error_outline,
              color: isSuccess
                  ? const Color(0xFF10B981)
                  : const Color(0xFFEF4444),
            ),
            const SizedBox(width: 10),
            Expanded(child: Text(message)),
          ],
        ),
        backgroundColor: const Color(0xFF1E293B),
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 2),
      ),
    );
  }

  // ==========================================================================
  // UI Layout
  // ==========================================================================
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: const Color(0xFF161B22),
        elevation: 0,
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
              decoration: BoxDecoration(
                color: const Color(0xFF00F0FF).withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(6),
                border: Border.all(
                    color: const Color(0xFF00F0FF).withValues(alpha: 0.4)),
              ),
              child: const Text(
                'GA700',
                style: TextStyle(
                  color: Color(0xFF00F0FF),
                  fontWeight: FontWeight.bold,
                  fontSize: 14,
                  letterSpacing: 1.2,
                ),
              ),
            ),
            const SizedBox(width: 12),
            const Expanded(
              child: Text(
                'Yaskawa RS-485 Controller',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
        actions: [
          _buildConnectionIndicator(),
          const SizedBox(width: 16),
        ],
      ),
      body: IndexedStack(
        index: _selectedNavIndex,
        children: [
          SingleChildScrollView(
            padding: const EdgeInsets.all(16.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _buildConnectionCard(),
                const SizedBox(height: 16),
                LayoutBuilder(
                  builder: (context, constraints) {
                    if (constraints.maxWidth > 700) {
                      return Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(child: _buildReadCard()),
                          const SizedBox(width: 16),
                          Expanded(child: _buildWriteCard()),
                        ],
                      );
                    } else {
                      return Column(
                        children: [
                          _buildReadCard(),
                          const SizedBox(height: 16),
                          _buildWriteCard(),
                        ],
                      );
                    }
                  },
                ),
                const SizedBox(height: 16),
                _buildDriveControlCard(),
                const SizedBox(height: 16),
                _buildTelemetryRow(),
                const SizedBox(height: 16),
                _buildActivityLogCard(),
              ],
            ),
          ),
          ParamExplorerScreen(
            baseUrl: _baseUrl,
            isConnected: _isConnected,
            onLog: _addLog,
          ),
        ],
      ),
      bottomNavigationBar: Container(
        decoration: const BoxDecoration(
          color: Color(0xFF161B22),
          border: Border(top: BorderSide(color: Color(0xFF30363D))),
        ),
        child: NavigationBar(
          backgroundColor: const Color(0xFF161B22),
          indicatorColor: const Color(0xFF00F0FF).withValues(alpha: 0.2),
          selectedIndex: _selectedNavIndex,
          onDestinationSelected: (idx) => setState(() => _selectedNavIndex = idx),
          destinations: const [
            NavigationDestination(
              icon: Icon(Icons.speed_rounded, color: Color(0xFF8B949E)),
              selectedIcon: Icon(Icons.speed_rounded, color: Color(0xFF00F0FF)),
              label: 'VFD Dashboard',
            ),
            NavigationDestination(
              icon: Icon(Icons.tune_rounded, color: Color(0xFF8B949E)),
              selectedIcon: Icon(Icons.tune_rounded, color: Color(0xFF00F0FF)),
              label: 'Parameter Explorer (1,003)',
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildConnectionIndicator() {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: _isConnected
                ? const Color(0xFF10B981)
                : const Color(0xFFEF4444),
            boxShadow: [
              BoxShadow(
                color: (_isConnected
                        ? const Color(0xFF10B981)
                        : const Color(0xFFEF4444))
                    .withValues(alpha: 0.6),
                blurRadius: 8,
                spreadRadius: 2,
              )
            ],
          ),
        ),
        const SizedBox(width: 8),
        Text(
          _isConnected ? 'ONLINE (${_lastLatencyMs}ms)' : 'OFFLINE',
          style: TextStyle(
            color: _isConnected
                ? const Color(0xFF10B981)
                : const Color(0xFFEF4444),
            fontWeight: FontWeight.bold,
            fontSize: 12,
          ),
        ),
      ],
    );
  }

  // ==========================================================================
  // Connection Card
  // ==========================================================================
  Widget _buildConnectionCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF30363D)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.wifi, color: Color(0xFF00F0FF), size: 20),
              const SizedBox(width: 8),
              const Text(
                'ESP32 Wi-Fi & Target Configuration',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
              ),
              const Spacer(),
              Row(
                children: [
                  const Text('Auto-Poll: ', style: TextStyle(fontSize: 12)),
                  Switch(
                    value: _autoPoll,
                    activeThumbColor: const Color(0xFF00F0FF),
                    onChanged: (val) {
                      setState(() => _autoPoll = val);
                      if (val) {
                        _startPolling();
                      } else {
                        _stopPolling();
                      }
                    },
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _ipController,
                  decoration: InputDecoration(
                    labelText: 'ESP32 IP Address',
                    hintText: '192.168.4.1',
                    prefixIcon: const Icon(Icons.router_outlined, size: 20),
                    isDense: true,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                      borderSide: const BorderSide(color: Color(0xFF30363D)),
                    ),
                    filled: true,
                    fillColor: const Color(0xFF0D1117),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              ElevatedButton.icon(
                onPressed: _isConnecting ? null : _checkConnection,
                style: ElevatedButton.styleFrom(
                  backgroundColor: _isConnected
                      ? const Color(0xFF1F2937)
                      : const Color(0xFF00F0FF),
                  foregroundColor:
                      _isConnected ? Colors.white : Colors.black,
                  padding: const EdgeInsets.symmetric(
                      horizontal: 20, vertical: 15),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8)),
                ),
                icon: _isConnecting
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : Icon(_isConnected ? Icons.refresh : Icons.link),
                label: Text(
                  _isConnected ? 'Refresh' : 'Connect',
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            children: [
              _buildIpChip('192.168.4.1 (ESP32 SoftAP)'),
              _buildIpChip('192.168.1.100'),
              _buildIpChip('localhost'),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildIpChip(String label) {
    final ipOnly = label.split(' ').first;
    return ActionChip(
      label: Text(label, style: const TextStyle(fontSize: 11)),
      backgroundColor: const Color(0xFF0D1117),
      side: const BorderSide(color: Color(0xFF30363D)),
      onPressed: () {
        _ipController.text = ipOnly;
        _checkConnection();
      },
    );
  }

  // ==========================================================================
  // Frequency Read Card (U1-01 / 0x0040)
  // ==========================================================================
  Widget _buildReadCard() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: const Color(0xFF00F0FF).withValues(alpha: 0.3),
        ),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFF00F0FF).withValues(alpha: 0.05),
            blurRadius: 15,
            spreadRadius: 2,
          )
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: const Color(0xFF00F0FF).withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: const Text(
                  'READ ONLY',
                  style: TextStyle(
                    color: Color(0xFF00F0FF),
                    fontWeight: FontWeight.bold,
                    fontSize: 11,
                  ),
                ),
              ),
              const Spacer(),
              const Text(
                'Param: U1-01  |  Addr: 0x0040',
                style: TextStyle(
                  color: Color(0xFF8B949E),
                  fontFamily: 'Courier',
                  fontSize: 12,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          const Text(
            'FREQUENCY MONITOR (U1-01)',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: Color(0xFF8B949E),
              letterSpacing: 1.0,
            ),
          ),
          const SizedBox(height: 10),
          Center(
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.baseline,
              textBaseline: TextBaseline.alphabetic,
              children: [
                Text(
                  _readFreqU1_01.toStringAsFixed(2),
                  style: const TextStyle(
                    fontSize: 48,
                    fontWeight: FontWeight.bold,
                    color: Color(0xFF00F0FF),
                    fontFamily: 'Courier',
                  ),
                ),
                const SizedBox(width: 8),
                const Text(
                  'Hz',
                  style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.w600,
                    color: Color(0xFF8B949E),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 8),
          Center(
            child: Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                color: const Color(0xFF0D1117),
                borderRadius: BorderRadius.circular(6),
                border: Border.all(color: const Color(0xFF30363D)),
              ),
              child: Text(
                'Raw Register: $_readRawU1_01  (0x${_readRawU1_01.toRadixString(16).padLeft(4, '0').toUpperCase()})',
                style: const TextStyle(
                  fontFamily: 'Courier',
                  fontSize: 12,
                  color: Color(0xFF8B949E),
                ),
              ),
            ),
          ),
          const SizedBox(height: 6),
          Center(
            child: Text(
              _lastReadTime != null
                  ? 'Last updated: ${_lastReadTime!.toLocal().toString().substring(11, 19)}'
                  : 'Status: Not polled yet',
              style: const TextStyle(
                fontSize: 11,
                color: Color(0xFF6E7681),
                fontFamily: 'Courier',
              ),
            ),
          ),
          const SizedBox(height: 12),
          // Speed bar
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: (_readFreqU1_01 / 60.0).clamp(0.0, 1.0),
              backgroundColor: const Color(0xFF0D1117),
              color: const Color(0xFF00F0FF),
              minHeight: 8,
            ),
          ),
          const SizedBox(height: 16),
          ElevatedButton.icon(
            onPressed: _readFrequencyU1_01,
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF00F0FF).withValues(alpha: 0.2),
              foregroundColor: const Color(0xFF00F0FF),
              side: const BorderSide(color: Color(0xFF00F0FF)),
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(8)),
            ),
            icon: const Icon(Icons.sensors, size: 20),
            label: const Text(
              'READ U1-01 (0x0040) NOW',
              style: TextStyle(fontWeight: FontWeight.bold),
            ),
          ),
        ],
      ),
    );
  }

  // ==========================================================================
  // Frequency Write Card (d1-01 / 0x0280)
  // ==========================================================================
  Widget _buildWriteCard() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: const Color(0xFF10B981).withValues(alpha: 0.3),
        ),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFF10B981).withValues(alpha: 0.05),
            blurRadius: 15,
            spreadRadius: 2,
          )
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: const Color(0xFF10B981).withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: const Text(
                  'WRITE / COMMAND',
                  style: TextStyle(
                    color: Color(0xFF10B981),
                    fontWeight: FontWeight.bold,
                    fontSize: 11,
                  ),
                ),
              ),
              const Spacer(),
              const Text(
                'Param: d1-01  |  Addr: 0x0280',
                style: TextStyle(
                  color: Color(0xFF8B949E),
                  fontFamily: 'Courier',
                  fontSize: 12,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          const Text(
            'FREQUENCY REFERENCE 1 (d1-01)',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: Color(0xFF8B949E),
              letterSpacing: 1.0,
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              _buildStepButton('-5', -5.0),
              const SizedBox(width: 6),
              _buildStepButton('-1', -1.0),
              const SizedBox(width: 8),
              Expanded(
                child: TextField(
                  controller: _writeFreqController,
                  keyboardType:
                      const TextInputType.numberWithOptions(decimal: true),
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                    color: Color(0xFF10B981),
                    fontFamily: 'Courier',
                  ),
                  decoration: InputDecoration(
                    suffixText: 'Hz',
                    isDense: true,
                    contentPadding: const EdgeInsets.symmetric(
                        vertical: 10, horizontal: 8),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                      borderSide:
                          const BorderSide(color: Color(0xFF30363D)),
                    ),
                    filled: true,
                    fillColor: const Color(0xFF0D1117),
                  ),
                  onChanged: (val) {
                    final d = double.tryParse(val);
                    if (d != null && d >= 0 && d <= 400) {
                      setState(() => _sliderFreq = d.clamp(0.0, 60.0));
                    }
                  },
                ),
              ),
              const SizedBox(width: 8),
              _buildStepButton('+1', 1.0),
              const SizedBox(width: 6),
              _buildStepButton('+5', 5.0),
            ],
          ),
          const SizedBox(height: 12),
          SliderTheme(
            data: SliderTheme.of(context).copyWith(
              activeTrackColor: const Color(0xFF10B981),
              thumbColor: const Color(0xFF10B981),
              inactiveTrackColor: const Color(0xFF0D1117),
              trackHeight: 6,
            ),
            child: Slider(
              value: _sliderFreq.clamp(0.0, 60.0),
              min: 0.0,
              max: 60.0,
              divisions: 120,
              label: '${_sliderFreq.toStringAsFixed(1)} Hz',
              onChanged: (val) {
                setState(() {
                  _sliderFreq = val;
                  _writeFreqController.text = val.toStringAsFixed(2);
                });
              },
            ),
          ),
          // Preset Buttons
          Wrap(
            alignment: WrapAlignment.center,
            spacing: 6,
            runSpacing: 6,
            children: [10.0, 20.0, 30.0, 40.0, 50.0, 60.0].map((hz) {
              return SizedBox(
                height: 28,
                child: OutlinedButton(
                  onPressed: () {
                    setState(() {
                      _sliderFreq = hz;
                      _writeFreqController.text = hz.toStringAsFixed(2);
                    });
                  },
                  style: OutlinedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(horizontal: 10),
                    side: const BorderSide(color: Color(0xFF30363D)),
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(6)),
                  ),
                  child: Text('${hz.toInt()} Hz',
                      style: const TextStyle(fontSize: 11)),
                ),
              );
            }).toList(),
          ),
          const SizedBox(height: 16),
          ElevatedButton.icon(
            onPressed: _isWritingFreq
                ? null
                : () {
                    final hz = double.tryParse(_writeFreqController.text);
                    if (hz != null) {
                      _writeFrequencyD1_01(hz);
                    } else {
                      _showSnackbar('Invalid frequency value', isSuccess: false);
                    }
                  },
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF10B981),
              foregroundColor: Colors.black,
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(8)),
            ),
            icon: _isWritingFreq
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(
                        strokeWidth: 2, color: Colors.black),
                  )
                : const Icon(Icons.flash_on, size: 20),
            label: Text(
              _isWritingFreq
                  ? 'WRITING TO 0x0280...'
                  : 'WRITE FREQUENCY TO d1-01 (0x0280)',
              style: const TextStyle(fontWeight: FontWeight.bold),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStepButton(String text, double delta) {
    return SizedBox(
      width: 36,
      height: 38,
      child: OutlinedButton(
        onPressed: () {
          double current = double.tryParse(_writeFreqController.text) ?? 50.0;
          current = (current + delta).clamp(0.0, 400.0);
          setState(() {
            _writeFreqController.text = current.toStringAsFixed(2);
            _sliderFreq = current.clamp(0.0, 60.0);
          });
        },
        style: OutlinedButton.styleFrom(
          padding: EdgeInsets.zero,
          side: const BorderSide(color: Color(0xFF30363D)),
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
        ),
        child: Text(text, style: const TextStyle(fontSize: 11)),
      ),
    );
  }

  // ==========================================================================
  // Drive Control Card (RUN / STOP)
  // ==========================================================================
  Widget _buildDriveControlCard() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFF30363D)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.settings_remote,
                  color: Color(0xFF00F0FF), size: 20),
              const SizedBox(width: 8),
              const Text(
                'Drive Operation Command (Register 0x0001)',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
              ),
              const Spacer(),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: _isDriveReady
                      ? const Color(0xFF00F0FF).withValues(alpha: 0.15)
                      : const Color(0xFF6E7681).withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  _isDriveReady ? 'READY' : 'STANDBY',
                  style: TextStyle(
                    color: _isDriveReady
                        ? const Color(0xFF00F0FF)
                        : const Color(0xFF8B949E),
                    fontWeight: FontWeight.bold,
                    fontSize: 12,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: _isDriveRunning
                      ? const Color(0xFF10B981).withValues(alpha: 0.2)
                      : const Color(0xFFEF4444).withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  _isDriveRunning ? 'STATE: RUNNING' : 'STATE: STOPPED',
                  style: TextStyle(
                    color: _isDriveRunning
                        ? const Color(0xFF10B981)
                        : const Color(0xFFEF4444),
                    fontWeight: FontWeight.bold,
                    fontSize: 12,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: ElevatedButton.icon(
                  onPressed:
                      _isSendingCmd ? null : () => _sendDriveCommand('run'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF10B981),
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 18),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(10),
                    ),
                    elevation: _isDriveRunning ? 8 : 2,
                    shadowColor:
                        const Color(0xFF10B981).withValues(alpha: 0.5),
                  ),
                  icon: const Icon(Icons.play_arrow, size: 28),
                  label: const Text(
                    'RUN DRIVE (FORWARD)',
                    style: TextStyle(
                        fontSize: 15, fontWeight: FontWeight.bold),
                  ),
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: ElevatedButton.icon(
                  onPressed:
                      _isSendingCmd ? null : () => _sendDriveCommand('stop'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFFEF4444),
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 18),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(10),
                    ),
                  ),
                  icon: const Icon(Icons.stop, size: 28),
                  label: const Text(
                    'STOP DRIVE',
                    style: TextStyle(
                        fontSize: 15, fontWeight: FontWeight.bold),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  // ==========================================================================
  // Telemetry Row
  // ==========================================================================
  Widget _buildTelemetryRow() {
    return Row(
      children: [
        Expanded(
          child: _buildTelemetryTile(
            title: 'Output Current (U1-03)',
            addr: '0x0042',
            value: '${_outputCurrentU1_03.toStringAsFixed(2)} A',
            icon: Icons.electric_meter,
            color: const Color(0xFFF59E0B),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _buildTelemetryTile(
            title: 'Output Freq (U1-02)',
            addr: '0x0041',
            value: '${_outputFreqU1_02.toStringAsFixed(2)} Hz',
            icon: Icons.speed,
            color: const Color(0xFF00F0FF),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _buildTelemetryTile(
            title: 'Drive Voltage',
            addr: '0x0025',
            value: '${_voltageV.toStringAsFixed(1)} V',
            icon: Icons.bolt,
            color: const Color(0xFF8B5CF6),
          ),
        ),
      ],
    );
  }

  Widget _buildTelemetryTile({
    required String title,
    required String addr,
    required String value,
    required IconData icon,
    required Color color,
  }) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF30363D)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 16, color: color),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(
                      fontSize: 11, color: Color(0xFF8B949E)),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            value,
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.bold,
              color: color,
              fontFamily: 'Courier',
            ),
          ),
          Text(
            'Addr: $addr',
            style: const TextStyle(
              fontSize: 10,
              color: Color(0xFF6E7681),
              fontFamily: 'Courier',
            ),
          ),
        ],
      ),
    );
  }

  // ==========================================================================
  // Activity / Modbus Console Card
  // ==========================================================================
  Widget _buildActivityLogCard() {
    return Container(
      height: 180,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFF0D1117),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF30363D)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.terminal, size: 16, color: Color(0xFF8B949E)),
              const SizedBox(width: 8),
              const Text(
                'Communication & Modbus Activity Log',
                style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    color: Color(0xFF8B949E)),
              ),
              const Spacer(),
              TextButton(
                onPressed: () => setState(() => _logs.clear()),
                style: TextButton.styleFrom(
                  padding: EdgeInsets.zero,
                  minimumSize: const Size(50, 24),
                ),
                child: const Text('Clear', style: TextStyle(fontSize: 11)),
              ),
            ],
          ),
          const Divider(color: Color(0xFF21262D), height: 12),
          Expanded(
            child: ListView.builder(
              controller: _logScrollController,
              itemCount: _logs.length,
              itemBuilder: (context, index) {
                final line = _logs[index];
                Color lineColor = const Color(0xFFC9D1D9);
                if (line.contains('TX ->')) {
                  lineColor = const Color(0xFF58A6FF);
                } else if (line.contains('RX <-') || line.contains('SUCCESS')) {
                  lineColor = const Color(0xFF7EE787);
                } else if (line.contains('Error') || line.contains('failed')) {
                  lineColor = const Color(0xFFFFA198);
                }
                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 2),
                  child: Text(
                    line,
                    style: TextStyle(
                      fontFamily: 'Courier',
                      fontSize: 11,
                      color: lineColor,
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
