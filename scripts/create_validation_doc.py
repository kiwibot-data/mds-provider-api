#!/usr/bin/env python3
"""
Create comprehensive validation requirements document from MDS 2.0 VALIDATOR.json
This script extracts all validation schemas embedded in Postman collection test scripts.
"""

import argparse
import json
import os
import re
from typing import Dict, List, Any, Set

# Default paths (relative to project root)
DEFAULT_COLLECTION_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'MDS 2.0 VALIDATOR.json'
)
DEFAULT_OUTPUT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'MDS_VALIDATION_REQUIREMENTS.md'
)

def clean_json_string(json_str: str) -> str:
    """Clean JSON string from JavaScript artifacts."""
    # Remove JavaScript comments
    json_str = re.sub(r'//[^\n]*', '', json_str)
    # Remove trailing commas before closing braces/brackets
    json_str = re.sub(r',\s*([}\]])', r'\1', json_str)
    # Remove control characters except for newline, tab, carriage return
    json_str = ''.join(char for char in json_str if ord(char) >= 32 or char in '\n\r\t')
    return json_str

def extract_schema_from_exec(exec_lines: List[str]) -> Dict:
    """Extract JSON schema from exec lines."""
    # The exec_lines are individual JavaScript strings that when concatenated form the schema
    # We need to join them properly - each line is a separate string in the array
    full_script = '\n'.join(exec_lines)

    # Find schema definition - may or may not have semicolon
    schema_match = re.search(r'var\s+schema\s*=\s*({[\s\S]*?})\s*;?\s*pm\.test', full_script)
    if not schema_match:
        return None

    schema_str = schema_match.group(1)

    # The JSON in exec_lines has embedded actual newlines which are invalid in JSON strings
    # We need to replace literal newlines within string values with escaped newlines
    # But keep newlines between JSON properties

    # First, clean JavaScript artifacts
    schema_str = clean_json_string(schema_str)

    # Replace unescaped newlines in string values
    # This is a heuristic: if we see \n not preceded by \, and we're inside quotes, escape it
    result = []
    in_string = False
    i = 0
    while i < len(schema_str):
        char = schema_str[i]

        # Track if we're in a string
        if char == '"' and (i == 0 or schema_str[i-1] != '\\'):
            in_string = not in_string
            result.append(char)
        elif char == '\n' and in_string:
            # Newline inside a string - escape it
            result.append('\\n')
        else:
            result.append(char)

        i += 1

    schema_str = ''.join(result)

    try:
        return json.loads(schema_str)
    except json.JSONDecodeError as e:
        print(f"JSON decode error for schema: {e}")
        # Save for debugging
        with open('/tmp/failed_schema.json', 'w') as f:
            f.write(schema_str)
        print("Saved failed schema to /tmp/failed_schema.json")
        return None

def format_constraints(definition: Dict) -> List[str]:
    """Format validation constraints for a field."""
    constraints = []

    if 'type' in definition:
        constraints.append(f"**Type:** `{definition['type']}`")

    if 'format' in definition:
        constraints.append(f"**Format:** `{definition['format']}`")

    if 'pattern' in definition:
        pattern = definition['pattern'].replace('\\', '\\\\')
        constraints.append(f"**Pattern:** `{pattern}`")

    if 'minimum' in definition:
        constraints.append(f"**Minimum:** `{definition['minimum']}`")

    if 'maximum' in definition:
        constraints.append(f"**Maximum:** `{definition['maximum']}`")

    if 'minLength' in definition:
        constraints.append(f"**Min Length:** `{definition['minLength']}`")

    if 'maxLength' in definition:
        constraints.append(f"**Max Length:** `{definition['maxLength']}`")

    if 'minItems' in definition:
        constraints.append(f"**Min Items:** `{definition['minItems']}`")

    if 'maxItems' in definition:
        constraints.append(f"**Max Items:** `{definition['maxItems']}`")

    if 'uniqueItems' in definition:
        constraints.append(f"**Unique Items:** `{definition['uniqueItems']}`")

    if 'multipleOf' in definition:
        constraints.append(f"**Multiple Of:** `{definition['multipleOf']}`")

    if 'const' in definition:
        constraints.append(f"**Constant Value:** `{definition['const']}`")

    return constraints

