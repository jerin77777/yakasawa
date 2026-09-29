#!/usr/bin/env python3
"""
Yaskawa GA700 Parameter Code Generation Script
==============================================
Reads `params.json` and automatically generates:
1. Flutter Frontend Data Model & Metadata (`frontend/lib/generated_params_data.dart`)
2. Flutter Frontend Parameter Explorer Screen (`frontend/lib/param_explorer_screen.dart`)
3. ESP-IDF C Parameter Definitions & Lookup (`main/generated_params.h`, `main/generated_params.c`)
4. ESP-IDF REST API Handlers for Reading/Editing (`main/param_handlers.h`, `main/param_handlers.c`)
5. Standalone Web Parameter Browser (`frontend/web/param_browser.html`)
"""

import os
import sys
import json
import argparse
from typing import Dict, List, Any


def load_params_json(file_path: str) -> Dict[str, Any]:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Params file not found: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def parse_and_normalize_params(raw_data: Dict[str, Any]):
    """
    Parses params.json and produces a normalized, structured hierarchy:
    - sections: list of { id, name, page, sub_groups: [ { id, name, page, params: [...] } ] }
    - flat_params: sorted list of all individual parameters
    """
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

    # Sort flat params by address
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
    lines.append("")
    lines.append("  const YaskawaParam({")
    lines.append("    required this.code,")
    lines.append("    required this.name,")
    lines.append("    required this.hexAddress,")
    lines.append("    required this.address,")
    lines.append("    required this.page,")
    lines.append("    required this.sectionId,")
    lines.append("    required this.groupId,")
    lines.append("  });")
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

    # Construct the static list of sections
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
                lines.append(
                    "          YaskawaParam(code: '%s', name: %s, hexAddress: '%s', address: %d, page: %d, sectionId: '%s', groupId: '%s'),"
                    % (p["code"], escaped_name, p["address_hex"], p["address_dec"], p["page"], p["section_id"], p["group_id"])
                )
            lines.append("        ],")
            lines.append("      ),")
        lines.append("    ],")
        lines.append("  ),")
    lines.append("];")
    lines.append("")

    # Add quick lookup map helper
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
# Generator: Flutter Dart UI Screen
# =============================================================================
def generate_flutter_screen_file(out_path: str):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    code = '''// AUTO-GENERATED FILE BY generate_code.py - DO NOT EDIT MANUALLY
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
'''
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"Generated Dart UI screen: {out_path}")


# =============================================================================
# Generator: ESP-IDF C Code (Header & Implementation)
# =============================================================================
def generate_esp_c_files(sections: List[Dict[str, Any]], flat_params: List[Dict[str, Any]], esp_dir: str):
    os.makedirs(esp_dir, exist_ok=True)
    header_path = os.path.join(esp_dir, "generated_params.h")
    source_path = os.path.join(esp_dir, "generated_params.c")

    # Header File
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
    h_lines.append("/**")
    h_lines.append(" * @brief Find parameter metadata by 16-bit register address (Binary search O(log N))")
    h_lines.append(" */")
    h_lines.append("const ga700_param_meta_t* ga700_find_param_by_addr(uint16_t addr);")
    h_lines.append("")
    h_lines.append("/**")
    h_lines.append(" * @brief Find parameter metadata by code (e.g. \"b1-01\")")
    h_lines.append(" */")
    h_lines.append("const ga700_param_meta_t* ga700_find_param_by_code(const char *code);")
    h_lines.append("")
    h_lines.append("/**")
    h_lines.append(" * @brief Check if a register address exists in GA700 parameter database")
    h_lines.append(" */")
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

    # C Source File
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

/**
 * @brief Register parameter REST API endpoints to ESP32 HTTP Server:
 * - GET  /api/param?addr=0x0100 (Read register)
 * - POST /api/param (Write register: {"address":"0x0100","value":1})
 * - OPTIONS /api/param (CORS Preflight)
 * - GET  /params (Embedded Web Parameter Explorer)
 */
esp_err_t register_param_api_endpoints(httpd_handle_t server);

#ifdef __cplusplus
}
#endif

#endif // PARAM_HANDLERS_H
'''
    with open(header_path, "w", encoding="utf-8") as f:
        f.write(h_code)
    print(f"Generated ESP API handler header: {header_path}")

    c_code = '''/**
 * @file param_handlers.c
 * @brief REST API Handlers for Reading and Writing Yaskawa GA700 Parameters
 */

#include <stdio.h>
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

/**
 * Helper to parse target address from query string or JSON
 */
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
                // Check 'addr' or 'address'
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
                // Check 'param' or 'code' (e.g. A1-00)
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

/**
 * GET /api/param?addr=0x0100 (or ?code=A1-00)
 */
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

