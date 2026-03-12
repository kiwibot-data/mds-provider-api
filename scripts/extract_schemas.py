#!/usr/bin/env python3
"""
Extract complete validation schemas from MDS 2.0 VALIDATOR.json
"""

import argparse
import json
import os
import re
from typing import Dict, Any, List

# Default paths (relative to project root)
DEFAULT_VALIDATOR_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'MDS 2.0 VALIDATOR.json'
)
DEFAULT_OUTPUT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'MDS_VALIDATION_REQUIREMENTS.md'
)

def extract_schema_from_test(test_script: Dict) -> Dict:
    """Extract schema from test script."""
    if not test_script or 'exec' not in test_script:
        return None

    exec_lines = test_script['exec']
    schema_str = '\n'.join(exec_lines)

    # Find the schema object
    match = re.search(r'var schema\s*=\s*({.*?});?\s*pm\.test', schema_str, re.DOTALL)
    if match:
        schema_json = match.group(1)
        # Remove JavaScript comments
        schema_json = re.sub(r'//.*?$', '', schema_json, flags=re.MULTILINE)
        # Replace escaped backslashes to handle regex patterns properly
        schema_json = schema_json.replace('\\\\', '\\')
        try:
            return json.loads(schema_json)
        except Exception as e:
            print(f"Error parsing schema: {e}")
            # Try to write the problematic JSON to debug
            with open('/tmp/debug_schema.json', 'w') as debug:
                debug.write(schema_json)
            print(f"Debug JSON written to /tmp/debug_schema.json")
            return None
    return None

def format_type_info(prop_def: Dict) -> str:
    """Format type information for a property."""
    parts = []

    if '$ref' in prop_def:
        ref_name = prop_def['$ref'].split('/')[-1]
        parts.append(f"Type: Reference to {ref_name}")
    elif 'type' in prop_def:
        parts.append(f"Type: {prop_def['type']}")

    if 'format' in prop_def:
        parts.append(f"Format: {prop_def['format']}")

    if 'pattern' in prop_def:
        parts.append(f"Pattern: {prop_def['pattern']}")

    if 'enum' in prop_def:
        parts.append(f"Enum: {', '.join(str(e) for e in prop_def['enum'][:5])}{'...' if len(prop_def['enum']) > 5 else ''}")

    if 'minimum' in prop_def:
        parts.append(f"Min: {prop_def['minimum']}")

    if 'maximum' in prop_def:
        parts.append(f"Max: {prop_def['maximum']}")

    if 'minLength' in prop_def:
        parts.append(f"MinLength: {prop_def['minLength']}")

    if 'maxLength' in prop_def:
        parts.append(f"MaxLength: {prop_def['maxLength']}")

    if 'minItems' in prop_def:
        parts.append(f"MinItems: {prop_def['minItems']}")

    if 'maxItems' in prop_def:
        parts.append(f"MaxItems: {prop_def['maxItems']}")

    if 'uniqueItems' in prop_def:
        parts.append(f"UniqueItems: {prop_def['uniqueItems']}")

    if 'multipleOf' in prop_def:
        parts.append(f"MultipleOf: {prop_def['multipleOf']}")

    return ' | '.join(parts)

