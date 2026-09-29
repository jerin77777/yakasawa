#!/usr/bin/env python3
"""
Yaskawa GA700 Parameter Code Generation Script
==============================================
Reads `params.json` and automatically generates:
1. Flutter Frontend Data Model & Metadata (`frontend/lib/generated_params_data.dart`)
2. Flutter Frontend Parameter Explorer Screen with Multi-Page Navigation (`frontend/lib/param_explorer_screen.dart`)
3. Flutter Frontend Main Entrypoint (`frontend/lib/main.dart`)
4. ESP-IDF C Parameter Definitions & Lookup (`main/generated_params.h`, `main/generated_params.c`)
5. ESP-IDF REST API Handlers for Reading/Editing (`main/param_handlers.h`, `main/param_handlers.c`)
6. Standalone Web Parameter Browser (`frontend/web/param_browser.html`)
"""

import os
import sys
import json
import argparse
from typing import Dict, List, Any


def load_params_json(file_path: str) -> Dict[str, Any]:
    if not os.path.exists(file_path):
        fallback_params = os.path.join("params", file_path)
        if os.path.exists(fallback_params):
            file_path = fallback_params
        else:
            raise FileNotFoundError(f"Params file not found: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def parse_and_normalize_params(raw_data: Dict[str, Any]):
    sections = []
    flat_params = []
    total_count = 0

    for sec_id, sec_data in raw_data.items():
        sec_name = sec_data.get("name", f"Section {sec_id}")
        sec_page = sec_data.get("page", 0)
        raw_subgroups = sec_data.get("parameters", {})

        subgroups = []
        for grp_id, grp_data in raw_subgroups.items():
            if not isinstance(grp_data, dict):
                continue
            grp_name = grp_data.get("name", grp_id)
            grp_page = grp_data.get("page", sec_page)
            raw_param_list = grp_data.get("parameters", [])

            param_items = []
            for p in raw_param_list:
                param_code = p.get("param", "").strip()
                param_name = p.get("name", "").strip()
                addr_str = (p.get("address") or p.get("adddress") or "").strip()

                if not addr_str:
                    hex_str = p.get("hex", "").strip()
                    if hex_str:
                        addr_str = f"0x{hex_str}"

                try:
                    addr_int = int(addr_str, 16) if addr_str.startswith("0x") else int(addr_str, 10)
                except ValueError:
                    continue

                hex_formatted = f"0x{addr_int:04X}"
                page = p.get("page", grp_page)

                item = {
                    "code": param_code,
                    "name": param_name,
                    "address_hex": hex_formatted,
                    "address_dec": addr_int,
                    "page": page,
                    "section_id": sec_id,
                    "section_name": sec_name,
                    "group_id": grp_id,
                    "group_name": grp_name,
                    "range": p.get("range", "").strip(),
                    "decimals": int(p.get("decimals", 0)),
                    "multiplier": float(p.get("multiplier", 1.0)),
                    "unit": p.get("unit", "").strip(),
                }
                param_items.append(item)
                flat_params.append(item)
                total_count += 1

            subgroups.append({
                "id": grp_id,
                "name": grp_name,
                "page": grp_page,
                "params": param_items
            })

        sections.append({
            "id": sec_id,
            "name": sec_name,
            "page": sec_page,
            "subgroups": subgroups
        })

    flat_params.sort(key=lambda x: x["address_dec"])
    return sections, flat_params, total_count


# =============================================================================
# Generator: Flutter Dart Data File
# =============================================================================
def generate_flutter_data_file(sections: List[Dict[str, Any]], flat_params: List[Dict[str, Any]], out_path: str):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    lines = []
    lines.append("// AUTO-GENERATED FILE BY generate_code.py - DO NOT EDIT MANUALLY")
    lines.append("// Total Parameters: %d" % len(flat_params))
    lines.append("// Target: Yaskawa GA700 VFD Controller")
    lines.append("")
    lines.append("class YaskawaParam {")
    lines.append("  final String code;        // e.g. A1-00")
    lines.append("  final String name;        // e.g. Language Selection")
    lines.append("  final String hexAddress;  // e.g. 0x0100")
    lines.append("  final int address;        // e.g. 256")
    lines.append("  final int page;           // e.g. 8")
    lines.append("  final String sectionId;   // e.g. 10.4")
    lines.append("  final String groupId;     // e.g. A1")
    lines.append("  final String range;       // e.g. 0-12")
    lines.append("  final int decimals;       // e.g. 2 for 0.01Hz")
    lines.append("  final double multiplier;  // e.g. 0.01 for 0.01Hz")
    lines.append("  final String unit;        // e.g. Hz")
    lines.append("")
    lines.append("  const YaskawaParam({")
    lines.append("    required this.code,")
    lines.append("    required this.name,")
    lines.append("    required this.hexAddress,")
    lines.append("    required this.address,")
    lines.append("    required this.page,")
    lines.append("    required this.sectionId,")
    lines.append("    required this.groupId,")
    lines.append("    this.range = '',")
    lines.append("    this.decimals = 0,")
    lines.append("    this.multiplier = 1.0,")
    lines.append("    this.unit = '',")
    lines.append("  });")
    lines.append("")
    lines.append("  String formatLiveValue(int rawValue) {")
    lines.append("    if (decimals == 0 || multiplier == 1.0) {")
    lines.append("      if (unit.isNotEmpty) {")
    lines.append("        return '$rawValue $unit';")
    lines.append("      }")
    lines.append("      return '$rawValue';")
    lines.append("    }")
    lines.append("    final scaled = rawValue * multiplier;")
    lines.append("    final formatted = scaled.toStringAsFixed(decimals);")
    lines.append("    if (unit.isNotEmpty) {")
    lines.append("      return '$formatted $unit';")
    lines.append("    }")
    lines.append("    return formatted;")
    lines.append("  }")
    lines.append("")
    lines.append("  int? parseUserInputToRaw(String input) {")
    lines.append("    input = input.trim();")
    lines.append("    if (input.isEmpty) return null;")
    lines.append("    if (input.startsWith('0x') || input.startsWith('0X')) {")
    lines.append("      return int.tryParse(input.substring(2), radix: 16);")
    lines.append("    }")
    lines.append("    final numVal = double.tryParse(input);")
    lines.append("    if (numVal == null) return null;")
    lines.append("    if (decimals == 0 || multiplier == 1.0) {")
    lines.append("      return numVal.round();")
    lines.append("    }")
    lines.append("    return (numVal / multiplier).round();")
    lines.append("  }")
    lines.append("}")
    lines.append("")
    lines.append("class YaskawaSubGroup {")
    lines.append("  final String id;          // e.g. A1")
    lines.append("  final String name;        // e.g. Initialization")
    lines.append("  final int page;           // e.g. 400")
    lines.append("  final List<YaskawaParam> params;")
    lines.append("")
    lines.append("  const YaskawaSubGroup({")
    lines.append("    required this.id,")
    lines.append("    required this.name,")
    lines.append("    required this.page,")
    lines.append("    required this.params,")
    lines.append("  });")
    lines.append("}")
    lines.append("")
    lines.append("class YaskawaSection {")
    lines.append("  final String id;          // e.g. 10.4")
    lines.append("  final String name;        // e.g. A: Initialization Parameters")
    lines.append("  final int page;           // e.g. 400")
    lines.append("  final List<YaskawaSubGroup> subGroups;")
    lines.append("")
    lines.append("  const YaskawaSection({")
    lines.append("    required this.id,")
    lines.append("    required this.name,")
    lines.append("    required this.page,")
    lines.append("    required this.subGroups,")
    lines.append("  });")
    lines.append("")
    lines.append("  int get totalParamsCount =>")
    lines.append("      subGroups.fold(0, (sum, g) => sum + g.params.length);")
    lines.append("}")
    lines.append("")
    lines.append("const List<YaskawaSection> kYaskawaSections = [")
    for sec in sections:
        lines.append("  YaskawaSection(")
        lines.append("    id: %s," % json.dumps(sec["id"]))
        lines.append("    name: %s," % json.dumps(sec["name"]))
        lines.append("    page: %d," % sec["page"])
        lines.append("    subGroups: [")
        for grp in sec["subgroups"]:
            lines.append("      YaskawaSubGroup(")
            lines.append("        id: %s," % json.dumps(grp["id"]))
            lines.append("        name: %s," % json.dumps(grp["name"]))
            lines.append("        page: %d," % grp["page"])
            lines.append("        params: [")
            for p in grp["params"]:
                escaped_name = json.dumps(p["name"])
                escaped_range = json.dumps(p.get("range", ""))
                lines.append(
                    "          YaskawaParam(code: '%s', name: %s, hexAddress: '%s', address: %d, page: %d, sectionId: '%s', groupId: '%s', range: %s, decimals: %d, multiplier: %s, unit: %s),"
                    % (p["code"], escaped_name, p["address_hex"], p["address_dec"], p["page"], p["section_id"], p["group_id"], escaped_range, p.get("decimals", 0), str(p.get("multiplier", 1.0)), json.dumps(p.get("unit", "")))
                )
            lines.append("        ],")
            lines.append("      ),")
        lines.append("    ],")
        lines.append("  ),")
    lines.append("];")
    lines.append("")
    lines.append("final Map<String, YaskawaParam> kParamsByCode = {")
    lines.append("  for (final sec in kYaskawaSections)")
    lines.append("    for (final grp in sec.subGroups)")
    lines.append("      for (final p in grp.params)")
    lines.append("        p.code: p,")
    lines.append("};")
    lines.append("")
    lines.append("final Map<int, YaskawaParam> kParamsByAddress = {")
    lines.append("  for (final sec in kYaskawaSections)")
    lines.append("    for (final grp in sec.subGroups)")
    lines.append("      for (final p in grp.params)")
    lines.append("        p.address: p,")
    lines.append("};")
    lines.append("")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Generated Dart data file: {out_path} ({len(flat_params)} params)")


# =============================================================================
# Generator: Flutter Dart UI Screen (Drill-Down Multi-Page with Back Option)
# =============================================================================
def generate_flutter_screen_file(out_path: str):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    code = '''// AUTO-GENERATED FILE BY generate_code.py - DO NOT EDIT MANUALLY
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
'''
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"Generated Dart UI screen (multi-page navigation): {out_path}")


