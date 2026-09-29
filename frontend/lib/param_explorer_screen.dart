// AUTO-GENERATED FILE BY generate_code.py - DO NOT EDIT MANUALLY
// Yaskawa GA700 Parameter Explorer (Drill-Down Multi-Page Navigation with Back Option)

import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:visibility_detector/visibility_detector.dart';
import 'generated_params_data.dart';

// =============================================================================
// State Management: Reactive Param Store & Smooth Refresh Widget
// =============================================================================

class ParamLiveStore extends ChangeNotifier {
  final Map<String, ParamLiveState> _states = {};
  final Set<String> _loading = {};

  final Map<String, ValueNotifier<ParamLiveState?>> _notifiers = {};
  final Map<String, ValueNotifier<bool>> _loadingNotifiers = {};

  ParamLiveState? getState(String hex) => _states[hex];
  bool isLoading(String hex) => _loading.contains(hex);

  ValueNotifier<ParamLiveState?> getNotifier(String hex) {
    return _notifiers.putIfAbsent(hex, () => ValueNotifier<ParamLiveState?>(_states[hex]));
  }

  ValueNotifier<bool> getLoadingNotifier(String hex) {
    return _loadingNotifiers.putIfAbsent(hex, () => ValueNotifier<bool>(_loading.contains(hex)));
  }

  void setLoading(String hex, bool loading) {
    if (loading) {
      _loading.add(hex);
    } else {
      _loading.remove(hex);
    }
    _loadingNotifiers[hex]?.value = loading;
  }

  void updateState(String hex, ParamLiveState state) {
    _states[hex] = state;
    _notifiers[hex]?.value = state;
  }
}

class RotatingRefreshIcon extends StatefulWidget {
  final double size;
  final Color color;

  const RotatingRefreshIcon({super.key, this.size = 13, this.color = const Color(0xFF2563EB)});

  @override
  State<RotatingRefreshIcon> createState() => _RotatingRefreshIconState();
}

class _RotatingRefreshIconState extends State<RotatingRefreshIcon>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return RotationTransition(
      turns: _controller,
      child: Icon(Icons.sync_rounded, size: widget.size, color: widget.color),
    );
  }
}

/// Level 1 Screen: Lists all Outer Layers (Sections) from params.json
class ParamExplorerScreen extends StatefulWidget {
  final String baseUrl;
  final bool isConnected;
  final Function(String message)? onLog;

  const ParamExplorerScreen({
    super.key,
    required this.baseUrl,
    required this.isConnected,
    this.onLog,
  });

  @override
  State<ParamExplorerScreen> createState() => _ParamExplorerScreenState();
}

class _ParamExplorerScreenState extends State<ParamExplorerScreen> {
  final TextEditingController _globalSearchController = TextEditingController();
  String _globalQuery = '';

  // Shared reactive store across all screens
  final ParamLiveStore _store = ParamLiveStore();

  // Track visible elements in search results
  final Set<String> _searchVisibleAddresses = {};
  Timer? _searchPollingTimer;
  bool _isSearchPollingActive = false;

  @override
  void initState() {
    super.initState();
    _searchPollingTimer = Timer.periodic(const Duration(milliseconds: 1500), (_) {
      if (!_isSearchPollingActive && mounted && _globalQuery.isNotEmpty) {
        _pollSearchVisibleElements();
      }
    });
  }

  @override
  void dispose() {
    _searchPollingTimer?.cancel();
    _globalSearchController.dispose();
    super.dispose();
  }

  Future<void> _pollSearchVisibleElements() async {
    if (_searchVisibleAddresses.isEmpty || !mounted || _isSearchPollingActive) return;
    _isSearchPollingActive = true;

    final addressesToPoll = _searchVisibleAddresses.toList();
    for (final addrHex in addressesToPoll) {
      if (!mounted || !_searchVisibleAddresses.contains(addrHex)) continue;

      _store.setLoading(addrHex, true);

      try {
        final uri = Uri.parse('${widget.baseUrl}/api/param?addr=$addrHex');
        final res = await http.get(uri).timeout(const Duration(seconds: 3));

        if (res.statusCode == 200) {
          final data = jsonDecode(res.body);
          if (data['status'] == 'error' || data['value'] == null) {
            throw Exception(data['message'] ?? data['error'] ?? 'ESP32 error');
          }
          final rawVal = (data['value'] as num).toInt();
          final hexVal = data['hex_value']?.toString() ??
              '0x${rawVal.toRadixString(16).padLeft(4, '0').toUpperCase()}';

          if (mounted) {
            _store.updateState(
              addrHex,
              ParamLiveState(
                decimalValue: rawVal,
                hexValue: hexVal,
                readTime: DateTime.now(),
                hasError: false,
              ),
            );
          }
        } else {
          String msg = 'HTTP ${res.statusCode}';
          try {
            final errBody = jsonDecode(res.body);
            if (errBody['message'] != null) msg = errBody['message'];
          } catch (_) {}
          throw Exception(msg);
        }
      } catch (e) {
        String cleanErr = e.toString()
            .replaceAll('Exception: ', '')
            .replaceAll('ClientException: ', '')
            .replaceAll('Failed host lookup:', 'Unreachable:');
        if (cleanErr.length > 25) cleanErr = cleanErr.substring(0, 25);
        if (mounted) {
          _store.updateState(
            addrHex,
            ParamLiveState(
              decimalValue: null,
              hexValue: null,
              readTime: DateTime.now(),
              hasError: true,
              errorMessage: cleanErr,
            ),
          );
        }
      } finally {
        if (mounted) {
          _store.setLoading(addrHex, false);
        }
      }
      await Future.delayed(const Duration(milliseconds: 40));
    }

    _isSearchPollingActive = false;
  }