def analyze_definition(name: str, definition: Dict, indent: int = 0) -> List[str]:
    """Recursively analyze a definition."""
    lines = []
    prefix = "  " * indent

    # Type and description
    if 'title' in definition:
        lines.append(f"{prefix}Title: {definition['title']}")

    if 'description' in definition:
        lines.append(f"{prefix}Description: {definition['description']}")

    type_info = format_type_info(definition)
    if type_info:
        lines.append(f"{prefix}{type_info}")

    # Required fields
    if 'required' in definition:
        lines.append(f"{prefix}Required fields: {', '.join(definition['required'])}")

    # Properties
    if 'properties' in definition:
        lines.append(f"{prefix}Properties:")
        for prop_name, prop_def in definition['properties'].items():
            lines.append(f"{prefix}  - {prop_name}:")
            prop_lines = analyze_definition(prop_name, prop_def, indent + 2)
            lines.extend(prop_lines)

    # Array items
    if 'items' in definition:
        lines.append(f"{prefix}Array items:")
        item_lines = analyze_definition('item', definition['items'], indent + 1)
        lines.extend(item_lines)

    # Enum values
    if 'enum' in definition and len(definition['enum']) > 5:
        lines.append(f"{prefix}All enum values: {', '.join(str(e) for e in definition['enum'])}")

    # OneOf, AnyOf, AllOf
    if 'oneOf' in definition:
        lines.append(f"{prefix}OneOf ({len(definition['oneOf'])} options):")
        for i, option in enumerate(definition['oneOf']):
            if 'title' in option:
                lines.append(f"{prefix}  Option {i+1}: {option['title']}")
            if 'properties' in option:
                for k, v in option['properties'].items():
                    if 'const' in v:
                        lines.append(f"{prefix}    {k} = {v['const']}")

    if 'anyOf' in definition:
        lines.append(f"{prefix}AnyOf ({len(definition['anyOf'])} options):")
        for i, option in enumerate(definition['anyOf']):
            if 'title' in option:
                lines.append(f"{prefix}  Option {i+1}: {option['title']}")

    if 'allOf' in definition:
        lines.append(f"{prefix}AllOf ({len(definition['allOf'])} schemas combined)")

    # Conditional logic
    if 'if' in definition:
        lines.append(f"{prefix}Conditional validation: if/then logic present")

    return lines