def document_enum(enum_values: List, max_inline: int = 10) -> List[str]:
    """Document enum values."""
    lines = []
    if len(enum_values) <= max_inline:
        lines.append(f"**Allowed Values:** {', '.join(f'`{v}`' for v in enum_values)}")
    else:
        lines.append(f"**Allowed Values:** ({len(enum_values)} total)")
        for value in enum_values:
            lines.append(f"  - `{value}`")
    return lines

def document_definition(name: str, definition: Dict, definitions_map: Dict, documented: Set, level: int = 4) -> List[str]:
    """Recursively document a schema definition."""
    lines = []
    heading = '#' * level

    if name in documented:
        return lines
    documented.add(name)

    lines.append(f"{heading} `{name}`")
    lines.append("")

    if 'title' in definition:
        lines.append(f"**Title:** {definition['title']}")
        lines.append("")

    if 'description' in definition:
        lines.append(f"**Description:** {definition['description']}")
        lines.append("")

    # Constraints
    constraints = format_constraints(definition)
    if constraints:
        for constraint in constraints:
            lines.append(constraint)
        lines.append("")

    # Enum
    if 'enum' in definition:
        lines.extend(document_enum(definition['enum']))
        lines.append("")

    # Required fields
    if 'required' in definition:
        lines.append(f"**Required Fields:** {', '.join(f'`{f}`' for f in definition['required'])}")
        lines.append("")

    # Properties
    if 'properties' in definition:
        lines.append(f"**Properties:**")
        lines.append("")
        for prop_name, prop_def in definition['properties'].items():
            lines.append(f"- **`{prop_name}`**")

            if 'description' in prop_def:
                lines.append(f"  - Description: {prop_def['description']}")

            if '$ref' in prop_def:
                ref_name = prop_def['$ref'].split('/')[-1]
                lines.append(f"  - Type: Reference to `{ref_name}`")
            else:
                prop_constraints = format_constraints(prop_def)
                for pc in prop_constraints:
                    lines.append(f"  - {pc}")

            if 'enum' in prop_def:
                enum_lines = document_enum(prop_def['enum'], max_inline=5)
                for el in enum_lines:
                    lines.append(f"  - {el}")

            # Array item details
            if prop_def.get('type') == 'array' and 'items' in prop_def:
                if '$ref' in prop_def['items']:
                    ref_name = prop_def['items']['$ref'].split('/')[-1]
                    lines.append(f"  - Array Items: Reference to `{ref_name}`")
                else:
                    item_constraints = format_constraints(prop_def['items'])
                    for ic in item_constraints:
                        lines.append(f"  - Array Items: {ic}")

            lines.append("")

    # Array items (for array types)
    if 'items' in definition and 'properties' not in definition:
        if '$ref' in definition['items']:
            ref_name = definition['items']['$ref'].split('/')[-1]
            lines.append(f"**Array Items:** Reference to `{ref_name}`")
        else:
            lines.append(f"**Array Items:**")
            item_constraints = format_constraints(definition['items'])
            for ic in item_constraints:
                lines.append(f"  - {ic}")
        lines.append("")

    # Conditional validation
    if 'oneOf' in definition:
        lines.append(f"**One Of** ({len(definition['oneOf'])} mutually exclusive options):")
        lines.append("")
        for i, option in enumerate(definition['oneOf']):
            opt_title = option.get('title', f'Option {i+1}')
            lines.append(f"  {i+1}. **{opt_title}**")
            if 'properties' in option:
                for prop, val in option['properties'].items():
                    if 'const' in val:
                        lines.append(f"     - `{prop}` must be `{val['const']}`")
                    if 'items' in val and 'enum' in val['items']:
                        enum_preview = ', '.join(f"`{e}`" for e in val['items']['enum'][:10])
                        more_indicator = '...' if len(val['items']['enum']) > 10 else ''
                        lines.append(f"     - `{prop}` items must be one of: {enum_preview}{more_indicator}")
        lines.append("")

    if 'anyOf' in definition:
        lines.append(f"**Any Of** (at least one must match, {len(definition['anyOf'])} options):")
        lines.append("")
        for i, option in enumerate(definition['anyOf']):
            opt_title = option.get('title', f'Option {i+1}')
            lines.append(f"  {i+1}. **{opt_title}**")
            if 'required' in option:
                required_fields = ', '.join(f"`{r}`" for r in option['required'])
                lines.append(f"     - Requires: {required_fields}")
        lines.append("")

    if 'allOf' in definition:
        lines.append(f"**All Of** (all must match, {len(definition['allOf'])} schemas):")
        lines.append("")

    if 'if' in definition:
        lines.append(f"**Conditional Validation:** if/then logic present")
        lines.append(f"  - If the event_types contains certain values, additional fields become required")
        lines.append("")

    return lines

