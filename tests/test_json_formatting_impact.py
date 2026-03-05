"""Test to measure the impact of JSON formatting on schema size."""
import json

# Sample compact schema
compact_schema = {
    "type_id": "SOXIssue",
    "type_name": "Issue",
    "label": "Issue",
    "description": "Represents an issue in OpenPages",
    "mode": "compact",
    "total_field_count": 28,
    "included_field_count": 4,
    "fields": [
        {
            "name": "Resource ID",
            "data_type": "STRING_TYPE",
            "required": True,
            "read_only": False
        },
        {
            "name": "Name",
            "data_type": "STRING_TYPE",
            "required": True,
            "read_only": False
        },
        {
            "name": "Description",
            "data_type": "STRING_TYPE",
            "required": False,
            "read_only": False
        },
        {
            "name": "Status",
            "data_type": "STRING_TYPE",
            "required": True,
            "read_only": False
        }
    ],
    "hierarchical_relationships": [
        {
            "direction": "parent",
            "type": "SOXControl",
            "label": "Controls",
            "join_syntax": "FROM [SOXIssue] JOIN [SOXControl] ON CHILD([SOXIssue])"
        }
    ],
    "note": "This is a compact schema showing only 4 required/system fields out of 28 total fields."
}

print("=" * 80)
print("JSON FORMATTING IMPACT ANALYSIS")
print("=" * 80)

# Test different formatting options
formats = {
    "indent=2 (current)": json.dumps(compact_schema, indent=2),
    "indent=1": json.dumps(compact_schema, indent=1),
    "indent=0 (compact)": json.dumps(compact_schema, indent=0),
    "no indent (minified)": json.dumps(compact_schema),
    "separators=(',', ':')": json.dumps(compact_schema, separators=(',', ':')),
}

results = []
for name, formatted in formats.items():
    size = len(formatted)
    lines = formatted.count('\n')
    results.append((name, size, lines, formatted))

# Sort by size
results.sort(key=lambda x: x[1])

print("\n[SIZE COMPARISON] (smallest to largest):\n")
baseline_size = results[-1][1]  # Largest (indent=2)

for name, size, lines, _ in results:
    reduction = ((baseline_size - size) / baseline_size) * 100
    print(f"{name:30s} {size:5,} bytes  {lines:3} lines  {reduction:5.1f}% smaller")

print("\n" + "=" * 80)
print("DETAILED COMPARISON")
print("=" * 80)

# Show first 200 chars of each format
for name, size, lines, formatted in results:
    print(f"\n{name}:")
    print("-" * 40)
    print(formatted[:200] + "..." if len(formatted) > 200 else formatted)

print("\n" + "=" * 80)
print("RECOMMENDATION")
print("=" * 80)

minified_size = results[0][1]
indent2_size = results[-1][1]
savings = ((indent2_size - minified_size) / indent2_size) * 100

print(f"""
Current format (indent=2): {indent2_size:,} bytes
Minified format: {minified_size:,} bytes
Potential savings: {savings:.1f}%

For AI agents:
- Minified JSON is just as parseable as pretty-printed
- AI agents don't need human-readable formatting
- Smaller payloads = faster processing + lower token costs

RECOMMENDATION: Use json.dumps(schema, separators=(',', ':')) for compact mode
This removes all unnecessary whitespace while maintaining valid JSON.
""")