"""Template variable validation — backend parity with the editor's inline checks.

Mirrors ``frontend/src/utils/templateValidation.ts`` so the same rules apply
whether a template is saved through the editor or programmatically (API, import,
bulk-assign). Both sides share the engine's ``VARIABLE_PATTERN`` (resolver.py) as
the single definition of what counts as a variable, and the registry as the
single source of valid names.

Validation is **advisory**: the resolver keeps unknown variables literal by
design (to surface typos in the output), so warnings never block a save — they
are logged on write and returned by ``POST /templates/validate`` for callers.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from teamarr.templates.resolver import VARIABLE_PATTERN
from teamarr.templates.variables import SuffixRules, get_registry

_SUFFIX_RE = re.compile(r"\.(next|last)$")


@dataclass(frozen=True)
class ValidationWarning:
    """One advisory finding about a template field."""

    variable: str
    message: str
    type: str  # "invalid" | "suffix_not_allowed"


def supported_suffixes(rules: SuffixRules) -> list[str]:
    """Suffix labels a variable supports. ``"base"`` means the bare name."""
    if rules == SuffixRules.ALL:
        return ["base", ".next", ".last"]
    if rules == SuffixRules.BASE_ONLY:
        return ["base"]
    if rules == SuffixRules.BASE_NEXT_ONLY:
        return ["base", ".next"]
    if rules == SuffixRules.LAST_ONLY:
        return [".last"]
    return ["base"]


def build_valid_variable_sets() -> tuple[set[str], set[str]]:
    """Return ``(valid_names, base_names)`` from the live registry.

    ``valid_names`` holds every legal full token (base plus only the suffixes
    each variable actually supports); ``base_names`` holds the bare names. Mirror
    of the frontend ``buildValidVariableSet()``.
    """
    valid_names: set[str] = set()
    base_names: set[str] = set()
    for var in get_registry().all_variables():
        base_names.add(var.name)
        for suffix in supported_suffixes(var.suffix_rules):
            valid_names.add(var.name if suffix == "base" else f"{var.name}{suffix}")
    return valid_names, base_names


def extract_variables(template: str) -> list[str]:
    """Variable tokens the engine would resolve, lowercased (matches resolver)."""
    if not template:
        return []
    return [m.group(1).lower() for m in VARIABLE_PATTERN.finditer(template)]


def _has_suffix(name: str) -> bool:
    return bool(_SUFFIX_RE.search(name))


def validate_template(
    template: str,
    valid_names: set[str],
    base_names: set[str],
    is_event_template: bool,
) -> list[ValidationWarning]:
    """Validate one template string. Mirror of frontend ``validateTemplate()``."""
    warnings: list[ValidationWarning] = []
    for name in extract_variables(template):
        # Suffixed variables are not supported in event templates.
        if is_event_template and _has_suffix(name):
            base = _SUFFIX_RE.sub("", name)
            if base in base_names:
                warnings.append(
                    ValidationWarning(
                        variable=name,
                        message=(
                            f"Suffixed variables like {{{name}}} are not supported in "
                            f"event templates. Use {{{base}}} instead."
                        ),
                        type="suffix_not_allowed",
                    )
                )
            else:
                warnings.append(
                    ValidationWarning(
                        variable=name,
                        message=f"Unknown variable: {{{name}}}",
                        type="invalid",
                    )
                )
        elif name not in valid_names:
            base = _SUFFIX_RE.sub("", name)
            if base in base_names and _has_suffix(name):
                warnings.append(
                    ValidationWarning(
                        variable=name,
                        message=f"{{{name}}} is not a valid suffix for this variable",
                        type="invalid",
                    )
                )
            else:
                warnings.append(
                    ValidationWarning(
                        variable=name,
                        message=f"Unknown variable: {{{name}}}",
                        type="invalid",
                    )
                )
    return warnings


def validate_fields(
    fields: dict[str, str | None],
    is_event_template: bool,
) -> dict[str, list[ValidationWarning]]:
    """Validate a map of ``field_name -> template``; return only fields with warnings."""
    valid_names, base_names = build_valid_variable_sets()
    results: dict[str, list[ValidationWarning]] = {}
    for field_name, value in fields.items():
        if not value:
            continue
        found = validate_template(value, valid_names, base_names, is_event_template)
        if found:
            results[field_name] = found
    return results


def warnings_as_dicts(
    results: dict[str, list[ValidationWarning]],
) -> dict[str, list[dict]]:
    """Serialize per-field warnings for API responses."""
    return {field: [asdict(w) for w in ws] for field, ws in results.items()}