/**
 * POST /api/param
 * Supports JSON: {"address":"0x0100", "value": 1}
 * or Query: ?addr=0x0100&val=1
 */
static esp_err_t api_post_param_handler(httpd_req_t *req)
{
    set_cors_headers(req);
    httpd_resp_set_type(req, "application/json");

    uint16_t reg_addr = 0;
    uint16_t reg_val = 0;
    bool has_addr = false;
    bool has_val = false;

    // 1. Try URL Query
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

    // 2. Try JSON Body if not found in query
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

    // OPTIONS /api/param
    httpd_uri_t uri_opt = {
        .uri      = "/api/param",
        .method   = HTTP_OPTIONS,
        .handler  = param_options_handler,
        .user_ctx = NULL
    };
    httpd_register_uri_handler(server, &uri_opt);

    // GET /api/param
    httpd_uri_t uri_get = {
        .uri      = "/api/param",
        .method   = HTTP_GET,
        .handler  = api_get_param_handler,
        .user_ctx = NULL
    };
    httpd_register_uri_handler(server, &uri_get);

    // POST /api/param
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
# Generator: Standalone Single-Page Web Parameter Explorer
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
      --bg: #0d1117;
      --card-bg: #161b22;
      --border: #30363d;
      --text: #c9d1d9;
      --text-muted: #8b949e;
      --accent: #00f0ff;
      --green: #10b981;
      --red: #ef4444;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      display: flex;
      height: 100vh;
      overflow: hidden;
    }}
    /* Sidebar */
    .sidebar {{
      width: 300px;
      background: var(--card-bg);
      border-right: 1px solid var(--border);
      display: flex;
      flex-direction: column;
    }}
    .sidebar-header {{
      padding: 16px;
      font-weight: bold;
      font-size: 13px;
      letter-spacing: 1px;
      color: var(--text-muted);
      border-bottom: 1px solid var(--border);
    }}
    .section-list {{
      flex: 1;
      overflow-y: auto;
    }}
    .section-item {{
      padding: 12px 16px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid #21262d;
      transition: background 0.15s;
    }}
    .section-item:hover {{ background: rgba(0,240,255,0.05); }}
    .section-item.active {{
      background: rgba(0,240,255,0.12);
      border-left: 3px solid var(--accent);
      color: #fff;
    }}
    .badge {{
      font-family: monospace;
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 11px;
      background: #21262d;
      color: var(--accent);
    }}
    /* Main Area */
    .main {{
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }}
    .topbar {{
      padding: 14px 20px;
      background: var(--card-bg);
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}
    .search-input {{
      padding: 8px 14px;
      width: 320px;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      color: #fff;
      font-size: 14px;
    }}
    .search-input:focus {{ outline: none; border-color: var(--accent); }}
    .chips-bar {{
      padding: 10px 20px;
      background: var(--bg);
      border-bottom: 1px solid var(--border);
      display: flex;
      gap: 8px;
      overflow-x: auto;
      white-space: nowrap;
    }}
    .chip {{
      padding: 6px 12px;
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 16px;
      font-size: 12px;
      cursor: pointer;
      color: var(--text);
    }}
    .chip.active {{
      background: var(--accent);
      color: #000;
      font-weight: bold;
      border-color: var(--accent);
    }}
    .params-container {{
      flex: 1;
      overflow-y: auto;
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}
    .param-card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 14px 18px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}
    .code-badge {{
      font-family: monospace;
      font-weight: bold;
      font-size: 15px;
      color: var(--accent);
      width: 80px;
    }}
    .param-info {{ flex: 1; padding: 0 16px; }}
    .param-name {{ font-weight: 600; font-size: 15px; color: #fff; margin-bottom: 4px; }}
    .param-meta {{ font-size: 12px; color: var(--text-muted); font-family: monospace; }}
    .val-box {{
      font-family: monospace;
      font-size: 15px;
      font-weight: bold;
      padding: 6px 14px;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      margin-right: 12px;
      min-width: 90px;
      text-align: center;
    }}
    .val-box.has-val {{ color: var(--green); border-color: var(--green); }}
    .btn {{
      padding: 8px 16px;
      font-weight: bold;
      font-size: 13px;
      border-radius: 6px;
      cursor: pointer;
      border: none;
      margin-left: 6px;
    }}
    .btn-read {{ background: #1f6feb; color: #fff; }}
    .btn-edit {{ background: var(--accent); color: #000; }}
    /* Modal */
    .modal-overlay {{
      display: none;
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0,0,0,0.7);
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
      box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    }}
  </style>
</head>
<body>
  <div class="sidebar">
    <div class="sidebar-header">SECTIONS (OUTER LAYER)</div>
    <div class="section-list" id="sectionList"></div>
  </div>
  <div class="main">
    <div class="topbar">
      <div>
        <h2 id="sectionTitle" style="font-size: 18px; color: #fff;">Parameters</h2>
        <div id="sectionSub" style="font-size: 12px; color: var(--text-muted);">Select section</div>
      </div>
      <input type="text" id="searchInput" class="search-input" placeholder="Search code, name, 0xADDR...">
    </div>
    <div class="chips-bar" id="subgroupChips"></div>
    <div class="params-container" id="paramsList"></div>
  </div>

  <!-- Edit Modal -->
  <div class="modal-overlay" id="editModal">
    <div class="modal">
      <h3 id="modalTitle" style="color: var(--accent); margin-bottom: 8px;">Edit Parameter</h3>
      <div id="modalDesc" style="color: var(--text-muted); font-size: 13px; margin-bottom: 16px;"></div>
      <label style="display:block; font-size: 12px; color: var(--text-muted); margin-bottom: 6px;">New Value (Decimal or 0xHEX):</label>
      <input type="text" id="modalInput" style="width: 100%; padding: 10px; background: var(--bg); border: 1px solid var(--border); border-radius: 6px; color: #fff; font-family: monospace; font-size: 16px; margin-bottom: 16px;">
      <div style="display: flex; justify-content: flex-end; gap: 8px;">
        <button class="btn" style="background:#30363d; color:#fff;" onclick="closeModal()">Cancel</button>
        <button class="btn btn-edit" onclick="submitEdit()">Write to VFD</button>
      </div>
    </div>
  </div>

  <script>
    const SECTIONS = {json_data};
    let activeSecIdx = 0;
    let activeSubId = 'ALL';
    let currentEditParam = null;
    const liveValues = {{}};

    function init() {{
      const secList = document.getElementById('sectionList');
      SECTIONS.forEach((sec, idx) => {{
        const total = sec.subgroups.reduce((s, g) => s + g.params.length, 0);
        const item = document.createElement('div');
        item.className = 'section-item' + (idx === 0 ? ' active' : '');
        item.innerHTML = `<span><strong>${{sec.id}}</strong> ${{sec.name}}</span><span class="badge">${{total}}</span>`;
        item.onclick = () => selectSection(idx);
        secList.appendChild(item);
      }});
      selectSection(0);
      document.getElementById('searchInput').oninput = renderParams;
    }}

    function selectSection(idx) {{
      activeSecIdx = idx;
      activeSubId = 'ALL';
      document.querySelectorAll('.section-item').forEach((el, i) => {{
        el.className = 'section-item' + (i === idx ? ' active' : '');
      }});
      const sec = SECTIONS[idx];
      document.getElementById('sectionTitle').innerText = `${{sec.id}}: ${{sec.name}}`;
      renderChips();
      renderParams();
    }}

    function renderChips() {{
      const bar = document.getElementById('subgroupChips');
      bar.innerHTML = '';
      const sec = SECTIONS[activeSecIdx];
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
      const sec = SECTIONS[activeSecIdx];
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

      document.getElementById('sectionSub').innerText = `${{list.length}} Parameters Visible`;

      list.forEach(p => {{
        const card = document.createElement('div');
        card.className = 'param-card';
        const val = liveValues[p.address_hex] !== undefined ? liveValues[p.address_hex] : '--';
        const valClass = liveValues[p.address_hex] !== undefined ? 'val-box has-val' : 'val-box';

        card.innerHTML = `
          <div class="code-badge">${{p.code}}</div>
          <div class="param-info">
            <div class="param-name">${{p.name}}</div>
            <div class="param-meta">Address: ${{p.address_hex}} (${{p.address_dec}}) • Page ${{p.page}}</div>
          </div>
          <div class="${{valClass}}" id="val_${{p.address_hex}}">${{val}}</div>
          <div>
            <button class="btn btn-read" onclick="readParam('${{p.address_hex}}', '${{p.code}}')">READ</button>
            <button class="btn btn-edit" onclick="openEdit('${{p.address_hex}}', '${{p.code}}', '${{p.name}}')">EDIT</button>
          </div>
        `;
        container.appendChild(card);
      }});
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
# Main Code Generator Entry Point
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

    # 2. Frontend Flutter Screen
    dart_screen_path = os.path.join(args.frontend_dir, "param_explorer_screen.dart")
    generate_flutter_screen_file(dart_screen_path)

    # 3. ESP-IDF C Parameter Database
    generate_esp_c_files(sections, flat_params, args.esp_dir)

    # 4. ESP-IDF REST API Handlers
    generate_esp_handlers(args.esp_dir)

    # 5. Standalone Web Parameter Explorer
    generate_web_explorer(sections, flat_params, args.web_out)

    print("==================================================================")
    print("All frontend and ESP code successfully generated with correct addresses!")
    print("==================================================================")


if __name__ == "__main__":
    main()
