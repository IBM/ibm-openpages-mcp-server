"""
MCP Protocol Performance Profiling Script

This script profiles the MCP protocol overhead by measuring timing at each stage:
1. JSON-RPC message parsing/serialization
2. Request routing and method dispatch
3. Resource handler execution
4. Cache operations (Layer 1 and Layer 2)
5. Response formatting

Usage:
    python test_mcp_protocol_profiling.py
"""

import asyncio
import json
import time
import sys
from typing import Dict, Any
from src.app.mcp.mcp_server import MCPServer
from src.app.config.settings import Settings

# Timing results storage
timing_results = []


class ProfilingTimer:
    """Context manager for timing code blocks"""
    
    def __init__(self, name: str):
        self.name = name
        self.start_time = None
        self.end_time = None
        self.duration = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, *args):
        self.end_time = time.perf_counter()
        if self.start_time is not None:
            self.duration = (self.end_time - self.start_time) * 1000  # Convert to ms
        else:
            self.duration = 0.0
        timing_results.append({
            "stage": self.name,
            "duration_ms": round(self.duration, 2)
        })
        print(f"  [{self.name}] {self.duration:.2f}ms")


async def profile_get_resource_request(server: MCPServer, type_id: str, mode: str = "compact"):
    """
    Profile a complete get_resource request through the MCP protocol
    
    Args:
        server: MCPServer instance
        type_id: Object type ID to request
        mode: Schema mode (compact or full)
    """
    print(f"\n{'='*80}")
    print(f"Profiling get_resource request: {type_id} (mode={mode})")
    print(f"{'='*80}\n")
    
    # Clear timing results
    timing_results.clear()
    
    # Stage 1: Build JSON-RPC request
    with ProfilingTimer("1. Build JSON-RPC request"):
        request_data = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "resources/read",
            "params": {
                "uri": f"openpages://schema/{type_id}",
                "mode": mode
            }
        }
    
    # Stage 2: Serialize request to JSON
    with ProfilingTimer("2. Serialize request to JSON"):
        request_json = json.dumps(request_data)
    
    # Stage 3: Parse JSON request (simulating stdin read)
    with ProfilingTimer("3. Parse JSON request"):
        parsed_request = json.loads(request_json)
    
    # Stage 4: Process request through MCP server
    total_start = time.perf_counter()
    
    with ProfilingTimer("4. Total request processing"):
        # Stage 4a: Request processor routing
        with ProfilingTimer("4a. Request processor routing"):
            method = parsed_request.get("method")
            params = parsed_request.get("params", {})
            request_id = parsed_request.get("id")
        
        # Stage 4b: Resource handler execution
        with ProfilingTimer("4b. Resource handler execution"):
            # This includes cache lookups and schema building
            result = await server.resource_handlers.handle_read_resource(params)
        
        # Stage 4c: Format response
        with ProfilingTimer("4c. Format JSON-RPC response"):
            response = {
                "jsonrpc": "2.0",
                "result": result,
                "id": request_id
            }
    
    total_duration = (time.perf_counter() - total_start) * 1000
    
    # Stage 5: Serialize response to JSON
    with ProfilingTimer("5. Serialize response to JSON"):
        response_json = json.dumps(response)
    
    # Stage 6: Calculate response size
    with ProfilingTimer("6. Calculate response size"):
        response_size = len(response_json)
        response_size_kb = response_size / 1024
    
    # Print summary
    print(f"\n{'='*80}")
    print(f"PROFILING SUMMARY")
    print(f"{'='*80}")
    print(f"Total request processing time: {total_duration:.2f}ms")
    print(f"Response size: {response_size_kb:.2f} KB ({response_size:,} bytes)")
    
    # Get cache statistics
    layer1_stats = server.schema_builder.get_cache_stats()
    layer2_stats = server.resource_handlers.get_schema_cache_stats()
    
    print(f"\nCache Statistics:")
    print(f"  Layer 1 (Type Definitions):")
    print(f"    - Size: {layer1_stats['current_size']}/{layer1_stats['max_size']}")
    print(f"    - Hit rate: {layer1_stats['hit_rate']}")
    print(f"    - Hits: {layer1_stats['hits']}, Misses: {layer1_stats['misses']}")
    print(f"  Layer 2 (Formatted Schemas):")
    print(f"    - Size: {layer2_stats['current_size']}/{layer2_stats['max_size']}")
    print(f"    - Hit rate: {layer2_stats['hit_rate']}")
    print(f"    - Hits: {layer2_stats['hits']}, Misses: {layer2_stats['misses']}")
    
    # Breakdown by stage
    print(f"\nTiming Breakdown:")
    for result in timing_results:
        percentage = (result['duration_ms'] / total_duration) * 100
        print(f"  {result['stage']}: {result['duration_ms']:.2f}ms ({percentage:.1f}%)")
    
    return {
        "total_duration_ms": total_duration,
        "response_size_kb": response_size_kb,
        "layer1_stats": layer1_stats,
        "layer2_stats": layer2_stats,
        "timing_breakdown": timing_results.copy()
    }


