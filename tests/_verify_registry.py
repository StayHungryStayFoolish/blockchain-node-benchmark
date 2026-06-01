
from utils.csv_schema_registry import CSVSchemaRegistry
bad = []
for ln in CSVSchemaRegistry.all_logical_names():
    try:
        CSVSchemaRegistry.resolve(ln, "aws", "data")
    except Exception as e:
        bad.append((ln, str(e)))
print("python internal consistency:", "OK" if not bad else f"FAIL {bad}")
print("field count:", len(CSVSchemaRegistry.all_logical_names()))
print("provider_aware:", CSVSchemaRegistry.provider_aware_fields())