  void _openSection(YaskawaSection section) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (ctx) => SectionParamsScreen(
          section: section,
          baseUrl: widget.baseUrl,
          isConnected: widget.isConnected,
          onLog: widget.onLog,
          store: _store,
        ),
      ),
    );
  }

  List<YaskawaParam> _getAllMatchingParams(String query) {
    final q = query.trim().toLowerCase();
    if (q.isEmpty) return [];

    final List<YaskawaParam> matches = [];
    for (final sec in kYaskawaSections) {
      for (final grp in sec.subGroups) {
        for (final p in grp.params) {
          if (p.code.toLowerCase().contains(q) ||
              p.name.toLowerCase().contains(q) ||
              p.hexAddress.toLowerCase().contains(q) ||
              p.address.toString().contains(q)) {
            matches.add(p);
          }
        }
      }
    }
    return matches;
  }

  @override
  Widget build(BuildContext context) {
    final searchMatches = _getAllMatchingParams(_globalQuery);

    return ColoredBox(
      color: const Color(0xFFF8FAFC),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Header with Title & Full-Width Search Bar
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: const BoxDecoration(
              color: Colors.white,
              border: Border(bottom: BorderSide(color: Color(0xFFE2E8F0))),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(6),
                      decoration: BoxDecoration(
                        color: const Color(0xFFEFF6FF),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: const Icon(
                        Icons.layers_rounded,
                        color: Color(0xFF2563EB),
                        size: 20,
                      ),
                    ),
                    const SizedBox(width: 10),
                    const Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'SECTIONS (OUTER LAYER)',
                            style: TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.bold,
                              letterSpacing: 0.5,
                              color: Color(0xFF0F172A),
                            ),
                          ),
                          Text(
                            '14 Categories • 1,003 Modbus Parameters',
                            style: TextStyle(
                              fontSize: 11.5,
                              color: Color(0xFF64748B),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                // Full-width search bar
                SizedBox(
                  height: 38,
                  child: TextField(
                    controller: _globalSearchController,
                    onChanged: (val) => setState(() => _globalQuery = val),
                    style: const TextStyle(fontSize: 13, color: Color(0xFF0F172A)),
                    decoration: InputDecoration(
                      isDense: true,
                      filled: true,
                      fillColor: const Color(0xFFF8FAFC),
                      hintText: 'Search all 1,003 parameters (e.g. b1-01, carrier, 0x0180)...',
                      hintStyle: const TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
                      prefixIcon: const Icon(Icons.search, size: 18, color: Color(0xFF64748B)),
                      suffixIcon: _globalQuery.isNotEmpty
                          ? IconButton(
                              icon: const Icon(Icons.clear, size: 16, color: Color(0xFF64748B)),
                              onPressed: () {
                                _globalSearchController.clear();
                                setState(() => _globalQuery = '');
                              },
                            )
                          : null,
                      contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
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
                        borderSide: const BorderSide(color: Color(0xFF2563EB), width: 1.5),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),

          // Content: Search Results OR List of Outer Layer Sections
          Expanded(
            child: _globalQuery.isNotEmpty
                ? _buildSearchResults(searchMatches)
                : _buildSectionsList(),
          ),
        ],
      ),
    );
  }

  Widget _buildSectionsList() {
    return SafeArea(
      top: false,
      child: ListView.separated(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      itemCount: kYaskawaSections.length,
      separatorBuilder: (context, index) => const SizedBox(height: 8),
      itemBuilder: (context, index) {
        final section = kYaskawaSections[index];
        final totalParams = section.totalParamsCount;
        final subGroupCount = section.subGroups.length;

        return Material(
          color: Colors.white,
          borderRadius: BorderRadius.circular(10),
          child: InkWell(
            onTap: () => _openSection(section),
            borderRadius: BorderRadius.circular(10),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: const Color(0xFFE2E8F0)),
              ),
              child: Row(
                children: [
                  Container(
                    width: 44,
                    height: 44,
                    decoration: BoxDecoration(
                      color: const Color(0xFFEFF6FF),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: const Color(0xFFBFDBFE)),
                    ),
                    child: Center(
                      child: Text(
                        section.id,
                        style: const TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.bold,
                          fontFamily: 'monospace',
                          color: Color(0xFF1D4ED8),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          section.name,
                          style: const TextStyle(
                            fontSize: 13.5,
                            fontWeight: FontWeight.bold,
                            color: Color(0xFF0F172A),
                          ),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                        const SizedBox(height: 3),
                        Text(
                          '$subGroupCount Groups • Page ${section.page}',
                          style: const TextStyle(
                            fontSize: 11.5,
                            color: Color(0xFF64748B),
                            fontWeight: FontWeight.w500,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: const Color(0xFFEFF6FF),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: const Color(0xFFDBEAFE)),
                    ),
                    child: Text(
                      '$totalParams',
                      style: const TextStyle(
                        fontSize: 11.5,
                        fontWeight: FontWeight.bold,
                        color: Color(0xFF2563EB),
                      ),
                    ),
                  ),
                  const SizedBox(width: 4),
                  const Icon(Icons.chevron_right_rounded, size: 18, color: Color(0xFF94A3B8)),
                ],
              ),
            ),
          ),
        );
      },
    ),
    );
  }

  Widget _buildSearchResults(List<YaskawaParam> matches) {
    if (matches.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.search_off_rounded, size: 44, color: Color(0xFFCBD5E1)),
            const SizedBox(height: 10),
            Text(
              'No parameters match "$_globalQuery"',
              style: const TextStyle(color: Color(0xFF64748B), fontSize: 13.5),
            ),
          ],
        ),
      );
    }

    return SafeArea(
      top: false,
      child: ListView.separated(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      itemCount: matches.length,
      separatorBuilder: (context, index) => const SizedBox(height: 8),
      itemBuilder: (context, index) {
        final param = matches[index];

        return VisibilityDetector(
          key: Key('search_vis_${param.hexAddress}'),
          onVisibilityChanged: (info) {
            if (info.visibleFraction > 0.05) {
              final wasEmpty = _searchVisibleAddresses.isEmpty;
              _searchVisibleAddresses.add(param.hexAddress);
              if (wasEmpty && !_isSearchPollingActive) {
                _pollSearchVisibleElements();
              }
            } else {
              _searchVisibleAddresses.remove(param.hexAddress);
            }
          },
          child: ParamItemCard(
            param: param,
            store: _store,
            baseUrl: widget.baseUrl,
            onLog: widget.onLog,
          ),
        );
      },
    ),
    );
  }
}