def main():
    parser = argparse.ArgumentParser(
        description="Extract validation schemas from MDS 2.0 VALIDATOR.json"
    )
    parser.add_argument(
        '--input', '-i',
        default=os.environ.get('MDS_VALIDATOR_FILE', DEFAULT_VALIDATOR_FILE),
        help='Path to MDS 2.0 VALIDATOR.json (default: MDS 2.0 VALIDATOR.json in project root, or MDS_VALIDATOR_FILE env var)'
    )
    parser.add_argument(
        '--output', '-o',
        default=os.environ.get('MDS_SCHEMA_OUTPUT', DEFAULT_OUTPUT_FILE),
        help='Output file path (default: MDS_VALIDATION_REQUIREMENTS.md in project root, or MDS_SCHEMA_OUTPUT env var)'
    )
    args = parser.parse_args()

    input_file = args.input
    output_file = args.output

    # Read the validation file
    with open(input_file, 'r') as f:
        data = json.load(f)

    output_lines = []
    output_lines.append("# MDS 2.0 VALIDATION REQUIREMENTS - COMPLETE ANALYSIS")
    output_lines.append("")
    output_lines.append("**Source:** MDS 2.0 VALIDATOR.json")
    output_lines.append("")
    output_lines.append("**Note:** IGNORE validation failures for `*_attributes` fields (vehicle_attributes, trip_attributes, accessibility_attributes, etc.) as these were not customized for delivery robots.")
    output_lines.append("")
    output_lines.append("---")
    output_lines.append("")

    # Process each test item
    for idx, item in enumerate(data['item'], 1):
        output_lines.append(f"## {idx}. {item['name']}")
        output_lines.append("")

        # Request details
        if 'request' in item:
            req = item['request']
            output_lines.append("### HTTP Request Details")
            output_lines.append("")
            output_lines.append(f"**Method:** `{req.get('method', 'N/A')}`")
            output_lines.append("")

            # URL
            if 'url' in req:
                url = req['url']
                if isinstance(url, dict):
                    raw_url = url.get('raw', '')
                    output_lines.append(f"**URL Pattern:** `{raw_url}`")
                    output_lines.append("")

                    # Extract path
                    if 'path' in url:
                        path = '/' + '/'.join(url['path'])
                        output_lines.append(f"**Endpoint:** `{path}`")
                        output_lines.append("")

                    # Query parameters
                    if 'query' in url and url['query']:
                        output_lines.append("**Query Parameters:**")
                        output_lines.append("")
                        for param in url['query']:
                            key = param.get('key', '')
                            value = param.get('value', '')
                            disabled = param.get('disabled', False)
                            status = '(optional)' if disabled else '(required)'
                            output_lines.append(f"- `{key}`: `{value}` {status}")
                        output_lines.append("")

            # Headers
            if 'header' in req:
                output_lines.append("**Required Headers:**")
                output_lines.append("")
                for header in req['header']:
                    key = header.get('key', '')
                    value = header.get('value', '')
                    output_lines.append(f"- `{key}`: `{value}`")
                output_lines.append("")

        # Extract and analyze schema
        if 'event' in item:
            for event in item['event']:
                if event.get('listen') == 'test' and 'script' in event:
                    schema = extract_schema_from_test(event['script'])
                    if schema:
                        output_lines.append("### Response Schema Validation")
                        output_lines.append("")

                        # Top-level schema
                        output_lines.append("#### Top-Level Schema")
                        output_lines.append("")
                        output_lines.append(f"**Type:** `{schema.get('type', 'N/A')}`")
                        output_lines.append("")

                        if 'additionalProperties' in schema:
                            output_lines.append(f"**Additional Properties Allowed:** `{schema['additionalProperties']}`")
                            output_lines.append("")

                        # Required fields
                        if 'required' in schema:
                            output_lines.append("**Required Fields:**")
                            output_lines.append("")
                            for field in schema['required']:
                                output_lines.append(f"- `{field}`")
                            output_lines.append("")

                        # Properties
                        if 'properties' in schema:
                            output_lines.append("**Properties:**")
                            output_lines.append("")
                            for prop_name, prop_def in schema['properties'].items():
                                output_lines.append(f"##### `{prop_name}`")
                                output_lines.append("")

                                if '$ref' in prop_def:
                                    ref_name = prop_def['$ref'].split('/')[-1]
                                    output_lines.append(f"- Type: Reference to `{ref_name}` (see definitions)")
                                elif 'type' in prop_def:
                                    output_lines.append(f"- Type: `{prop_def['type']}`")

                                if 'description' in prop_def:
                                    output_lines.append(f"- Description: {prop_def['description']}")

                                # Array details
                                if prop_def.get('type') == 'array':
                                    if 'items' in prop_def:
                                        if '$ref' in prop_def['items']:
                                            ref_name = prop_def['items']['$ref'].split('/')[-1]
                                            output_lines.append(f"- Array item type: Reference to `{ref_name}`")
                                        elif 'type' in prop_def['items']:
                                            output_lines.append(f"- Array item type: `{prop_def['items']['type']}`")

                                output_lines.append("")

                        # Definitions
                        if 'definitions' in schema:
                            output_lines.append("#### Schema Definitions")
                            output_lines.append("")
                            output_lines.append("The following type definitions are used in the schema:")
                            output_lines.append("")

                            # Sort definitions by importance
                            important_defs = []
                            other_defs = []

                            for def_name in schema['definitions'].keys():
                                if def_name in ['Event', 'Telemetry', 'Trip', 'Vehicle', 'Vehicle-status']:
                                    important_defs.append(def_name)
                                else:
                                    other_defs.append(def_name)

                            # Process important definitions first
                            for def_name in sorted(important_defs):
                                definition = schema['definitions'][def_name]
                                output_lines.append(f"##### Definition: `{def_name}`")
                                output_lines.append("")

                                # Analyze definition
                                def_lines = analyze_definition(def_name, definition)
                                output_lines.extend(def_lines)
                                output_lines.append("")

                            # Then data types
                            output_lines.append("##### Base Data Types")
                            output_lines.append("")
                            for def_name in sorted(other_defs):
                                definition = schema['definitions'][def_name]
                                output_lines.append(f"**`{def_name}`:**")
                                output_lines.append("")

                                if 'description' in definition:
                                    output_lines.append(f"- {definition['description']}")

                                type_info = format_type_info(definition)
                                if type_info:
                                    output_lines.append(f"- {type_info}")

                                # Special handling for enums
                                if 'enum' in definition and len(definition['enum']) <= 20:
                                    output_lines.append(f"- Allowed values: {', '.join(f'`{e}`' for e in definition['enum'])}")
                                elif 'enum' in definition:
                                    output_lines.append(f"- Allowed values ({len(definition['enum'])} total):")
                                    for i in range(0, len(definition['enum']), 5):
                                        chunk = definition['enum'][i:i+5]
                                        output_lines.append(f"  - {', '.join(f'`{e}`' for e in chunk)}")

                                output_lines.append("")

                        break

        output_lines.append("---")
        output_lines.append("")

    # Write output
    with open(output_file, 'w') as f:
        f.write('\n'.join(output_lines))

    print(f"Analysis complete! Output written to: {output_file}")
    print(f"Total lines: {len(output_lines)}")

if __name__ == '__main__':
    main()
