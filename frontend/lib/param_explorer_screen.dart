// AUTO-GENERATED FILE BY generate_code.py - DO NOT EDIT MANUALLY
// Yaskawa GA700 Parameter Explorer & Editor Screen

import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'generated_params_data.dart';

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
  // Navigation / Selection State
  late YaskawaSection _selectedSection;
  String _selectedGroupId = 'ALL'; // 'ALL' or specific group ID
  final TextEditingController _searchController = TextEditingController();
  String _searchQuery = '';

  // Live Values cache: Map<AddressHex, ParamState>
  final Map<String, _ParamLiveState> _liveValues = {};
  final Set<String> _loadingAddresses = {};

  @override
  void initState() {
    super.initState();
    _selectedSection = kYaskawaSections.firstWhere(
      (s) => s.totalParamsCount > 0,
      orElse: () => kYaskawaSections.first,
    );
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  void _log(String msg) {
    widget.onLog?.call(msg);
  }

  // ==========================================================================
  // HTTP REST API Actions: Read & Write
  // ==========================================================================

  Future<void> _readParameter(YaskawaParam param) async {
    final addrHex = param.hexAddress;
    setState(() => _loadingAddresses.add(addrHex));
    _log('TX -> Read Param ${param.code} ($addrHex)...');

    try {
      final uri = Uri.parse('${widget.baseUrl}/api/param?addr=$addrHex');
      final res = await http.get(uri).timeout(const Duration(seconds: 4));

      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        final rawVal = (data['value'] as num).toInt();
        final hexVal = data['hex_value']?.toString() ?? '0x${rawVal.toRadixString(16).padLeft(4, '0').toUpperCase()}';

        setState(() {
          _liveValues[addrHex] = _ParamLiveState(
            decimalValue: rawVal,
            hexValue: hexVal,
            readTime: DateTime.now(),
            hasError: false,
          );
        });

        _log('RX <- Param ${param.code} ($addrHex) = $rawVal ($hexVal)');
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Read ${param.code}: $rawVal ($hexVal)'),
              backgroundColor: const Color(0xFF10B981),
              duration: const Duration(seconds: 2),
            ),
          );
        }
      } else {
        throw Exception('HTTP ${res.statusCode}: ${res.body}');
      }
    } catch (e) {
      setState(() {
        _liveValues[addrHex] = _ParamLiveState(
          decimalValue: null,
          hexValue: null,
          readTime: DateTime.now(),
          hasError: true,
          errorMessage: e.toString(),
        );
      });
      _log('RX Error reading ${param.code}: $e');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to read ${param.code}: $e'),
            backgroundColor: const Color(0xFFEF4444),
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _loadingAddresses.remove(addrHex));
      }
    }
  }

  Future<void> _writeParameter(YaskawaParam param, int newValue) async {
    final addrHex = param.hexAddress;
    setState(() => _loadingAddresses.add(addrHex));
    _log('TX -> Write Param ${param.code} ($addrHex) = $newValue (0x${newValue.toRadixString(16).toUpperCase()})...');

    try {
      final uri = Uri.parse('${widget.baseUrl}/api/param');
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

        setState(() {
          _liveValues[addrHex] = _ParamLiveState(
            decimalValue: writtenVal.toInt(),
            hexValue: hexVal,
            readTime: DateTime.now(),
            hasError: false,
          );
        });

        _log('RX <- Successfully written ${param.code} ($addrHex) = $writtenVal');
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Success: Written ${param.code} = $writtenVal ($hexVal)'),
              backgroundColor: const Color(0xFF10B981),
            ),
          );
        }
      } else {
        throw Exception('HTTP ${res.statusCode}: ${res.body}');
      }
    } catch (e) {
      _log('RX Error writing ${param.code}: $e');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to write ${param.code}: $e'),
            backgroundColor: const Color(0xFFEF4444),
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _loadingAddresses.remove(addrHex));
      }
    }
  }

  // ==========================================================================
  // Edit Parameter Modal Dialog
  // ==========================================================================

  void _showEditDialog(YaskawaParam param) {
    final liveState = _liveValues[param.hexAddress];
    final initialValStr = liveState?.decimalValue?.toString() ?? '0';
    final editController = TextEditingController(text: initialValStr);
    int parsedValue = int.tryParse(initialValStr) ?? 0;

    showDialog(
      context: context,
      builder: (dialogCtx) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            String hexPreview = '0x${(parsedValue & 0xFFFF).toRadixString(16).padLeft(4, '0').toUpperCase()}';

            return AlertDialog(
              backgroundColor: const Color(0xFF161B22),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
                side: const BorderSide(color: Color(0xFF30363D)),
              ),
              title: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: const Color(0xFF00F0FF).withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(color: const Color(0xFF00F0FF)),
                    ),
                    child: Text(
                      param.code,
                      style: const TextStyle(
                        color: Color(0xFF00F0FF),
                        fontFamily: 'monospace',
                        fontWeight: FontWeight.bold,
                        fontSize: 16,
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  const Expanded(
                    child: Text(
                      'Edit Parameter',
                      style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
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
                      style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: Colors.white),
                    ),
                    const SizedBox(height: 6),
                    Row(
                      children: [
                        _buildInfoTag('Address', param.hexAddress, const Color(0xFF58A6FF)),
                        const SizedBox(width: 8),
                        _buildInfoTag('Dec', '${param.address}', const Color(0xFF8B949E)),
                        const SizedBox(width: 8),
                        _buildInfoTag('Page', 'p.${param.page}', const Color(0xFF8B949E)),
                      ],
                    ),
                    const SizedBox(height: 16),
                    const Divider(color: Color(0xFF30363D)),
                    const SizedBox(height: 12),
                    const Text(
                      'Target Register Value (16-bit)',
                      style: TextStyle(fontSize: 13, color: Color(0xFF8B949E), fontWeight: FontWeight.w600),
                    ),
                    const SizedBox(height: 8),
                    TextField(
                      controller: editController,
                      keyboardType: TextInputType.text,
                      autofocus: true,
                      style: const TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: Color(0xFF00F0FF),
                      ),
                      decoration: InputDecoration(
                        filled: true,
                        fillColor: const Color(0xFF0D1117),
                        hintText: 'Enter decimal or 0xHEX',
                        hintStyle: const TextStyle(color: Color(0xFF484F58)),
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(8),
                          borderSide: const BorderSide(color: Color(0xFF30363D)),
                        ),
                        enabledBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(8),
                          borderSide: const BorderSide(color: Color(0xFF30363D)),
                        ),
                        focusedBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(8),
                          borderSide: const BorderSide(color: Color(0xFF00F0FF), width: 2),
                        ),
                        suffixIcon: IconButton(
                          icon: const Icon(Icons.clear, color: Color(0xFF8B949E)),
                          onPressed: () {
                            editController.clear();
                            setDialogState(() => parsedValue = 0);
                          },
                        ),
                      ),
                      onChanged: (val) {
                        setDialogState(() {
                          val = val.trim();
                          if (val.startsWith('0x') || val.startsWith('0X')) {
                            parsedValue = int.tryParse(val.substring(2), radix: 16) ?? 0;
                          } else {
                            parsedValue = int.tryParse(val) ?? 0;
                          }
                        });
                      },
                    ),
                    const SizedBox(height: 12),
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: const Color(0xFF0D1117),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: const Color(0xFF30363D)),
                      ),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text('Decimal', style: TextStyle(fontSize: 11, color: Color(0xFF8B949E))),
                              Text('$parsedValue', style: const TextStyle(fontFamily: 'monospace', fontWeight: FontWeight.bold)),
                            ],
                          ),
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.end,
                            children: [
                              const Text('Hexadecimal', style: TextStyle(fontSize: 11, color: Color(0xFF8B949E))),
                              Text(hexPreview, style: const TextStyle(fontFamily: 'monospace', fontWeight: FontWeight.bold, color: Color(0xFF10B981))),
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
                  child: const Text('Cancel', style: TextStyle(color: Color(0xFF8B949E))),
                ),
                ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF00F0FF),
                    foregroundColor: Colors.black,
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                  icon: const Icon(Icons.send_rounded, size: 18),
                  label: const Text('Write to VFD', style: TextStyle(fontWeight: FontWeight.bold)),
                  onPressed: () {
                    Navigator.of(dialogCtx).pop();
                    _writeParameter(param, parsedValue & 0xFFFF);
                  },
                ),
              ],
            );
          },
        );
      },
    );
  }

  Widget _buildInfoTag(String label, String value, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Text(
        '$label: $value',
        style: TextStyle(fontSize: 11, color: color, fontFamily: 'monospace', fontWeight: FontWeight.w600),
      ),
    );
  }

  // ==========================================================================
  // Filtered Parameters Calculation
  // ==========================================================================

  List<YaskawaParam> _getFilteredParams() {
    List<YaskawaParam> params = [];

    // Filter by selected section and subgroup
    for (final grp in _selectedSection.subGroups) {
      if (_selectedGroupId == 'ALL' || grp.id == _selectedGroupId) {
        params.addAll(grp.params);
      }
    }

    // Filter by search query
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
      backgroundColor: const Color(0xFF0D1117),
      body: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 1. Left Sidebar: Outer Layers (Sections)
          _buildOuterLayersSidebar(),

          // 2. Main Content: Subgroups, Search, & Parameters List
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _buildTopHeader(filteredParams.length),
                _buildSubGroupChips(),
                const Divider(height: 1, color: Color(0xFF30363D)),
                Expanded(
                  child: filteredParams.isEmpty
                      ? _buildEmptyState()
                      : _buildParamsListView(filteredParams),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ==========================================================================
  // UI Component: Left Sidebar (Outer Layers)
  // ==========================================================================

  Widget _buildOuterLayersSidebar() {
    return Container(
      width: 280,
      decoration: const BoxDecoration(
        color: Color(0xFF161B22),
        border: Border(right: BorderSide(color: Color(0xFF30363D))),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            padding: const EdgeInsets.all(16),
            decoration: const BoxDecoration(
              border: Border(bottom: BorderSide(color: Color(0xFF30363D))),
            ),
            child: const Row(
              children: [
                Icon(Icons.folder_special_rounded, color: Color(0xFF00F0FF), size: 20),
                SizedBox(width: 8),
                Text(
                  'SECTIONS (Outer Layer)',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 1.1,
                    color: Color(0xFF8B949E),
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: ListView.builder(
              itemCount: kYaskawaSections.length,
              itemBuilder: (context, index) {
                final section = kYaskawaSections[index];
                final isSelected = section.id == _selectedSection.id;
                final count = section.totalParamsCount;

                return InkWell(
                  onTap: () {
                    setState(() {
                      _selectedSection = section;
                      _selectedGroupId = 'ALL';
                    });
                  },
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                    decoration: BoxDecoration(
                      color: isSelected ? const Color(0xFF00F0FF).withValues(alpha: 0.12) : Colors.transparent,
                      border: Border(
                        left: BorderSide(
                          color: isSelected ? const Color(0xFF00F0FF) : Colors.transparent,
                          width: 3,
                        ),
                        bottom: const BorderSide(color: Color(0xFF21262D)),
                      ),
                    ),
                    child: Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: isSelected ? const Color(0xFF00F0FF) : const Color(0xFF30363D),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            section.id,
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.bold,
                              fontFamily: 'monospace',
                              color: isSelected ? Colors.black : const Color(0xFFC9D1D9),
                            ),
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            section.name,
                            style: TextStyle(
                              fontSize: 13,
                              fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                              color: isSelected ? Colors.white : const Color(0xFF8B949E),
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        const SizedBox(width: 6),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: const Color(0xFF21262D),
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Text(
                            '$count',
                            style: const TextStyle(fontSize: 11, color: Color(0xFF8B949E)),
                          ),
                        ),
                      ],
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

  // ==========================================================================
  // UI Component: Top Header with Search and Stats
  // ==========================================================================

  Widget _buildTopHeader(int matchCount) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
      decoration: const BoxDecoration(
        color: Color(0xFF161B22),
        border: Border(bottom: BorderSide(color: Color(0xFF30363D))),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _selectedSection.name,
                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.white),
                ),
                const SizedBox(height: 2),
                Text(
                  'Section ${_selectedSection.id} • Page ${_selectedSection.page} • $matchCount Parameters visible',
                  style: const TextStyle(fontSize: 12, color: Color(0xFF8B949E)),
                ),
              ],
            ),
          ),
          const SizedBox(width: 16),
          // Search Field
          SizedBox(
            width: 280,
            height: 40,
            child: TextField(
              controller: _searchController,
              onChanged: (val) => setState(() => _searchQuery = val),
              style: const TextStyle(fontSize: 13),
              decoration: InputDecoration(
                filled: true,
                fillColor: const Color(0xFF0D1117),
                hintText: 'Search code, name, or 0xADDR...',
                hintStyle: const TextStyle(color: Color(0xFF484F58), fontSize: 13),
                prefixIcon: const Icon(Icons.search, size: 18, color: Color(0xFF8B949E)),
                suffixIcon: _searchQuery.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear, size: 16, color: Color(0xFF8B949E)),
                        onPressed: () {
                          _searchController.clear();
                          setState(() => _searchQuery = '');
                        },
                      )
                    : null,
                contentPadding: const EdgeInsets.symmetric(horizontal: 12),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                  borderSide: const BorderSide(color: Color(0xFF30363D)),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                  borderSide: const BorderSide(color: Color(0xFF30363D)),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                  borderSide: const BorderSide(color: Color(0xFF00F0FF)),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ==========================================================================
  // UI Component: Subgroup Selector Chips
  // ==========================================================================

  Widget _buildSubGroupChips() {
    final subGroups = _selectedSection.subGroups;
    if (subGroups.isEmpty) return const SizedBox.shrink();

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      color: const Color(0xFF0D1117),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(
          children: [
            _buildFilterChip('ALL', 'All (${_selectedSection.totalParamsCount})', _selectedGroupId == 'ALL'),
            const SizedBox(width: 8),
            ...subGroups.map((grp) {
              final isSel = _selectedGroupId == grp.id;
              final label = '${grp.id}: ${grp.name} (${grp.params.length})';
              return Padding(
                padding: const EdgeInsets.only(right: 8),
                child: _buildFilterChip(grp.id, label, isSel),
              );
            }),
          ],
        ),
      ),
    );
  }

  Widget _buildFilterChip(String id, String label, bool isSelected) {
    return ChoiceChip(
      selected: isSelected,
      label: Text(label),
      labelStyle: TextStyle(
        fontSize: 12,
        fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
        color: isSelected ? Colors.black : const Color(0xFFC9D1D9),
      ),
      selectedColor: const Color(0xFF00F0FF),
      backgroundColor: const Color(0xFF161B22),
      side: BorderSide(color: isSelected ? const Color(0xFF00F0FF) : const Color(0xFF30363D)),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      onSelected: (_) {
        setState(() => _selectedGroupId = id);
      },
    );
  }

  // ==========================================================================
  // UI Component: Parameters List View
  // ==========================================================================

  Widget _buildParamsListView(List<YaskawaParam> params) {
    return ListView.separated(
      padding: const EdgeInsets.all(16),
      itemCount: params.length,
      separatorBuilder: (context, index) => const SizedBox(height: 10),
      itemBuilder: (context, index) {
        final param = params[index];
        final liveState = _liveValues[param.hexAddress];
        final isLoading = _loadingAddresses.contains(param.hexAddress);

        return _buildParamCard(param, liveState, isLoading);
      },
    );
  }

  Widget _buildParamCard(YaskawaParam param, _ParamLiveState? liveState, bool isLoading) {
    final hasVal = liveState != null && liveState.decimalValue != null;

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: hasVal ? const Color(0xFF10B981).withValues(alpha: 0.4) : const Color(0xFF30363D),
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          // Param Code Badge
          Container(
            width: 76,
            padding: const EdgeInsets.symmetric(vertical: 8),
            decoration: BoxDecoration(
              color: const Color(0xFF00F0FF).withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: const Color(0xFF00F0FF).withValues(alpha: 0.5)),
            ),
            child: Text(
              param.code,
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontFamily: 'monospace',
                fontSize: 14,
                fontWeight: FontWeight.bold,
                color: Color(0xFF00F0FF),
              ),
            ),
          ),
          const SizedBox(width: 14),

          // Name and Details
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  param.name,
                  style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Colors.white),
                ),
                const SizedBox(height: 4),
                Row(
                  children: [
                    _buildMetaBadge('HEX: ${param.hexAddress}', const Color(0xFF58A6FF)),
                    const SizedBox(width: 8),
                    _buildMetaBadge('DEC: ${param.address}', const Color(0xFF8B949E)),
                    const SizedBox(width: 8),
                    _buildMetaBadge('Page ${param.page}', const Color(0xFF8B949E)),
                  ],
                ),
              ],
            ),
          ),

          // Live Value Badge
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            decoration: BoxDecoration(
              color: const Color(0xFF0D1117),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: hasVal ? const Color(0xFF10B981) : const Color(0xFF30363D),
              ),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                const Text('CURRENT VALUE', style: TextStyle(fontSize: 10, color: Color(0xFF8B949E))),
                if (isLoading)
                  const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF00F0FF)),
                  )
                else if (hasVal)
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        '${liveState.decimalValue}',
                        style: const TextStyle(
                          fontFamily: 'monospace',
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                          color: Color(0xFF10B981),
                        ),
                      ),
                      const SizedBox(width: 6),
                      Text(
                        '(${liveState.hexValue})',
                        style: const TextStyle(
                          fontFamily: 'monospace',
                          fontSize: 12,
                          color: Color(0xFF8B949E),
                        ),
                      ),
                    ],
                  )
                else
                  const Text(
                    '-- (Unread)',
                    style: TextStyle(fontFamily: 'monospace', fontSize: 13, color: Color(0xFF484F58)),
                  ),
              ],
            ),
          ),
          const SizedBox(width: 12),

          // Actions: READ & EDIT buttons
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Read Button
              OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: const Color(0xFF58A6FF),
                  side: const BorderSide(color: Color(0xFF58A6FF)),
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                ),
                icon: const Icon(Icons.sync_rounded, size: 16),
                label: const Text('READ', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12)),
                onPressed: isLoading ? null : () => _readParameter(param),
              ),
              const SizedBox(width: 8),

              // Edit / Write Button
              ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF00F0FF),
                  foregroundColor: Colors.black,
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                ),
                icon: const Icon(Icons.edit_note_rounded, size: 18),
                label: const Text('EDIT', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12)),
                onPressed: () => _showEditDialog(param),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildMetaBadge(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        text,
        style: TextStyle(fontSize: 11, fontFamily: 'monospace', color: color),
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.search_off_rounded, size: 48, color: Color(0xFF484F58)),
          const SizedBox(height: 12),
          Text(
            _searchQuery.isNotEmpty
                ? 'No parameters match "$_searchQuery"'
                : 'No parameters in this category',
            style: const TextStyle(color: Color(0xFF8B949E), fontSize: 15),
          ),
        ],
      ),
    );
  }
}

class _ParamLiveState {
  final int? decimalValue;
  final String? hexValue;
  final DateTime readTime;
  final bool hasError;
  final String? errorMessage;

  _ParamLiveState({
    required this.decimalValue,
    required this.hexValue,
    required this.readTime,
    required this.hasError,
    this.errorMessage,
  });
}