/// Level 2 Screen: Opens in a NEW page with a BACK option to view & edit parameters inside the nest
class SectionParamsScreen extends StatefulWidget {
  final YaskawaSection section;
  final String baseUrl;
  final bool isConnected;
  final Function(String message)? onLog;
  final ParamLiveStore store;

  const SectionParamsScreen({
    super.key,
    required this.section,
    required this.baseUrl,
    required this.isConnected,
    this.onLog,
    required this.store,
  });

  @override
  State<SectionParamsScreen> createState() => _SectionParamsScreenState();
}

class _SectionParamsScreenState extends State<SectionParamsScreen> {
  String _selectedGroupId = 'ALL';
  final TextEditingController _searchController = TextEditingController();
  String _searchQuery = '';

  // Track addresses currently visible in viewport
  final Set<String> _visibleAddresses = {};
  Timer? _pollingTimer;
  bool _isPollingCycleActive = false;

  @override
  void initState() {
    super.initState();
    // Periodically poll active/visible elements in the viewport
    _pollingTimer = Timer.periodic(const Duration(milliseconds: 1500), (_) {
      if (!_isPollingCycleActive && mounted) {
        _pollVisibleElements();
      }
    });
  }

  @override
  void dispose() {
    _pollingTimer?.cancel();
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _pollVisibleElements() async {
    if (_visibleAddresses.isEmpty || !mounted || _isPollingCycleActive) return;
    _isPollingCycleActive = true;

    final addressesToPoll = _visibleAddresses.toList();
    for (final addrHex in addressesToPoll) {
      if (!mounted || !_visibleAddresses.contains(addrHex)) continue;

      widget.store.setLoading(addrHex, true);

      try {
        final uri = Uri.parse('${widget.baseUrl}/api/param?addr=$addrHex');
        final res = await http.get(uri).timeout(const Duration(seconds: 3));

        if (res.statusCode == 200) {
          final data = jsonDecode(res.body);
          if (data['status'] == 'error' || data['value'] == null) {
            throw Exception(data['message'] ?? data['error'] ?? 'No data from ESP32');
          }
          final rawVal = (data['value'] as num).toInt();
          final hexVal = data['hex_value']?.toString() ??
              '0x${rawVal.toRadixString(16).padLeft(4, '0').toUpperCase()}';

          if (mounted) {
            widget.store.updateState(
              addrHex,
              ParamLiveState(
                decimalValue: rawVal,
                hexValue: hexVal,
                readTime: DateTime.now(),
                hasError: false,
              ),
            );
          }
        } else {
          String msg = 'HTTP ${res.statusCode}';
          try {
            final errBody = jsonDecode(res.body);
            if (errBody['message'] != null) msg = errBody['message'];
          } catch (_) {}
          throw Exception(msg);
        }
      } catch (e) {
        String cleanErr = e.toString()
            .replaceAll('Exception: ', '')
            .replaceAll('ClientException: ', '')
            .replaceAll('Failed host lookup:', 'Unreachable:');
        if (cleanErr.length > 25) cleanErr = cleanErr.substring(0, 25);
        if (mounted) {
          widget.store.updateState(
            addrHex,
            ParamLiveState(
              decimalValue: null,
              hexValue: null,
              readTime: DateTime.now(),
              hasError: true,
              errorMessage: cleanErr,
            ),
          );
        }
      } finally {
        if (mounted) {
          widget.store.setLoading(addrHex, false);
        }
      }
      await Future.delayed(const Duration(milliseconds: 40));
    }

    _isPollingCycleActive = false;
  }

  List<YaskawaParam> _getFilteredParams() {
    List<YaskawaParam> params = [];

    for (final grp in widget.section.subGroups) {
      if (_selectedGroupId == 'ALL' || grp.id == _selectedGroupId) {
        params.addAll(grp.params);
      }
    }

    final query = _searchQuery.trim().toLowerCase();
    if (query.isNotEmpty) {
      params = params.where((p) {
        return p.code.toLowerCase().contains(query) ||
            p.name.toLowerCase().contains(query) ||
            p.hexAddress.toLowerCase().contains(query) ||
            p.address.toString().contains(query);
      }).toList();
    }

    return params;
  }

  @override
  Widget build(BuildContext context) {
    final filteredParams = _getFilteredParams();

    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      appBar: AppBar(
        titleSpacing: 0,
        backgroundColor: Colors.white,
        elevation: 0,
        scrolledUnderElevation: 0,
        leading: IconButton(
          tooltip: 'Back to Sections',
          icon: const Icon(Icons.arrow_back_rounded, color: Color(0xFF2563EB)),
          onPressed: () => Navigator.of(context).pop(),
        ),
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
              decoration: BoxDecoration(
                color: const Color(0xFFEFF6FF),
                borderRadius: BorderRadius.circular(6),
                border: Border.all(color: const Color(0xFFBFDBFE)),
              ),
              child: Text(
                widget.section.id,
                style: const TextStyle(
                  color: Color(0xFF1D4ED8),
                  fontFamily: 'monospace',
                  fontWeight: FontWeight.bold,
                  fontSize: 12,
                ),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                widget.section.name,
                style: const TextStyle(
                  fontSize: 14.5,
                  fontWeight: FontWeight.bold,
                  color: Color(0xFF0F172A),
                ),
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
        actions: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
            decoration: BoxDecoration(
              color: const Color(0xFFEFF6FF),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: const Color(0xFFBFDBFE)),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 6,
                  height: 6,
                  decoration: const BoxDecoration(
                    color: Color(0xFF2563EB),
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 4),
                const Text(
                  'Live',
                  style: TextStyle(
                    fontSize: 10.5,
                    fontWeight: FontWeight.bold,
                    color: Color(0xFF1D4ED8),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 6),
          Container(
            margin: const EdgeInsets.only(right: 12),
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
            decoration: BoxDecoration(
              color: const Color(0xFFF1F5F9),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Text(
              '${filteredParams.length}',
              style: const TextStyle(
                fontSize: 11.5,
                fontWeight: FontWeight.bold,
                color: Color(0xFF475569),
              ),
            ),
          ),
        ],
        bottom: const PreferredSize(
          preferredSize: Size.fromHeight(1),
          child: Divider(height: 1, color: Color(0xFFE2E8F0)),
        ),
      ),
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Top Controls: Full-width search + Subgroup chips
          Container(
            padding: const EdgeInsets.fromLTRB(14, 10, 14, 8),
            decoration: const BoxDecoration(
              color: Colors.white,
              border: Border(bottom: BorderSide(color: Color(0xFFE2E8F0))),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // Full-width search inside section
                SizedBox(
                  height: 38,
                  child: TextField(
                    controller: _searchController,
                    onChanged: (val) => setState(() => _searchQuery = val),
                    style: const TextStyle(fontSize: 13, color: Color(0xFF0F172A)),
                    decoration: InputDecoration(
                      isDense: true,
                      filled: true,
                      fillColor: const Color(0xFFF8FAFC),
                      hintText: 'Search in this section (code, name, hex)...',
                      hintStyle: const TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
                      prefixIcon: const Icon(Icons.search, size: 16, color: Color(0xFF64748B)),
                      suffixIcon: _searchQuery.isNotEmpty
                          ? IconButton(
                              icon: const Icon(Icons.clear, size: 14, color: Color(0xFF64748B)),
                              onPressed: () {
                                _searchController.clear();
                                setState(() => _searchQuery = '');
                              },
                            )
                          : null,
                      contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(6),
                        borderSide: const BorderSide(color: Color(0xFFCBD5E1)),
                      ),
                      enabledBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(6),
                        borderSide: const BorderSide(color: Color(0xFFCBD5E1)),
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(6),
                        borderSide: const BorderSide(color: Color(0xFF2563EB)),
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 8),

                // Horizontal scrollable subgroup filter chips
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: [
                      _buildFilterChip(
                        'ALL',
                        'All (${widget.section.totalParamsCount})',
                        _selectedGroupId == 'ALL',
                      ),
                      const SizedBox(width: 6),
                      ...widget.section.subGroups.map((grp) {
                        final isSel = _selectedGroupId == grp.id;
                        final label = '${grp.id} (${grp.params.length})';
                        return Padding(
                          padding: const EdgeInsets.only(right: 6),
                          child: _buildFilterChip(grp.id, label, isSel),
                        );
                      }),
                    ],
                  ),
                ),
              ],
            ),
          ),

          // Parameters List View
          Expanded(
            child: filteredParams.isEmpty
                ? Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.search_off_rounded, size: 44, color: Color(0xFFCBD5E1)),
                        const SizedBox(height: 10),
                        Text(
                          _searchQuery.isNotEmpty
                              ? 'No parameters match "$_searchQuery"'
                              : 'No parameters in this category',
                          style: const TextStyle(color: Color(0xFF64748B), fontSize: 13.5),
                        ),
                      ],
                    ),
                  )
                : SafeArea(
                    top: false,
                    child: ListView.separated(
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                    itemCount: filteredParams.length,
                    separatorBuilder: (context, index) => const SizedBox(height: 8),
                    itemBuilder: (context, index) {
                      final param = filteredParams[index];

                      return VisibilityDetector(
                        key: Key('param_vis_${param.hexAddress}'),
                        onVisibilityChanged: (info) {
                          if (info.visibleFraction > 0.05) {
                            final wasEmpty = _visibleAddresses.isEmpty;
                            _visibleAddresses.add(param.hexAddress);
                            if (wasEmpty && !_isPollingCycleActive) {
                              _pollVisibleElements();
                            }
                          } else {
                            _visibleAddresses.remove(param.hexAddress);
                          }
                        },
                        child: ParamItemCard(
                          param: param,
                          store: widget.store,
                          baseUrl: widget.baseUrl,
                          onLog: widget.onLog,
                        ),
                      );
                    },
                  ),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildFilterChip(String id, String label, bool isSelected) {
    return ChoiceChip(
      selected: isSelected,
      label: Text(label),
      labelStyle: TextStyle(
        fontSize: 11.5,
        fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
        color: isSelected ? Colors.white : const Color(0xFF334155),
      ),
      selectedColor: const Color(0xFF2563EB),
      backgroundColor: Colors.white,
      side: BorderSide(
        color: isSelected ? const Color(0xFF2563EB) : const Color(0xFFCBD5E1),
      ),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
      onSelected: (_) {
        setState(() => _selectedGroupId = id);
      },
    );
  }
}

