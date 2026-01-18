# Vivado Log Patterns

Analysis of `vivado.log` to inform Sawmill filter development.

## Log Summary

| Metric | Value |
|--------|-------|
| Total Lines | 3,021 |
| INFO messages | 546 |
| WARNING messages | 325 |
| CRITICAL WARNING | 19 |
| ERROR messages | 0 |

## Message Format

Standard Vivado message format:
```
TYPE: [Category ID-Number] message text [optional file:line reference]
```

Examples:
```
INFO: [Synth 8-6157] synthesizing module 'pcie_s7' [/path/to/file.v:53]
WARNING: [Vivado 12-3523] Attempt to change 'Component_Name' from 'pcie_s7' to 'pcie' is not allowed
CRITICAL WARNING: [Vivado 12-5447] synth_ip is not supported in project mode
```

## Severity Levels

| Severity | Pattern | Description |
|----------|---------|-------------|
| INFO | `^INFO:` | Informational messages |
| WARNING | `^WARNING:` | Potential issues, may be ignorable |
| CRITICAL WARNING | `^CRITICAL WARNING:` | Significant issues requiring attention |
| ERROR | `^ERROR:` | Build failures |

## Message Categories (by ID prefix)

| Category | ID Pattern | Description |
|----------|------------|-------------|
| Synthesis | `[Synth 8-*]` | RTL synthesis messages |
| Vivado | `[Vivado 12-*]` | General Vivado tool messages |
| Timing | `[Timing 38-*]` | Timing analysis |
| Common | `[Common 17-*]` | Common/general messages |
| IP Flow | `[IP_Flow 19-*]` | IP core management |
| Constraints | `[Constraints 18-*]` | XDC constraint issues |
| DRC | `[DRC 23-*]` | Design Rule Checks |
| Route | `[Route 35-*]` | Routing messages |
| Opt | `[Opt 31-*]` | Optimization messages |
| Physopt | `[Physopt 32-*]` | Physical optimization |
| Power | `[Power 33-*]` | Power analysis |
| Device | `[Device 21-*]` | Device/part messages |
| Project | `[Project 1-*]` | Project management |

## Most Common Message IDs

From this log file:
```
109 [Synth 8-6014]   - Binding/inference messages
108 [Synth 8-7129]   - Port connection messages
100 [Synth 8-5396]   - Synthesis optimization
 53 [Synth 8-6157]   - "synthesizing module"
 53 [Synth 8-6155]   - "done synthesizing module"
 40 [Synth 8-7071]   - Declaration messages
 31 [Synth 8-802]    - FSM encoding
 30 [Synth 8-3354]   - RAM inference
```

## Multi-Line Message Patterns

### 1. Header Banner (Session Start)
```
#-----------------------------------------------------------
# Vivado v2025.2 (64-bit)
# SW Build 6299465 on Fri Nov 14 12:34:56 MST 2025
# ...
#-----------------------------------------------------------
```
**Pattern:** Lines starting with `#` at start of file

### 2. Phase Separators
```
---------------------------------------------------------------------------------
Starting RTL Elaboration : Time (s): cpu = 00:00:07 ; elapsed = 00:00:07 ...
---------------------------------------------------------------------------------
```
**Pattern:** Line of dashes, followed by phase info, followed by dashes

### 3. Timing Summary Tables
```
------------------------------------------------------------------------------------------------
| Design Timing Summary
| ---------------------
------------------------------------------------------------------------------------------------

    WNS(ns)      TNS(ns)  TNS Failing Endpoints  TNS Total Endpoints      WHS(ns)      ...
    -------      -------  ---------------------  -------------------      -------      ...
      0.082        0.000                      0                31102        0.032      ...
```
**Pattern:** Box-drawn tables with `|` borders and `-` separators

### 4. Check Reports
```
1. checking no_clock (0)
------------------------
 There are 0 register/latch pins with no clock driven by root clock pin.

2. checking constant_clock (0)
------------------------------
 There are 0 register/latch pins with constant_clock.
```
**Pattern:** Numbered sections with underline, followed by indented details

### 5. Clock Summary Tables
```
Clock                              Waveform(ns)         Period(ns)      Frequency(MHz)
-----                              ------------         ----------      --------------
clk100                             {0.000 5.000}        10.000          100.000
```
**Pattern:** Column headers with underline dashes, followed by data rows

## Suggested Filter Categories for Vivado Plugin

### Errors & Critical
- `^ERROR:` - All errors
- `^CRITICAL WARNING:` - Critical warnings
- `\[.*\] .*timing.*fail` - Timing failures

### Synthesis
- `^WARNING: \[Synth` - Synthesis warnings
- `^INFO: \[Synth 8-6157\]` - Module synthesis start
- `^INFO: \[Synth 8-6155\]` - Module synthesis complete
- `\[Synth 8-3354\]` - RAM inference (often important)
- `\[Synth 8-802\]` - FSM encoding

### Timing
- `^WARNING: \[Timing` - Timing warnings
- `WNS\(ns\).*-\d` - Negative slack (failing timing)
- `TNS Failing Endpoints\s+[1-9]` - Failing endpoint count > 0
- `All user specified timing constraints are met` - Timing passed

### Constraints
- `^CRITICAL WARNING: \[Constraints` - Constraint issues
- `^WARNING: \[Vivado 12-4739\]` - Invalid constraint objects

### IP/Core Generation
- `\[IP_Flow` - IP core messages
- `Generating .* target for IP` - IP generation

### Resource Usage
- `\[Synth 8-3354\]` - RAM inference
- `\[Synth 8-7129\]` - Port connections
- `Bitstream compression saved` - Compression stats

## Message Boundary Rules for Multi-line Grouping

For Vivado logs, continuation lines typically:
1. Are indented with spaces
2. Don't start with a severity keyword (INFO/WARNING/etc.)
3. Are part of table structures (contain `|` characters)
4. Are part of separator lines (all `-` or `=` characters)

**Proposed boundary rule:**
```json
{
  "start_pattern": "^(INFO|WARNING|CRITICAL WARNING|ERROR):",
  "continuation_pattern": "^(\\s+|\\||[-=]+$)",
  "max_lines": 20
}
```

## Files Referenced in Log

The log contains references to:
- Verilog source files (`.v`)
- XDC constraint files (`.xdc`)
- IP core files (`.xci`)
- Report files (`.rpt`)

These could be made clickable in the TUI for quick navigation.