async def run_profiling_tests():
    """Run comprehensive profiling tests"""
    print("="*80)
    print("MCP PROTOCOL PERFORMANCE PROFILING")
    print("="*80)
    
    # Initialize server
    print("\nInitializing MCP server...")
    server = MCPServer()
    
    # Initialize authentication
    print("Initializing authentication...")
    await server.initialize_client()
    
    # Load dynamic schemas
    print("Loading dynamic schemas...")
    await server.load_dynamic_schemas()
    
    # Get configured object types
    object_types = [obj.get("type_id") for obj in server.settings.OPENPAGES_OBJECT_TYPES if obj.get("type_id")]
    
    if not object_types:
        print("ERROR: No object types configured!")
        return
    
    # Filter out None values and ensure all are strings
    valid_types = [t for t in object_types if t is not None]
    if not valid_types:
        print("ERROR: No valid object types found!")
        return
    
    print(f"\nConfigured object types: {', '.join(valid_types)}")
    
    # Test 1: Cold cache (first request)
    print(f"\n{'#'*80}")
    print("TEST 1: COLD CACHE (First Request)")
    print(f"{'#'*80}")
    
    type_id = valid_types[0]
    result1 = await profile_get_resource_request(server, type_id, mode="compact")
    
    # Test 2: Warm cache (second request, same type and mode)
    print(f"\n{'#'*80}")
    print("TEST 2: WARM CACHE (Second Request - Same Type & Mode)")
    print(f"{'#'*80}")
    
    result2 = await profile_get_resource_request(server, type_id, mode="compact")
    
    # Test 3: Different mode (cache miss on Layer 2, hit on Layer 1)
    print(f"\n{'#'*80}")
    print("TEST 3: DIFFERENT MODE (Layer 2 Miss, Layer 1 Hit)")
    print(f"{'#'*80}")
    
    result3 = await profile_get_resource_request(server, type_id, mode="full")
    
    # Test 4: Back to compact mode (cache hit on both layers)
    print(f"\n{'#'*80}")
    print("TEST 4: BACK TO COMPACT MODE (Both Layers Hit)")
    print(f"{'#'*80}")
    
    result4 = await profile_get_resource_request(server, type_id, mode="compact")
    
    # Final comparison
    print(f"\n{'='*80}")
    print("PERFORMANCE COMPARISON")
    print(f"{'='*80}")
    print(f"Test 1 (Cold cache):        {result1['total_duration_ms']:.2f}ms")
    print(f"Test 2 (Warm cache):        {result2['total_duration_ms']:.2f}ms")
    print(f"Test 3 (Different mode):    {result3['total_duration_ms']:.2f}ms")
    print(f"Test 4 (Back to compact):   {result4['total_duration_ms']:.2f}ms")
    
    speedup_cold_to_warm = result1['total_duration_ms'] / result2['total_duration_ms']
    print(f"\nSpeedup (cold -> warm): {speedup_cold_to_warm:.1f}x")
    
    # Analyze where time is spent
    print(f"\n{'='*80}")
    print("TIME DISTRIBUTION ANALYSIS")
    print(f"{'='*80}")
    
    # Analyze Test 2 (warm cache) to see protocol overhead
    print("\nWarm Cache Request Breakdown:")
    for timing in result2['timing_breakdown']:
        print(f"  {timing['stage']}: {timing['duration_ms']:.2f}ms")
    
    # Calculate protocol overhead (everything except resource handler execution)
    resource_handler_time = next(
        (t['duration_ms'] for t in result2['timing_breakdown'] if '4b' in t['stage']),
        0
    )
    protocol_overhead = result2['total_duration_ms'] - resource_handler_time
    
    print(f"\nProtocol Overhead Analysis (Warm Cache):")
    print(f"  Resource handler execution: {resource_handler_time:.2f}ms")
    print(f"  Protocol overhead:          {protocol_overhead:.2f}ms")
    print(f"  Overhead percentage:        {(protocol_overhead/result2['total_duration_ms'])*100:.1f}%")
    
    # Cleanup
    await server.client.close()
    
    print(f"\n{'='*80}")
    print("PROFILING COMPLETE")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    asyncio.run(run_profiling_tests())