/// Mobile-First Responsive Parameter Card with Reactive Store (Zero Blinking)
class ParamItemCard extends StatelessWidget {
  final YaskawaParam param;
  final ParamLiveStore store;
  final String baseUrl;
  final Function(String message)? onLog;

  const ParamItemCard({
    super.key,
    required this.param,
    required this.store,
    required this.baseUrl,
    this.onLog,
  });

  void _openEditDialog(BuildContext context, ParamLiveState? liveState) {
    final hasVal = liveState != null && liveState.decimalValue != null;
    final initialValStr = hasVal
        ? (param.decimals > 0
            ? (liveState.decimalValue! * param.multiplier).toStringAsFixed(param.decimals)
            : liveState.decimalValue.toString())
        : '';
    final editController = TextEditingController(text: initialValStr);
    int parsedValue = param.parseUserInputToRaw(initialValStr) ?? (hasVal ? liveState.decimalValue! : 0);

    showDialog(
      context: context,
      builder: (dialogCtx) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            String hexPreview =
                '0x${(parsedValue & 0xFFFF).toRadixString(16).padLeft(4, '0').toUpperCase()}';

            return AlertDialog(
              backgroundColor: Colors.white,
              surfaceTintColor: Colors.white,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(14),
                side: const BorderSide(color: Color(0xFFE2E8F0)),
              ),
              title: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: const Color(0xFFEFF6FF),
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(color: const Color(0xFFBFDBFE)),
                    ),
                    child: Text(
                      param.code,
                      style: const TextStyle(
                        color: Color(0xFF1D4ED8),
                        fontFamily: 'monospace',
                        fontWeight: FontWeight.bold,
                        fontSize: 15,
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  const Expanded(
                    child: Text(
                      'Edit Parameter',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                        color: Color(0xFF0F172A),
                      ),
                    ),
                  ),
                ],
              ),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      param.name,
                      style: const TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: Color(0xFF1E293B),
                      ),
                    ),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 6,
                      runSpacing: 6,
                      children: [
                        _buildMetaBadge('HEX: ${param.hexAddress}', const Color(0xFF2563EB)),
                        _buildMetaBadge('DEC: ${param.address}', const Color(0xFF64748B)),
                        _buildMetaBadge('Page ${param.page}', const Color(0xFF64748B)),
                        if (param.range.isNotEmpty)
                          _buildMetaBadge('Range: ${param.range}', const Color(0xFF0284C7)),
                      ],
                    ),
                    if (param.range.isNotEmpty) ...[
                      const SizedBox(height: 10),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                        decoration: BoxDecoration(
                          color: const Color(0xFFF0F9FF),
                          borderRadius: BorderRadius.circular(6),
                          border: Border.all(color: const Color(0xFFBAE6FD)),
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.tune_rounded, size: 14, color: Color(0xFF0284C7)),
                            const SizedBox(width: 6),
                            Expanded(
                              child: Text(
                                'Allowed Range: ${param.range}',
                                style: const TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.bold,
                                  color: Color(0xFF0369A1),
                                  fontFamily: 'monospace',
                                ),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                    if (!hasVal) ...[
                      const SizedBox(height: 10),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                        decoration: BoxDecoration(
                          color: const Color(0xFFFFFBEB),
                          borderRadius: BorderRadius.circular(6),
                          border: Border.all(color: const Color(0xFFFDE68A)),
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.info_outline, size: 14, color: Color(0xFFD97706)),
                            const SizedBox(width: 6),
                            Expanded(
                              child: Text(
                                liveState?.hasError == true
                                    ? 'Drive read failed or offline. Enter desired setting.'
                                    : 'Drive value not read yet. Enter desired setting.',
                                style: const TextStyle(fontSize: 11, color: Color(0xFFB45309)),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                    const SizedBox(height: 10),
                    const Divider(color: Color(0xFFE2E8F0)),
                    const SizedBox(height: 10),
                    const Text(
                      'New Register Value (16-bit):',
                      style: TextStyle(
                        fontSize: 12.5,
                        color: Color(0xFF475569),
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 6),
                    TextField(
                      controller: editController,
                      keyboardType: TextInputType.text,
                      autofocus: true,
                      style: const TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                        color: Color(0xFF1D4ED8),
                      ),
                      decoration: InputDecoration(
                        filled: true,
                        fillColor: const Color(0xFFF8FAFC),
                        hintText: 'e.g. 50 or 0x0032',
                        hintStyle: const TextStyle(color: Color(0xFF94A3B8), fontSize: 13),
                        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
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
                          borderSide: const BorderSide(color: Color(0xFF2563EB), width: 1.5),
                        ),
                        suffixIcon: IconButton(
                          icon: const Icon(Icons.clear, color: Color(0xFF94A3B8)),
                          onPressed: () {
                            editController.clear();
                            setDialogState(() => parsedValue = 0);
                          },
                        ),
                      ),
                      onChanged: (val) {
                        setDialogState(() {
                          final pVal = param.parseUserInputToRaw(val);
                          parsedValue = pVal ?? 0;
                        });
                      },
                    ),
                    const SizedBox(height: 10),
                    Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: const Color(0xFFF1F5F9),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: const Color(0xFFE2E8F0)),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              const Text('Drive Setting:', style: TextStyle(fontSize: 11, color: Color(0xFF64748B), fontWeight: FontWeight.w600)),
                              Text(
                                param.formatLiveValue(parsedValue),
                                style: const TextStyle(
                                  fontFamily: 'monospace',
                                  fontWeight: FontWeight.bold,
                                  fontSize: 13,
                                  color: Color(0xFF0F172A),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 6),
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              const Text('Modbus Register:', style: TextStyle(fontSize: 11, color: Color(0xFF64748B))),
                              Text(
                                '$parsedValue ($hexPreview)',
                                style: const TextStyle(
                                  fontFamily: 'monospace',
                                  fontWeight: FontWeight.bold,
                                  fontSize: 12,
                                  color: Color(0xFF2563EB),
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.of(dialogCtx).pop(),
                  child: const Text('Cancel', style: TextStyle(color: Color(0xFF64748B))),
                ),
                ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF2563EB),
                    foregroundColor: Colors.white,
                    elevation: 0,
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                  icon: const Icon(Icons.send_rounded, size: 16),
                  label: const Text('Write to VFD', style: TextStyle(fontWeight: FontWeight.bold)),
                  onPressed: () async {
                    Navigator.of(dialogCtx).pop();
                    await _write(context, parsedValue & 0xFFFF);
                  },
                ),
              ],
            );
          },
        );
      },
    );
  }

  Future<void> _write(BuildContext context, int newValue) async {
    final addrHex = param.hexAddress;
    store.setLoading(addrHex, true);
    onLog?.call('TX -> Write Param ${param.code} ($addrHex) = $newValue (0x${newValue.toRadixString(16).toUpperCase()})...');

    try {
      final uri = Uri.parse('$baseUrl/api/param');
      final body = jsonEncode({
        'address': addrHex,
        'value': newValue,
        'param': param.code,
      });

      final res = await http.post(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: body,
      ).timeout(const Duration(seconds: 4));

      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        final writtenVal = (data['written_value'] ?? data['value'] ?? newValue) as num;
        final hexVal = '0x${writtenVal.toInt().toRadixString(16).padLeft(4, '0').toUpperCase()}';

        store.updateState(
          addrHex,
          ParamLiveState(
            decimalValue: writtenVal.toInt(),
            hexValue: hexVal,
            readTime: DateTime.now(),
            hasError: false,
          ),
        );

        onLog?.call('RX <- Successfully written ${param.code} ($addrHex) = $writtenVal (${param.formatLiveValue(writtenVal.toInt())})');
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Row(
                children: [
                  const Icon(Icons.check_circle_rounded, color: Colors.white, size: 18),
                  const SizedBox(width: 8),
                  Text('Updated ${param.code} to ${param.formatLiveValue(writtenVal.toInt())}'),
                ],
              ),
              backgroundColor: const Color(0xFF2563EB),
              behavior: SnackBarBehavior.floating,
            ),
          );
        }
      } else {
        throw Exception('HTTP ${res.statusCode}: ${res.body}');
      }
    } catch (e) {
      onLog?.call('RX Error writing ${param.code}: $e');
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Row(
              children: [
                const Icon(Icons.error_outline_rounded, color: Colors.white, size: 18),
                const SizedBox(width: 8),
                Expanded(child: Text('Failed to write ${param.code}: $e')),
              ],
            ),
            backgroundColor: const Color(0xFFDC2626),
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    } finally {
      store.setLoading(addrHex, false);
    }
  }

  Widget _buildMetaBadge(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        text,
        style: TextStyle(
          fontSize: 10.5,
          fontFamily: 'monospace',
          color: color,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final stateNotifier = store.getNotifier(param.hexAddress);
    final loadingNotifier = store.getLoadingNotifier(param.hexAddress);

    return ValueListenableBuilder<ParamLiveState?>(
      valueListenable: stateNotifier,
      builder: (context, liveState, _) {
        final hasVal = liveState != null && liveState.decimalValue != null;
        final hasErr = liveState != null && liveState.hasError;

        return ValueListenableBuilder<bool>(
          valueListenable: loadingNotifier,
          builder: (context, isLoading, _) {
            return Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(
                  color: hasErr ? const Color(0xFFFCA5A5) : const Color(0xFFE2E8F0),
                  width: hasErr ? 1.5 : 1.0,
                ),
                boxShadow: const [
                  BoxShadow(
                    color: Color(0x04000000),
                    blurRadius: 4,
                    offset: Offset(0, 1),
                  ),
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // Row 1: Code Badge + Param Name (Expanded) + Page
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
                        decoration: BoxDecoration(
                          color: const Color(0xFFEFF6FF),
                          borderRadius: BorderRadius.circular(6),
                          border: Border.all(color: const Color(0xFFBFDBFE)),
                        ),
                        child: Text(
                          param.code,
                          style: const TextStyle(
                            fontFamily: 'monospace',
                            fontSize: 12.5,
                            fontWeight: FontWeight.bold,
                            color: Color(0xFF1D4ED8),
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          param.name,
                          style: const TextStyle(
                            fontSize: 13.5,
                            fontWeight: FontWeight.w600,
                            color: Color(0xFF0F172A),
                          ),
                        ),
                      ),
                      const SizedBox(width: 6),
                      Text(
                        'p.${param.page}',
                        style: const TextStyle(
                          fontSize: 11,
                          color: Color(0xFF94A3B8),
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),

                  // Row 2: Address Tags & Range
                  Row(
                    children: [
                      _buildMetaBadge('HEX: ${param.hexAddress}', const Color(0xFF2563EB)),
                      const SizedBox(width: 6),
                      _buildMetaBadge('DEC: ${param.address}', const Color(0xFF64748B)),
                      if (param.range.isNotEmpty) ...[
                        const SizedBox(width: 6),
                        Expanded(
                          child: Text(
                            'Range: ${param.range}',
                            style: const TextStyle(
                              fontSize: 10.5,
                              color: Color(0xFF0284C7),
                              fontWeight: FontWeight.w600,
                              fontFamily: 'monospace',
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ],
                    ],
                  ),
                  const SizedBox(height: 8),
                  const Divider(height: 1, color: Color(0xFFF1F5F9)),
                  const SizedBox(height: 8),

                  // Row 3: Current Value Readout + Action Buttons
                  Row(
                    children: [
                      // Value Box (No blinking, refresh icon next to decimal value, no hex on right)
                      Expanded(
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
                          decoration: BoxDecoration(
                            color: hasErr ? const Color(0xFFFEF2F2) : const Color(0xFFF8FAFC),
                            borderRadius: BorderRadius.circular(6),
                            border: Border.all(
                              color: hasErr ? const Color(0xFFFECACA) : const Color(0xFFE2E8F0),
                            ),
                          ),
                          child: Row(
                            children: [
                              Text(
                                'VAL: ',
                                style: TextStyle(
                                  fontSize: 10,
                                  fontWeight: FontWeight.bold,
                                  color: hasErr ? const Color(0xFFDC2626) : const Color(0xFF64748B),
                                ),
                              ),
                              if (hasVal) ...[
                                Text(
                                  param.formatLiveValue(liveState.decimalValue!),
                                  style: const TextStyle(
                                    fontFamily: 'monospace',
                                    fontSize: 13,
                                    fontWeight: FontWeight.bold,
                                    color: Color(0xFF0F172A),
                                  ),
                                ),
                                const SizedBox(width: 6),
                                if (isLoading)
                                  const RotatingRefreshIcon(size: 13, color: Color(0xFF2563EB))
                                else
                                  const Icon(Icons.sync_rounded, size: 13, color: Color(0xFF94A3B8)),
                              ] else if (hasErr) ...[
                                Expanded(
                                  child: Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      const Icon(Icons.error_outline_rounded,
                                          size: 13, color: Color(0xFFDC2626)),
                                      const SizedBox(width: 4),
                                      Flexible(
                                        child: Text(
                                          liveState.errorMessage?.isNotEmpty == true
                                              ? 'ERROR (${liveState.errorMessage})'
                                              : 'ERROR',
                                          style: const TextStyle(
                                            fontFamily: 'monospace',
                                            fontSize: 11,
                                            fontWeight: FontWeight.bold,
                                            color: Color(0xFFDC2626),
                                          ),
                                          overflow: TextOverflow.ellipsis,
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                                const SizedBox(width: 4),
                                if (isLoading)
                                  const RotatingRefreshIcon(size: 13, color: Color(0xFFDC2626))
                                else
                                  const Icon(Icons.sync_rounded, size: 13, color: Color(0xFFCBD5E1)),
                              ] else ...[
                                Text(
                                  isLoading ? 'Polling...' : '--',
                                  style: const TextStyle(
                                    fontFamily: 'monospace',
                                    fontSize: 11,
                                    color: Color(0xFF94A3B8),
                                  ),
                                ),
                                const SizedBox(width: 6),
                                if (isLoading)
                                  const RotatingRefreshIcon(size: 13, color: Color(0xFF2563EB))
                                else
                                  const Icon(Icons.sync_rounded, size: 13, color: Color(0xFF94A3B8)),
                              ],
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),

                      // EDIT Button
                      ElevatedButton.icon(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xFF2563EB),
                          foregroundColor: Colors.white,
                          elevation: 0,
                          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
                          minimumSize: const Size(72, 34),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
                        ),
                        icon: const Icon(Icons.edit_outlined, size: 14),
                        label: const Text('EDIT', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11)),
                        onPressed: () => _openEditDialog(context, liveState),
                      ),
                    ],
                  ),
                ],
              ),
            );
          },
        );
      },
    );
  }
}

class ParamLiveState {
  final int? decimalValue;
  final String? hexValue;
  final DateTime readTime;
  final bool hasError;
  final String? errorMessage;

  ParamLiveState({
    required this.decimalValue,
    required this.hexValue,
    required this.readTime,
    required this.hasError,
    this.errorMessage,
  });
}
