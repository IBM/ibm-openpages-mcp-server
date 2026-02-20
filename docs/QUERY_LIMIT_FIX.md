# Query Limit Fix

## Issue

The `limit` parameter in query tools was not working correctly. When requesting 10 objects, the system was returning 100 objects instead.

## Root Cause

The OpenPages REST API ignores the SQL `LIMIT` clause in the query statement. Instead, it uses the `limit` parameter in the API request body.

The code was:
1. Adding `LIMIT {limit}` to the SQL query statement
2. Calling `client.query(query)` without passing the limit parameter
3. The client.query() method has a default limit of 100

Result: The SQL LIMIT was ignored, and the default API limit of 100 was used.

## Fix

**Changed in**: `src/app/tools/generic_object_tools.py`

**Before**:
```python
query += f" LIMIT {limit}"
result = await self.client.query(query)
```

**After**:
```python
# Note: Do not add LIMIT to SQL query - OpenPages API ignores it
# Instead, pass limit parameter to client.query() method
result = await self.client.query(query, limit=limit)
```

## How It Works Now

1. The `limit` parameter from the tool arguments is extracted (default: 20, max: 100)
2. The SQL query is built WITHOUT a LIMIT clause
3. The `limit` parameter is passed to `client.query(query, limit=limit)`
4. The OpenPages API receives the limit in the request body: `{"limit": 10, ...}`
5. The API correctly returns only the requested number of rows

## Example

**Request**:
```json
{
  "limit": 10,
  "sort_by": [{"field": "Creation Date", "order": "DESC"}]
}
```

**Generated SQL** (no LIMIT clause):
```sql
SELECT [Resource ID], [Name], [Description]
FROM [SOXControl]
WHERE [Resource ID] IS NOT NULL
ORDER BY [Creation Date] DESC
```

**API Request Body**:
```json
{
  "statement": "SELECT ... ORDER BY [Creation Date] DESC",
  "offset": 0,
  "max_rows": 500,
  "limit": 10,
  "case_insensitive": false,
  "honor_primary": false
}
```

**Result**: Exactly 10 rows returned ✓

## Testing

Updated tests to verify:
1. The limit parameter is correctly passed to client.query()
2. The SQL query does NOT contain a LIMIT clause
3. The correct number of results are returned

All 14 tests pass successfully.

## Impact

- ✅ Query limit now works correctly
- ✅ No breaking changes to API
- ✅ Backward compatible
- ✅ All existing tests pass