# =============================================================================
# Generator: Flutter Main App File
# =============================================================================
def generate_flutter_main_file(out_path: str):
    code = '''import 'dart:async';
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
'''
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"Generated Dart Main App: {out_path}")

def generate_esp_c_files(sections: List[Dict[str, Any]], flat_params: List[Dict[str, Any]], esp_dir: str):
    os.makedirs(esp_dir, exist_ok=True)
    header_path = os.path.join(esp_dir, "generated_params.h")
    source_path = os.path.join(esp_dir, "generated_params.c")

    h_lines = []
    h_lines.append("/**")
    h_lines.append(" * @file generated_params.h")
    h_lines.append(" * @brief Auto-generated Yaskawa GA700 Parameter Database & Lookup")
    h_lines.append(" * Generated by generate_code.py. Total parameters: %d" % len(flat_params))
    h_lines.append(" */")
    h_lines.append("")
    h_lines.append("#ifndef GENERATED_PARAMS_H")
    h_lines.append("#define GENERATED_PARAMS_H")
    h_lines.append("")
    h_lines.append("#include <stdint.h>")
    h_lines.append("#include <stdbool.h>")
    h_lines.append("#include <stddef.h>")
    h_lines.append("")
    h_lines.append("#ifdef __cplusplus")
    h_lines.append("extern \"C\" {")
    h_lines.append("#endif")
    h_lines.append("")
    h_lines.append("#define GA700_PARAM_COUNT %d" % len(flat_params))
    h_lines.append("")
    h_lines.append("typedef struct {")
    h_lines.append("    const char *code;        // e.g. \"A1-00\"")
    h_lines.append("    const char *name;        // e.g. \"Language Selection\"")
    h_lines.append("    uint16_t address;        // e.g. 0x0100")
    h_lines.append("    uint16_t page;           // e.g. 8")
    h_lines.append("    const char *section_id;  // e.g. \"10.4\"")
    h_lines.append("    const char *group_id;    // e.g. \"A1\"")
    h_lines.append("} ga700_param_meta_t;")
    h_lines.append("")
    h_lines.append("extern const ga700_param_meta_t g_ga700_params[GA700_PARAM_COUNT];")
    h_lines.append("")
    h_lines.append("const ga700_param_meta_t* ga700_find_param_by_addr(uint16_t addr);")
    h_lines.append("const ga700_param_meta_t* ga700_find_param_by_code(const char *code);")
    h_lines.append("bool ga700_is_valid_param_addr(uint16_t addr);")
    h_lines.append("")
    h_lines.append("#ifdef __cplusplus")
    h_lines.append("}")
    h_lines.append("#endif")
    h_lines.append("")
    h_lines.append("#endif // GENERATED_PARAMS_H")
    h_lines.append("")

    with open(header_path, "w", encoding="utf-8") as f:
        f.write("\n".join(h_lines))
    print(f"Generated ESP header: {header_path}")

    c_lines = []
    c_lines.append("/**")
    c_lines.append(" * @file generated_params.c")
    c_lines.append(" * @brief Auto-generated Yaskawa GA700 Parameter Database Implementation")
    c_lines.append(" */")
    c_lines.append("")
    c_lines.append("#include <string.h>")
    c_lines.append("#include \"generated_params.h\"")
    c_lines.append("")
    c_lines.append("const ga700_param_meta_t g_ga700_params[GA700_PARAM_COUNT] = {")
    for p in flat_params:
        esc_name = json.dumps(p["name"])
        c_lines.append(
            '    { "%s", %s, %s, %d, "%s", "%s" },'
            % (p["code"], esc_name, p["address_hex"], p["page"], p["section_id"], p["group_id"])
        )
    c_lines.append("};")
    c_lines.append("")
    c_lines.append("const ga700_param_meta_t* ga700_find_param_by_addr(uint16_t addr)")
    c_lines.append("{")
    c_lines.append("    int low = 0;")
    c_lines.append("    int high = GA700_PARAM_COUNT - 1;")
    c_lines.append("    while (low <= high) {")
    c_lines.append("        int mid = low + (high - low) / 2;")
    c_lines.append("        if (g_ga700_params[mid].address == addr) {")
    c_lines.append("            return &g_ga700_params[mid];")
    c_lines.append("        } else if (g_ga700_params[mid].address < addr) {")
    c_lines.append("            low = mid + 1;")
    c_lines.append("        } else {")
    c_lines.append("            high = mid - 1;")
    c_lines.append("        }")
    c_lines.append("    }")
    c_lines.append("    return NULL;")
    c_lines.append("}")
    c_lines.append("")
    c_lines.append("const ga700_param_meta_t* ga700_find_param_by_code(const char *code)")
    c_lines.append("{")
    c_lines.append("    if (code == NULL) return NULL;")
    c_lines.append("    for (size_t i = 0; i < GA700_PARAM_COUNT; i++) {")
    c_lines.append("        if (strcasecmp(g_ga700_params[i].code, code) == 0) {")
    c_lines.append("            return &g_ga700_params[i];")
    c_lines.append("        }")
    c_lines.append("    }")
    c_lines.append("    return NULL;")
    c_lines.append("}")
    c_lines.append("")
    c_lines.append("bool ga700_is_valid_param_addr(uint16_t addr)")
    c_lines.append("{")
    c_lines.append("    return (ga700_find_param_by_addr(addr) != NULL);")
    c_lines.append("}")
    c_lines.append("")

    with open(source_path, "w", encoding="utf-8") as f:
        f.write("\n".join(c_lines))
    print(f"Generated ESP source: {source_path}")


