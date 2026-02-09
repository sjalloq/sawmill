"""CI reporting and waiver application for sawmill CLI.

Provides check-mode logic, waiver application, and JSON report generation.
"""

from __future__ import annotations

from datetime import datetime, timezone

import rich_click as click

from sawmill.core.severity import get_severity_level_map, get_severity_levels
from sawmill.models.waiver import Waiver


def get_fail_on_level(fail_on: str | None, plugin) -> int:
    """Get the numeric level for --fail-on severity.

    Args:
        fail_on: Severity name from --fail-on option, or None for default.
        plugin: Plugin instance to get severity levels from.

    Returns:
        Numeric level threshold. Default: second-lowest severity level
        from the plugin (i.e., everything above the lowest info-like level).

    Raises:
        click.BadParameter: If fail_on is not a valid severity for the plugin.
    """
    level_map = get_severity_level_map(plugin)

    if fail_on is None:
        # Default: fail on everything above the lowest severity level
        severity_levels = get_severity_levels(plugin)
        sorted_levels = sorted(severity_levels, key=lambda s: s.level)
        if len(sorted_levels) >= 2:
            return int(sorted_levels[1].level)
        return int(sorted_levels[0].level) if sorted_levels else 0

    fail_on_lower = fail_on.lower()
    if fail_on_lower not in level_map:
        valid = sorted(level_map.keys(), key=lambda x: -level_map[x])
        raise click.BadParameter(
            f"Unknown severity '{fail_on}'. Valid options for this plugin: {', '.join(valid)}",
            param_hint="'--fail-on'",
        )
    return level_map[fail_on_lower]


def has_check_failures(messages: list, plugin, min_level: int = 1) -> bool:
    """Check if messages contain severities at or above the threshold.

    Used by --check mode to determine exit code.

    Args:
        messages: List of unwaived messages to check.
        plugin: Plugin instance to get severity level map from.
        min_level: Minimum severity level that causes failure.

    Returns:
        True if there are messages at or above the threshold.
    """
    level_map = get_severity_level_map(plugin)

    for msg in messages:
        if msg.severity:
            msg_level = level_map.get(msg.severity.lower(), 0)
            if msg_level >= min_level:
                return True
    return False


def apply_waivers(
    messages: list,
    matcher,
) -> tuple[list, list, list[Waiver]]:
    """Separate messages into waived and unwaived lists.

    Args:
        messages: All messages to process.
        matcher: WaiverMatcher to use for checking waivers.

    Returns:
        A tuple of (unwaived_messages, waived_messages, used_waivers).
    """
    unwaived: list = []
    waived: list = []
    used_waivers: list[Waiver] = []

    for msg in messages:
        waiver = matcher.is_waived(msg)
        if waiver:
            waived.append((msg, waiver))
            # Track used waivers (by identity, not by hash)
            if waiver not in used_waivers:
                used_waivers.append(waiver)
        else:
            unwaived.append(msg)

    return unwaived, waived, used_waivers


def generate_check_report(
    messages: list,
    waived_messages: list,
    used_waivers: list[Waiver],
    all_waivers: list[Waiver],
    plugin,
    min_level: int,
    log_file: str,
    plugin_name: str,
    suppressed_messages: list | None = None,
) -> dict:
    """Generate a check summary report as a dictionary.

    Args:
        messages: List of unwaived messages (from CI set, not display set).
        waived_messages: List of (message, waiver) tuples for waived messages.
        used_waivers: List of waivers that matched messages.
        all_waivers: All waivers that were loaded.
        plugin: Plugin instance to get severity levels from.
        min_level: Minimum severity level that causes failure.
        log_file: Path to the log file being analyzed.
        plugin_name: Name of the plugin used.
        suppressed_messages: Messages hidden from display by suppress filters.

    Returns:
        Dictionary containing the check report.
    """
    if suppressed_messages is None:
        suppressed_messages = []
    # Build severity counts dynamically from plugin
    severity_levels = get_severity_levels(plugin)
    counts: dict[str, int] = {level.id: 0 for level in severity_levels}
    counts["other"] = 0

    level_map = {level.id: level.level for level in severity_levels}

    for msg in messages:
        if msg.severity:
            sev = msg.severity.lower()
            if sev in counts:
                counts[sev] += 1
            else:
                counts["other"] += 1
        else:
            counts["other"] += 1

    # Count waived messages by severity
    waived_counts: dict[str, int] = {level.id: 0 for level in severity_levels}
    waived_counts["other"] = 0

    for msg, _waiver in waived_messages:
        if msg.severity:
            sev = msg.severity.lower()
            if sev in waived_counts:
                waived_counts[sev] += 1
            else:
                waived_counts["other"] += 1
        else:
            waived_counts["other"] += 1

    # Calculate exit code based on unwaived messages and threshold
    exit_code = 0
    for msg in messages:
        if msg.severity:
            msg_level = level_map.get(msg.severity.lower(), 0)
            if msg_level >= min_level:
                exit_code = 1
                break

    # Build issues list (unwaived messages with CI-relevant severities)
    issues = []
    for msg in messages:
        issues.append(
            {
                "message_id": msg.message_id,
                "severity": msg.severity,
                "content": msg.content,
                "line": msg.start_line,
                "raw_text": msg.raw_text,
            }
        )

    # Build waived list
    waived_list = []
    for msg, waiver in waived_messages:
        waived_list.append(
            {
                "message_id": msg.message_id,
                "severity": msg.severity,
                "content": msg.content,
                "line": msg.start_line,
                "waiver_message_id": waiver.message_id,
                "waiver_reason": waiver.reason,
            }
        )

    # Find unused waivers
    unused_waivers = []
    for waiver in all_waivers:
        if waiver not in used_waivers:
            unused_waivers.append(
                {
                    "message_id": waiver.message_id,
                    "reason": waiver.reason,
                }
            )

    # Build suppressed list
    suppressed_list = []
    for msg in suppressed_messages:
        suppressed_list.append(
            {
                "message_id": msg.message_id,
                "severity": msg.severity,
                "content": msg.content,
                "line": msg.start_line,
                "raw_text": msg.raw_text,
            }
        )

    # Build the report with dynamic severity counts
    # total = all scope-filtered messages (pre-waiver, pre-suppress from CI perspective)
    # Note: suppressed_messages are a subset of (messages + waived_messages) that were
    # removed from display only, so they're already counted in the CI totals.
    summary = {
        "total": len(messages) + len(waived_messages),
        "suppressed": len(suppressed_messages),
        "waived": len(waived_messages),
        "by_severity": counts,
        "waived_by_severity": waived_counts,
    }

    report = {
        "metadata": {
            "log_file": log_file,
            "plugin": plugin_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fail_on_level": min_level,
        },
        "exit_code": exit_code,
        "summary": summary,
        "issues": issues,
        "waived": waived_list,
        "suppressed": suppressed_list,
        "unused_waivers": unused_waivers,
    }

    return report