def main():
    parser = argparse.ArgumentParser(
        description="Create validation requirements document from MDS 2.0 VALIDATOR.json"
    )
    parser.add_argument(
        '--collection', '-c',
        default=os.environ.get('MDS_COLLECTION_FILE', DEFAULT_COLLECTION_FILE),
        help='Path to MDS 2.0 VALIDATOR.json Postman collection (default: MDS 2.0 VALIDATOR.json in project root, or MDS_COLLECTION_FILE env var)'
    )
    parser.add_argument(
        '--output', '-o',
        default=os.environ.get('MDS_VALIDATION_OUTPUT', DEFAULT_OUTPUT_PATH),
        help='Output file path (default: MDS_VALIDATION_REQUIREMENTS.md in project root, or MDS_VALIDATION_OUTPUT env var)'
    )
    args = parser.parse_args()

    collection_file = args.collection
    output_path = args.output

    # Read Postman collection
    with open(collection_file, 'r') as f:
        collection = json.load(f)

    output_lines = []
    output_lines.append("# MDS 2.0 API Validation Requirements")
    output_lines.append("")
    output_lines.append("## Overview")
    output_lines.append("")
    output_lines.append("This document details ALL validation requirements for the MDS 2.0 Provider API endpoints.")
    output_lines.append("The requirements are extracted from the official MDS 2.0 validation Postman collection.")
    output_lines.append("")
    output_lines.append("### Important Note")
    output_lines.append("")
    output_lines.append("**IGNORE** validation failures for the following attribute fields as they were not customized for delivery robots:")
    output_lines.append("- `vehicle_attributes`")
    output_lines.append("- `trip_attributes`")
    output_lines.append("- `accessibility_attributes`")
    output_lines.append("- Any other `*_attributes` fields")
    output_lines.append("")
    output_lines.append("---")
    output_lines.append("")
    output_lines.append("## Table of Contents")
    output_lines.append("")

    # Build TOC
    for idx, item in enumerate(collection['item'], 1):
        output_lines.append(f"{idx}. [{item['name']}](#{item['name'].lower().replace(' ', '-')})")

    output_lines.append("")
    output_lines.append("---")
    output_lines.append("")

    # Process each test item
    for idx, item in enumerate(collection['item'], 1):
        output_lines.append(f"## {idx}. {item['name']}")
        output_lines.append("")

        # Request details
        if 'request' in item:
            req = item['request']

            output_lines.append("### Request Specification")
            output_lines.append("")
            output_lines.append(f"**HTTP Method:** `{req.get('method', 'N/A')}`")
            output_lines.append("")

            # URL
            if 'url' in req:
                url = req['url']
                if isinstance(url, dict):
                    if 'raw' in url:
                        output_lines.append(f"**URL:** `{url['raw']}`")
                        output_lines.append("")

                    if 'path' in url:
                        path = '/' + '/'.join(url['path'])
                        output_lines.append(f"**Endpoint Path:** `{path}`")
                        output_lines.append("")

                    # Query parameters
                    if 'query' in url and url['query']:
                        output_lines.append("#### Query Parameters")
                        output_lines.append("")
                        output_lines.append("| Parameter | Example Value | Required |")
                        output_lines.append("|-----------|---------------|----------|")
                        for param in url['query']:
                            key = param.get('key', '')
                            value = param.get('value', 'N/A')
                            disabled = param.get('disabled', False)
                            required = 'No' if disabled else 'Yes'
                            output_lines.append(f"| `{key}` | `{value}` | {required} |")
                        output_lines.append("")

            # Headers
            if 'header' in req:
                output_lines.append("#### Required Headers")
                output_lines.append("")
                output_lines.append("| Header | Value |")
                output_lines.append("|--------|-------|")
                for header in req['header']:
                    key = header.get('key', '')
                    value = header.get('value', '')
                    output_lines.append(f"| `{key}` | `{value}` |")
                output_lines.append("")

        # Extract schema
        schema = None
        if 'event' in item:
            for event in item['event']:
                if event.get('listen') == 'test' and 'script' in event:
                    schema = extract_schema_from_exec(event['script'].get('exec', []))
                    if schema:
                        break

        if schema:
            output_lines.append("### Response Schema")
            output_lines.append("")

            # Top level
            output_lines.append(f"**Schema Type:** `{schema.get('type', 'object')}`")
            output_lines.append("")

            if schema.get('additionalProperties') is False:
                output_lines.append("**Additional Properties:** Not allowed (response must only contain specified fields)")
                output_lines.append("")

            # Required top-level fields
            if 'required' in schema:
                output_lines.append("#### Required Top-Level Fields")
                output_lines.append("")
                for field in schema['required']:
                    output_lines.append(f"- `{field}`")
                output_lines.append("")

            # Top-level properties
            if 'properties' in schema:
                output_lines.append("#### Top-Level Properties")
                output_lines.append("")
                for prop_name, prop_def in schema['properties'].items():
                    output_lines.append(f"##### `{prop_name}`")
                    output_lines.append("")

                    if 'description' in prop_def:
                        output_lines.append(f"{prop_def['description']}")
                        output_lines.append("")

                    if '$ref' in prop_def:
                        ref_name = prop_def['$ref'].split('/')[-1]
                        output_lines.append(f"**Type:** Reference to definition `{ref_name}` (see below)")
                    else:
                        constraints = format_constraints(prop_def)
                        for c in constraints:
                            output_lines.append(c)

                    output_lines.append("")

            # Definitions
            if 'definitions' in schema:
                output_lines.append("### Schema Definitions")
                output_lines.append("")
                output_lines.append("The following type definitions specify the structure and validation rules for complex types:")
                output_lines.append("")

                # Categorize definitions
                main_models = []
                data_types = []
                mode_specific = []

                for def_name in schema['definitions'].keys():
                    if def_name in ['Event', 'Telemetry', 'Trip', 'Vehicle', 'Vehicle-status']:
                        main_models.append(def_name)
                    elif def_name.startswith('Event_') or 'mode' in schema['definitions'][def_name].get('title', '').lower():
                        mode_specific.append(def_name)
                    else:
                        data_types.append(def_name)

                # Document main models first
                if main_models:
                    output_lines.append("#### Main Data Models")
                    output_lines.append("")
                    documented = set()
                    for def_name in sorted(main_models):
                        lines = document_definition(def_name, schema['definitions'][def_name],
                                                    schema['definitions'], documented, level=5)
                        output_lines.extend(lines)

                # Mode-specific definitions
                if mode_specific:
                    output_lines.append("#### Mode-Specific Event Definitions")
                    output_lines.append("")
                    output_lines.append("These define valid state transitions for different vehicle modes:")
                    output_lines.append("")
                    documented = set()
                    for def_name in sorted(mode_specific):
                        lines = document_definition(def_name, schema['definitions'][def_name],
                                                    schema['definitions'], documented, level=5)
                        output_lines.extend(lines)

                # Data types
                if data_types:
                    output_lines.append("#### Data Type Definitions")
                    output_lines.append("")
                    documented = set()
                    for def_name in sorted(data_types):
                        lines = document_definition(def_name, schema['definitions'][def_name],
                                                    schema['definitions'], documented, level=5)
                        output_lines.extend(lines)

        else:
            output_lines.append("### Response Schema")
            output_lines.append("")
            output_lines.append("*Schema not found in test script*")
            output_lines.append("")

        output_lines.append("---")
        output_lines.append("")

    # Write output
    with open(output_path, 'w') as f:
        f.write('\n'.join(output_lines))

    print(f"\n✓ Successfully generated validation requirements document")
    print(f"✓ Output: {output_path}")
    print(f"✓ Total lines: {len(output_lines)}")
    print(f"✓ Processed {len(collection['item'])} test items")

if __name__ == '__main__':
    main()