# =============================================================================
# Generator: ESP-IDF Parameter REST API Handlers
# =============================================================================
def generate_esp_handlers(esp_dir: str):
    header_path = os.path.join(esp_dir, "param_handlers.h")
    source_path = os.path.join(esp_dir, "param_handlers.c")

    h_code = '''#ifndef PARAM_HANDLERS_H
#define PARAM_HANDLERS_H

#include "esp_err.h"
#include "esp_http_server.h"

#ifdef __cplusplus
extern "C" {
#endif

esp_err_t register_param_api_endpoints(httpd_handle_t server);

#ifdef __cplusplus
}
#endif

#endif // PARAM_HANDLERS_H
'''
    with open(header_path, "w", encoding="utf-8") as f:
        f.write(h_code)
    print(f"Generated ESP API handler header: {header_path}")

    c_code = '''#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "esp_log.h"
#include "esp_http_server.h"
#include "ga700_modbus.h"
#include "generated_params.h"
#include "param_handlers.h"

static const char *TAG = "PARAM_API";

static esp_err_t set_cors_headers(httpd_req_t *req)
{
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Methods", "GET, POST, OPTIONS");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Headers", "Content-Type, Authorization, Accept");
    httpd_resp_set_hdr(req, "Access-Control-Max-Age", "86400");
    return ESP_OK;
}

static esp_err_t param_options_handler(httpd_req_t *req)
{
    set_cors_headers(req);
    httpd_resp_set_status(req, "204 No Content");
    httpd_resp_send(req, NULL, 0);
    return ESP_OK;
}

static bool parse_param_address(httpd_req_t *req, uint16_t *out_addr, const ga700_param_meta_t **out_meta)
{
    if (out_addr == NULL) return false;
    *out_addr = 0;
    if (out_meta) *out_meta = NULL;

    size_t qry_len = httpd_req_get_url_query_len(req);
    if (qry_len > 0) {
        char *qry = malloc(qry_len + 1);
        if (qry != NULL) {
            if (httpd_req_get_url_query_str(req, qry, qry_len + 1) == ESP_OK) {
                char val_str[64];
                if (httpd_query_key_value(qry, "addr", val_str, sizeof(val_str)) == ESP_OK ||
                    httpd_query_key_value(qry, "address", val_str, sizeof(val_str)) == ESP_OK) {
                    if (strncmp(val_str, "0x", 2) == 0 || strncmp(val_str, "0X", 2) == 0) {
                        *out_addr = (uint16_t)strtoul(val_str, NULL, 16);
                    } else {
                        *out_addr = (uint16_t)strtoul(val_str, NULL, 10);
                    }
                    if (out_meta) *out_meta = ga700_find_param_by_addr(*out_addr);
                    free(qry);
                    return true;
                }
                if (httpd_query_key_value(qry, "param", val_str, sizeof(val_str)) == ESP_OK ||
                    httpd_query_key_value(qry, "code", val_str, sizeof(val_str)) == ESP_OK) {
                    const ga700_param_meta_t *meta = ga700_find_param_by_code(val_str);
                    if (meta != NULL) {
                        *out_addr = meta->address;
                        if (out_meta) *out_meta = meta;
                        free(qry);
                        return true;
                    }
                }
            }
            free(qry);
        }
    }
    return false;
}

static esp_err_t api_get_param_handler(httpd_req_t *req)
{
    set_cors_headers(req);
    httpd_resp_set_type(req, "application/json");

    uint16_t reg_addr = 0;
    const ga700_param_meta_t *meta = NULL;

    if (!parse_param_address(req, &reg_addr, &meta)) {
        httpd_resp_set_status(req, "400 Bad Request");
        const char *err = "{\\"status\\":\\"error\\",\\"message\\":\\"Missing or invalid 'addr' or 'code' parameter\\"}";
        return httpd_resp_send(req, err, HTTPD_RESP_USE_STRLEN);
    }

    uint16_t reg_val = 0;
    esp_err_t err = ga700_read_holding_register(reg_addr, &reg_val);

    char resp[350];
    if (err == ESP_OK) {
        snprintf(resp, sizeof(resp),
            "{\\"status\\":\\"ok\\",\\"code\\":\\"%s\\",\\"name\\":\\"%s\\",\\"address\\":\\"0x%04X\\",\\"address_dec\\":%u,\\"value\\":%u,\\"hex_value\\":\\"0x%04X\\"}",
            meta ? meta->code : "UNKNOWN",
            meta ? meta->name : "Custom Register",
            reg_addr, reg_addr,
            reg_val, reg_val);
        return httpd_resp_send(req, resp, HTTPD_RESP_USE_STRLEN);
    } else {
        snprintf(resp, sizeof(resp),
            "{\\"status\\":\\"error\\",\\"address\\":\\"0x%04X\\",\\"error\\":\\"%s\\",\\"message\\":\\"Modbus read failed\\"}",
            reg_addr, esp_err_to_name(err));
        httpd_resp_set_status(req, "500 Internal Server Error");
        return httpd_resp_send(req, resp, HTTPD_RESP_USE_STRLEN);
    }
}

static esp_err_t api_post_param_handler(httpd_req_t *req)
{
    set_cors_headers(req);
    httpd_resp_set_type(req, "application/json");

    uint16_t reg_addr = 0;
    uint16_t reg_val = 0;
    bool has_addr = false;
    bool has_val = false;

    size_t qry_len = httpd_req_get_url_query_len(req);
    if (qry_len > 0) {
        char *qry = malloc(qry_len + 1);
        if (qry && httpd_req_get_url_query_str(req, qry, qry_len + 1) == ESP_OK) {
            char val_str[64];
            if (httpd_query_key_value(qry, "addr", val_str, sizeof(val_str)) == ESP_OK ||
                httpd_query_key_value(qry, "address", val_str, sizeof(val_str)) == ESP_OK) {
                reg_addr = (val_str[0] == '0' && (val_str[1] == 'x' || val_str[1] == 'X'))
                    ? (uint16_t)strtoul(val_str, NULL, 16)
                    : (uint16_t)strtoul(val_str, NULL, 10);
                has_addr = true;
            }
            if (httpd_query_key_value(qry, "val", val_str, sizeof(val_str)) == ESP_OK ||
                httpd_query_key_value(qry, "value", val_str, sizeof(val_str)) == ESP_OK) {
                reg_val = (val_str[0] == '0' && (val_str[1] == 'x' || val_str[1] == 'X'))
                    ? (uint16_t)strtoul(val_str, NULL, 16)
                    : (uint16_t)strtoul(val_str, NULL, 10);
                has_val = true;
            }
            free(qry);
        }
    }

    if (!has_addr || !has_val) {
        int total_len = req->content_len;
        if (total_len > 0 && total_len < 1024) {
            char body[256];
            int received = httpd_req_recv(req, body, sizeof(body) - 1);
            if (received > 0) {
                body[received] = '\\0';
                char *addr_pos = strstr(body, "\\"address\\"");
                if (!addr_pos) addr_pos = strstr(body, "\\"addr\\"");
                if (addr_pos) {
                    char *col = strchr(addr_pos, ':');
                    if (col) {
                        while (*col == ':' || *col == ' ' || *col == '\"') col++;
                        if (strncmp(col, "0x", 2) == 0 || strncmp(col, "0X", 2) == 0) {
                            reg_addr = (uint16_t)strtoul(col, NULL, 16);
                        } else {
                            reg_addr = (uint16_t)strtoul(col, NULL, 10);
                        }
                        has_addr = true;
                    }
                }

                char *val_pos = strstr(body, "\\"value\\"");
                if (!val_pos) val_pos = strstr(body, "\\"val\\"");
                if (val_pos) {
                    char *col = strchr(val_pos, ':');
                    if (col) {
                        while (*col == ':' || *col == ' ' || *col == '\"') col++;
                        if (strncmp(col, "0x", 2) == 0 || strncmp(col, "0X", 2) == 0) {
                            reg_val = (uint16_t)strtoul(col, NULL, 16);
                        } else {
                            reg_val = (uint16_t)strtoul(col, NULL, 10);
                        }
                        has_val = true;
                    }
                }
            }
        }
    }

    if (!has_addr || !has_val) {
        httpd_resp_set_status(req, "400 Bad Request");
        const char *err = "{\\"status\\":\\"error\\",\\"message\\":\\"Missing 'address' or 'value' in request\\"}";
        return httpd_resp_send(req, err, HTTPD_RESP_USE_STRLEN);
    }

    ESP_LOGI(TAG, "Writing register 0x%04X = %u (0x%04X)", reg_addr, reg_val, reg_val);
    esp_err_t err = ga700_write_single_register(reg_addr, reg_val);

    const ga700_param_meta_t *meta = ga700_find_param_by_addr(reg_addr);
    char resp[350];
    if (err == ESP_OK) {
        snprintf(resp, sizeof(resp),
            "{\\"status\\":\\"ok\\",\\"code\\":\\"%s\\",\\"name\\":\\"%s\\",\\"address\\":\\"0x%04X\\",\\"address_dec\\":%u,\\"written_value\\":%u,\\"hex_value\\":\\"0x%04X\\"}",
            meta ? meta->code : "UNKNOWN",
            meta ? meta->name : "Custom Register",
            reg_addr, reg_addr,
            reg_val, reg_val);
        return httpd_resp_send(req, resp, HTTPD_RESP_USE_STRLEN);
    } else {
        snprintf(resp, sizeof(resp),
            "{\\"status\\":\\"error\\",\\"address\\":\\"0x%04X\\",\\"error\\":\\"%s\\",\\"message\\":\\"Modbus write failed\\"}",
            reg_addr, esp_err_to_name(err));
        httpd_resp_set_status(req, "500 Internal Server Error");
        return httpd_resp_send(req, resp, HTTPD_RESP_USE_STRLEN);
    }
}

esp_err_t register_param_api_endpoints(httpd_handle_t server)
{
    if (server == NULL) return ESP_ERR_INVALID_ARG;

    httpd_uri_t uri_opt = {
        .uri      = "/api/param",
        .method   = HTTP_OPTIONS,
        .handler  = param_options_handler,
        .user_ctx = NULL
    };
    httpd_register_uri_handler(server, &uri_opt);

    httpd_uri_t uri_get = {
        .uri      = "/api/param",
        .method   = HTTP_GET,
        .handler  = api_get_param_handler,
        .user_ctx = NULL
    };
    httpd_register_uri_handler(server, &uri_get);

    httpd_uri_t uri_post = {
        .uri      = "/api/param",
        .method   = HTTP_POST,
        .handler  = api_post_param_handler,
        .user_ctx = NULL
    };
    httpd_register_uri_handler(server, &uri_post);

    ESP_LOGI(TAG, "Parameter REST API Endpoints registered (/api/param GET/POST/OPTIONS)");
    return ESP_OK;
}
'''
    with open(source_path, "w", encoding="utf-8") as f:
        f.write(c_code)
    print(f"Generated ESP API handler source: {source_path}")


