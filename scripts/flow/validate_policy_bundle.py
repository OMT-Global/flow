#!/usr/bin/env python3
"""Validate the Public Repository Standard policy bundle deterministically."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUNDLE = ROOT / "policies" / "public-repository-standard-v1.json"
DEFAULT_SCHEMA = ROOT / "schemas" / "public-repository-standard-v1.schema.json"
REQUIRED_TOP_LEVEL = (
    "$schema",
    "standard",
    "version",
    "publisher",
    "repositoryClasses",
    "maturityLevels",
    "materialActions",
    "notifications",
    "humanHardStops",
    "adrTriggers",
    "quality",
    "security",
    "provenance",
    "release",
    "exceptions",
    "conformance",
    "compatibility",
    "rules",
)


def resolve_ref(root_schema: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ValueError(f"unsupported schema reference: {ref}")
    node: Any = root_schema
    for part in ref[2:].split("/"):
        node = node[part.replace("~1", "/").replace("~0", "~")]
    if not isinstance(node, dict):
        raise ValueError(f"schema reference is not an object: {ref}")
    return node


def validate_schema_value(value: Any, schema: dict[str, Any], root: dict[str, Any], path: str) -> list[str]:
    if "$ref" in schema:
        return validate_schema_value(value, resolve_ref(root, schema["$ref"]), root, path)

    errors: list[str] = []
    expected = schema.get("type")
    type_matches = {
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "string": lambda item: isinstance(item, str),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "boolean": lambda item: isinstance(item, bool),
    }
    if expected in type_matches and not type_matches[expected](value):
        return [f"{path}: expected {expected}"]
    if "const" in schema and value != schema["const"]:
        expected = schema["const"]
        if isinstance(expected, (dict, list)):
            errors.append(f"{path}: expected constant policy value")
        else:
            errors.append(f"{path}: expected constant {expected!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value is not in the allowed set")

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}.{key}: required property is missing")
        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        for key, item in value.items():
            child_path = f"{path}.{key}"
            if key in properties:
                errors.extend(validate_schema_value(item, properties[key], root, child_path))
            elif additional is False:
                errors.append(f"{child_path}: additional property is not allowed")
            elif isinstance(additional, dict):
                errors.extend(validate_schema_value(item, additional, root, child_path))
        if len(value) < schema.get("minProperties", 0):
            errors.append(f"{path}: has fewer than {schema['minProperties']} properties")

    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: has fewer than {schema['minItems']} items")
        if schema.get("uniqueItems"):
            encoded = [json.dumps(item, sort_keys=True) for item in value]
            if len(encoded) != len(set(encoded)):
                errors.append(f"{path}: items must be unique")
        if "items" in schema:
            for index, item in enumerate(value):
                errors.extend(validate_schema_value(item, schema["items"], root, f"{path}[{index}]"))

    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path}: string is shorter than {schema['minLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: string does not match required pattern")
    if isinstance(value, int) and not isinstance(value, bool) and value < schema.get("minimum", value):
        errors.append(f"{path}: value is below minimum {schema['minimum']}")
    return errors


def validate_bundle(bundle: Any, schema: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(schema, dict) or schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        errors.append("$schema: expected a JSON Schema Draft 2020-12 document")
    if not isinstance(bundle, dict):
        return errors + ["$: expected an object"]

    errors.extend(validate_schema_value(bundle, schema, schema, "$"))

    for key in REQUIRED_TOP_LEVEL:
        if key not in bundle:
            errors.append(f"$.{key}: required property is missing")

    if errors:
        return sorted(errors)

    if bundle["standard"] != "public-repository-standard":
        errors.append("$.standard: expected 'public-repository-standard'")
    if not isinstance(bundle["version"], str) or not re.fullmatch(r"1\.[0-9]+\.[0-9]+", bundle["version"]):
        errors.append("$.version: expected a v1 semantic version")

    classes = bundle["repositoryClasses"]
    if not isinstance(classes, dict):
        errors.append("$.repositoryClasses: expected an object")
        classes = {}

    rules = bundle["rules"]
    rule_ids: set[str] = set()
    if not isinstance(rules, list):
        errors.append("$.rules: expected an array")
        rules = []
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            errors.append(f"$.rules[{index}]: expected an object")
            continue
        rule_id = rule.get("id")
        if not isinstance(rule_id, str):
            errors.append(f"$.rules[{index}].id: expected a string")
        elif rule_id in rule_ids:
            errors.append(f"$.rules[{index}].id: duplicate rule id '{rule_id}'")
        else:
            rule_ids.add(rule_id)

    blocking = bundle.get("conformance", {}).get("blockingRuleIds", [])
    if isinstance(blocking, list):
        for index, rule_id in enumerate(blocking):
            if rule_id not in rule_ids:
                errors.append(
                    f"$.conformance.blockingRuleIds[{index}]: unknown rule id '{rule_id}'"
                )
        for rule in rules:
            if isinstance(rule, dict) and rule.get("severity") == "blocking":
                rule_id = rule.get("id")
                if isinstance(rule_id, str) and rule_id not in blocking:
                    errors.append(
                        f"$.conformance.blockingRuleIds: missing blocking rule id '{rule_id}'"
                    )

    aliases = bundle.get("compatibility", {}).get("repositoryClassAliases", {})
    if isinstance(aliases, dict):
        for alias, target in aliases.items():
            if target not in classes:
                errors.append(
                    f"$.compatibility.repositoryClassAliases.{alias}: "
                    f"unknown repository class '{target}'"
                )

    return sorted(errors)


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{path}: {error}") from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    args = parser.parse_args(argv)

    try:
        errors = validate_bundle(read_json(args.bundle), read_json(args.schema))
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(f"valid: {args.bundle}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