# =============================================================================
# Generator: Standalone Single-Page Web Parameter Explorer (Drill-Down with Back)
# =============================================================================
def generate_web_explorer(sections: List[Dict[str, Any]], flat_params: List[Dict[str, Any]], out_path: str):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    json_data = json.dumps(sections)

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Yaskawa GA700 Parameter Explorer</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root {{
      --bg: #f8fafc;
      --card-bg: #ffffff;
      --border: #e2e8f0;
      --text: #0f172a;
      --text-muted: #64748b;
      --accent: #2563eb;
      --accent-soft: #eff6ff;
      --accent-border: #bfdbfe;
      --green: #059669;
      --green-soft: #ecfdf5;
      --red: #dc2626;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
    }}
    /* Topbar */
    .topbar {{
      padding: 14px 24px;
      background: var(--card-bg);
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}
    .brand-badge {{
      background: var(--accent-soft);
      color: var(--accent);
      border: 1px solid var(--accent-border);
      padding: 4px 8px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: bold;
      letter-spacing: 1px;
    }}
    .back-btn {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 7px 14px;
      background: var(--accent-soft);
      color: var(--accent);
      border: 1px solid var(--accent-border);
      border-radius: 6px;
      cursor: pointer;
      font-weight: 600;
      font-size: 13px;
      transition: background 0.15s;
    }}
    .back-btn:hover {{ background: #dbeafe; }}
    .search-input {{
      padding: 8px 14px;
      width: 300px;
      background: #f8fafc;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      color: var(--text);
      font-size: 13px;
    }}
    .search-input:focus {{ outline: none; border-color: var(--accent); }}
    /* Main View Area */
    .view-container {{
      flex: 1;
      overflow-y: auto;
      padding: 24px;
    }}
    /* Sections Grid / List (Level 1) */
    .sections-grid {{
      display: flex;
      flex-direction: column;
      gap: 12px;
      max-width: 900px;
      margin: 0 auto;
    }}
    .section-card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 18px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      cursor: pointer;
      box-shadow: 0 1px 4px rgba(0,0,0,0.04);
      transition: transform 0.15s, box-shadow 0.15s, border-color 0.15s;
    }}
    .section-card:hover {{
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(37,99,235,0.08);
      border-color: var(--accent-border);
    }}
    .sec-id-box {{
      width: 54px;
      height: 54px;
      background: var(--accent-soft);
      border: 1px solid var(--accent-border);
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: monospace;
      font-size: 16px;
      font-weight: bold;
      color: var(--accent);
      margin-right: 18px;
    }}
    .sec-meta-pill {{
      display: inline-block;
      padding: 2px 8px;
      background: #f1f5f9;
      border-radius: 4px;
      font-size: 11px;
      color: var(--text-muted);
      margin-right: 8px;
    }}
    .count-pill {{
      padding: 4px 12px;
      background: var(--accent-soft);
      border: 1px solid var(--accent-border);
      color: var(--accent);
      border-radius: 20px;
      font-size: 12px;
      font-weight: 600;
    }}
    /* Params View (Level 2) */
    .chips-bar {{
      padding: 10px 0;
      margin-bottom: 16px;
      display: flex;
      gap: 8px;
      overflow-x: auto;
      white-space: nowrap;
    }}
    .chip {{
      padding: 6px 14px;
      background: var(--card-bg);
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      font-size: 12px;
      cursor: pointer;
      color: #334155;
    }}
    .chip.active {{
      background: var(--accent);
      color: #fff;
      font-weight: 600;
      border-color: var(--accent);
    }}
    .param-card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 14px 18px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 10px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }}
    .code-badge {{
      font-family: monospace;
      font-weight: bold;
      font-size: 14px;
      color: var(--accent);
      background: var(--accent-soft);
      border: 1px solid var(--accent-border);
      padding: 6px 10px;
      border-radius: 6px;
      text-align: center;
      width: 82px;
    }}
    .param-info {{ flex: 1; padding: 0 16px; }}
    .param-name {{ font-weight: 600; font-size: 14px; color: var(--text); margin-bottom: 4px; }}
    .param-meta {{ font-size: 12px; color: var(--text-muted); font-family: monospace; }}
    .val-box {{
      font-family: monospace;
      font-size: 14px;
      font-weight: bold;
      padding: 6px 14px;
      background: #f8fafc;
      border: 1px solid var(--border);
      border-radius: 6px;
      margin-right: 12px;
      min-width: 90px;
      text-align: center;
      color: var(--text-muted);
    }}
    .val-box.has-val {{ color: var(--green); background: var(--green-soft); border-color: #a7f3d0; }}
    .btn {{
      padding: 8px 16px;
      font-weight: 600;
      font-size: 12px;
      border-radius: 6px;
      cursor: pointer;
      margin-left: 6px;
    }}
    .btn-read {{ background: transparent; color: var(--accent); border: 1px solid var(--accent); }}
    .btn-read:hover {{ background: var(--accent-soft); }}
    .btn-edit {{ background: var(--accent); color: #fff; border: 1px solid var(--accent); }}
    .btn-edit:hover {{ opacity: 0.9; }}
    /* Modal */
    .modal-overlay {{
      display: none;
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(15,23,42,0.5);
      align-items: center;
      justify-content: center;
      z-index: 1000;
    }}
    .modal {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 24px;
      width: 440px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.15);
    }}
  </style>
</head>
<body>
  <div class="topbar">
    <div style="display: flex; align-items: center; gap: 12px;">
      <span class="brand-badge">GA700</span>
      <div id="topTitleArea">
        <h2 style="font-size: 17px; color: var(--text);">Yaskawa Parameter Explorer</h2>
        <div style="font-size: 11px; color: var(--text-muted);">Direct Modbus Register Management</div>
      </div>
    </div>
    <div style="display: flex; align-items: center; gap: 12px;">
      <button class="back-btn" id="backBtn" style="display: none;" onclick="goBackToSections()">
        &#8592; Back to Sections
      </button>
      <input type="text" id="searchInput" class="search-input" placeholder="Search code, name, 0xADDR...">
    </div>
  </div>

  <div class="view-container">
    <div id="sectionsView">
      <div class="sections-grid" id="sectionsList"></div>
    </div>
    <div id="paramsView" style="display: none; max-width: 1000px; margin: 0 auto;">
      <div class="chips-bar" id="subgroupChips"></div>
      <div id="paramsList"></div>
    </div>
  </div>

  <!-- Edit Modal -->
  <div class="modal-overlay" id="editModal">
    <div class="modal">
      <h3 id="modalTitle" style="color: var(--accent); margin-bottom: 8px;">Edit Parameter</h3>
      <div id="modalDesc" style="color: var(--text-muted); font-size: 13px; margin-bottom: 16px;"></div>
      <label style="display:block; font-size: 12px; color: var(--text-muted); margin-bottom: 6px; font-weight: 600;">New Value (Decimal or 0xHEX):</label>
      <input type="text" id="modalInput" style="width: 100%; padding: 10px; background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; color: var(--text); font-family: monospace; font-size: 16px; margin-bottom: 16px;">
      <div style="display: flex; justify-content: flex-end; gap: 8px;">
        <button class="btn" style="background:#f1f5f9; color:#475569; border: 1px solid #e2e8f0;" onclick="closeModal()">Cancel</button>
        <button class="btn btn-edit" onclick="submitEdit()">Write to VFD</button>
      </div>
    </div>
  </div>

  <script>
    const SECTIONS = {json_data};
    let currentSectionIdx = null;
    let activeSubId = 'ALL';
    let currentEditParam = null;
    const liveValues = {{}};

    function init() {{
      renderSections();
      document.getElementById('searchInput').oninput = handleSearch;
    }}

    function renderSections() {{
      const list = document.getElementById('sectionsList');
      list.innerHTML = '';
      SECTIONS.forEach((sec, idx) => {{
        const total = sec.subgroups.reduce((s, g) => s + g.params.length, 0);
        const card = document.createElement('div');
        card.className = 'section-card';
        card.onclick = () => openSection(idx);
        card.innerHTML = `
          <div style="display: flex; align-items: center;">
            <div class="sec-id-box">${{sec.id}}</div>
            <div>
              <div style="font-weight: bold; font-size: 16px; color: var(--text);">${{sec.name}}</div>
              <div style="margin-top: 4px;">
                <span class="sec-meta-pill">${{sec.subgroups.length}} Subgroups</span>
                <span class="sec-meta-pill">Page ${{sec.page}}</span>
              </div>
            </div>
          </div>
          <div style="display: flex; align-items: center; gap: 12px;">
            <span class="count-pill">${{total}} Params</span>
            <span style="color: var(--text-muted);">&#8250;</span>
          </div>
        `;
        list.appendChild(card);
      }});
    }}

    function openSection(idx) {{
      currentSectionIdx = idx;
      activeSubId = 'ALL';
      document.getElementById('sectionsView').style.display = 'none';
      document.getElementById('paramsView').style.display = 'block';
      document.getElementById('backBtn').style.display = 'inline-flex';

      const sec = SECTIONS[idx];
      document.getElementById('topTitleArea').innerHTML = `
        <h2 style="font-size: 17px; color: var(--text);">${{sec.id}}: ${{sec.name}}</h2>
        <div style="font-size: 11px; color: var(--text-muted);">Page ${{sec.page}} • Parameters in this nest</div>
      `;

      renderChips();
      renderParams();
    }}

    function goBackToSections() {{
      currentSectionIdx = null;
      document.getElementById('paramsView').style.display = 'none';
      document.getElementById('sectionsView').style.display = 'block';
      document.getElementById('backBtn').style.display = 'none';

      document.getElementById('topTitleArea').innerHTML = `
        <h2 style="font-size: 17px; color: var(--text);">Yaskawa Parameter Explorer</h2>
        <div style="font-size: 11px; color: var(--text-muted);">Direct Modbus Register Management</div>
      `;
      renderSections();
    }}

    function renderChips() {{
      const bar = document.getElementById('subgroupChips');
      bar.innerHTML = '';
      const sec = SECTIONS[currentSectionIdx];
      const allChip = document.createElement('div');
      allChip.className = 'chip' + (activeSubId === 'ALL' ? ' active' : '');
      allChip.innerText = 'All';
      allChip.onclick = () => {{ activeSubId = 'ALL'; renderChips(); renderParams(); }};
      bar.appendChild(allChip);

      sec.subgroups.forEach(g => {{
        const chip = document.createElement('div');
        chip.className = 'chip' + (activeSubId === g.id ? ' active' : '');
        chip.innerText = `${{g.id}}: ${{g.name}} (${{g.params.length}})`;
        chip.onclick = () => {{ activeSubId = g.id; renderChips(); renderParams(); }};
        bar.appendChild(chip);
      }});
    }}

    function renderParams() {{
      const container = document.getElementById('paramsList');
      container.innerHTML = '';
      const sec = SECTIONS[currentSectionIdx];
      const q = document.getElementById('searchInput').value.trim().toLowerCase();

      let list = [];
      sec.subgroups.forEach(g => {{
        if (activeSubId === 'ALL' || activeSubId === g.id) {{
          list.push(...g.params);
        }}
      }});

      if (q) {{
        list = list.filter(p => p.code.toLowerCase().includes(q) || p.name.toLowerCase().includes(q) || p.address_hex.toLowerCase().includes(q));
      }}

      list.forEach(p => {{
        const card = document.createElement('div');
        card.className = 'param-card';
        card.dataset.hex = p.address_hex;
        card.dataset.code = p.code;
        const val = liveValues[p.address_hex] !== undefined ? liveValues[p.address_hex] : '--';
        const valClass = liveValues[p.address_hex] !== undefined ? 'val-box has-val' : 'val-box';

        card.innerHTML = `
          <div class="code-badge">${{p.code}}</div>
          <div class="param-info">
            <div class="param-name">${{p.name}}</div>
            <div class="param-meta">Address: ${{p.address_hex}} (${{p.address_dec}}) • Page ${{p.page}}${{p.range ? ` • <span style="color:#0284c7;font-weight:600;">Range: ${{p.range}}</span>` : ''}}</div>
          </div>
          <div class="${{valClass}}" id="val_${{p.address_hex}}">${{val}}</div>
          <div>
            <button class="btn btn-edit" onclick="openEdit('${{p.address_hex}}', '${{p.code}}', '${{p.name}}')">EDIT</button>
          </div>
        `;
        container.appendChild(card);
      }});
      setupVisibilityObserver();
    }}

    let observer = null;
    function setupVisibilityObserver() {{
      if (observer) observer.disconnect();
      if (!window.IntersectionObserver) return;
      observer = new IntersectionObserver((entries) => {{
        entries.forEach(entry => {{
          if (entry.isIntersecting) {{
            const hex = entry.target.dataset.hex;
            const code = entry.target.dataset.code;
            if (hex && !liveValues[hex]) {{
              readParam(hex, code);
            }}
          }}
        }});
      }}, {{ threshold: 0.1 }});
      document.querySelectorAll('.param-card').forEach(el => observer.observe(el));
    }}

    function handleSearch() {{
      if (currentSectionIdx !== null) {{
        renderParams();
      }}
    }}

    async function readParam(hex, code) {{
      const el = document.getElementById('val_' + hex);
      if (el) el.innerText = '...';
      try {{
        const res = await fetch('/api/param?addr=' + hex);
        const data = await res.json();
        if (data.status === 'ok') {{
          liveValues[hex] = `${{data.value}} (${{data.hex_value}})`;
          if (el) {{ el.innerText = liveValues[hex]; el.className = 'val-box has-val'; }}
        }} else {{
          alert('Read error: ' + (data.message || data.error));
        }}
      }} catch(e) {{
        alert('Network/API error: ' + e);
      }}
    }}

    function openEdit(hex, code, name) {{
      currentEditParam = {{ hex, code }};
      document.getElementById('modalTitle').innerText = `Edit: ${{code}} (${{hex}})`;
      document.getElementById('modalDesc').innerText = name;
      document.getElementById('modalInput').value = liveValues[hex] ? parseInt(liveValues[hex]) : 0;
      document.getElementById('editModal').style.display = 'flex';
    }}

    function closeModal() {{
      document.getElementById('editModal').style.display = 'none';
      currentEditParam = null;
    }}

    async function submitEdit() {{
      if (!currentEditParam) return;
      const valStr = document.getElementById('modalInput').value.trim();
      let val = valStr.startsWith('0x') || valStr.startsWith('0X') ? parseInt(valStr, 16) : parseInt(valStr, 10);
      if (isNaN(val)) {{ alert('Invalid number!'); return; }}

      try {{
        const res = await fetch('/api/param', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ address: currentEditParam.hex, value: val, param: currentEditParam.code }})
        }});
        const data = await res.json();
        if (data.status === 'ok') {{
          liveValues[currentEditParam.hex] = `${{data.written_value}} (${{data.hex_value}})`;
          renderParams();
          closeModal();
        }} else {{
          alert('Write error: ' + (data.message || data.error));
        }}
      }} catch(e) {{
        alert('Write failed: ' + e);
      }}
    }}

    window.onload = init;
  </script>
</body>
</html>
'''
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Generated Web Explorer: {out_path}")


# =============================================================================
# Main Entry Point
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="Yaskawa GA700 Parameter Code Generation Script")
    parser.add_argument("--input", default="params.json", help="Path to params.json")
    parser.add_argument("--frontend-dir", default="frontend/lib", help="Output directory for Flutter lib")
    parser.add_argument("--esp-dir", default="main", help="Output directory for ESP-IDF C source")
    parser.add_argument("--web-out", default="frontend/web/param_browser.html", help="Output path for standalone HTML parameter browser")

    args = parser.parse_args()

    print("==================================================================")
    print(" >>> YASKAWA GA700 PARAMETER CODE GENERATOR <<< ")
    print("==================================================================")
    print(f"Input JSON: {args.input}")

    raw_data = load_params_json(args.input)
    sections, flat_params, total = parse_and_normalize_params(raw_data)

    print(f"Successfully processed {len(sections)} sections and {total} parameters.")

    # 1. Frontend Dart Data
    dart_data_path = os.path.join(args.frontend_dir, "generated_params_data.dart")
    generate_flutter_data_file(sections, flat_params, dart_data_path)

    # 2. Frontend Flutter Screen (Multi-page with Back Option)
    dart_screen_path = os.path.join(args.frontend_dir, "param_explorer_screen.dart")
    generate_flutter_screen_file(dart_screen_path)

    # 3. Frontend Flutter Main App
    dart_main_path = os.path.join(args.frontend_dir, "main.dart")
    generate_flutter_main_file(dart_main_path)

    # 4. ESP-IDF C Parameter Database
    generate_esp_c_files(sections, flat_params, args.esp_dir)

    # 5. ESP-IDF REST API Handlers
    generate_esp_handlers(args.esp_dir)

    # 6. Standalone Web Parameter Explorer
    generate_web_explorer(sections, flat_params, args.web_out)

    print("==================================================================")
    print("All frontend and ESP code successfully generated with correct addresses!")
    print("Multi-page navigation with back button active.")
    print("==================================================================")


if __name__ == "__main__":
    main()
