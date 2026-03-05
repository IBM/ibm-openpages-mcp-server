"""
MCP Client Library Performance Profiling

This script profiles the official MCP Python client library (mcp>=1.9.4)
to identify where the 7-8 second delay is occurring when calling get_resource.

It measures:
1. stdio_client connection setup time
2. Session initialization time
3. Resource read time (broken down by stages)
4. Overall end-to-end time
"""

import asyncio
import time
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class ProfilingTimer:
    """Context manager for timing code blocks"""
    
    def __init__(self, name: str, verbose: bool = True):
        self.name = name
        self.verbose = verbose
        self.start_time = None
        self.end_time = None
        self.duration_ms = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        if self.verbose:
            print(f"  [{self.name}] Starting...")
        return self
    
    def __exit__(self, *args):
        self.end_time = time.perf_counter()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        if self.verbose:
            print(f"  [{self.name}] {self.duration_ms:.2f}ms")
        return False


async def profile_mcp_client():
    """Profile the MCP client library performance"""
    
    print("="*80)
    print("MCP CLIENT LIBRARY PERFORMANCE PROFILING")
    print("="*80)
    print()
    
    # Configure server parameters
    server_params = StdioServerParameters(
        command="python",
        args=["main.py", "--mode", "local"],
        env=None
    )
    
    print("Testing get_resource through MCP client library...")
    print()
    
    # Overall timing
    overall_start = time.perf_counter()
    
    # Stage 1: stdio_client connection setup
    print("STAGE 1: stdio_client Connection Setup")
    print("-" * 80)
    with ProfilingTimer("stdio_client context manager entry"):
        client_context = stdio_client(server_params)
        read_write = await client_context.__aenter__()
        read, write = read_write
    
    try:
        # Stage 2: ClientSession creation and initialization
        print()
        print("STAGE 2: ClientSession Initialization")
        print("-" * 80)
        
        with ProfilingTimer("ClientSession context manager entry"):
            session_context = ClientSession(read, write)
            session = await session_context.__aenter__()
        
        try:
            with ProfilingTimer("session.initialize()"):
                await session.initialize()
            
            # Stage 3: First resource read (cold)
            print()
            print("STAGE 3: First Resource Read (Cold Cache)")
            print("-" * 80)
            
            uri = "openpages://schema/SOXControl"
            
            with ProfilingTimer("session.read_resource() - COLD"):
                result1 = await session.read_resource(uri)
            
            # Get response size
            if result1.contents:
                content_text = result1.contents[0].text if hasattr(result1.contents[0], 'text') else str(result1.contents[0])
                size_kb = len(content_text) / 1024
                print(f"  Response size: {size_kb:.2f} KB")
            
            # Stage 4: Second resource read (warm)
            print()
            print("STAGE 4: Second Resource Read (Warm Cache)")
            print("-" * 80)
            
            with ProfilingTimer("session.read_resource() - WARM"):
                result2 = await session.read_resource(uri)
            
            # Stage 5: Different mode (compact)
            print()
            print("STAGE 5: Resource Read with Compact Mode")
            print("-" * 80)
            
            uri_compact = f"{uri}?mode=compact"
            with ProfilingTimer("session.read_resource() - COMPACT"):
                result3 = await session.read_resource(uri_compact)
            
            if result3.contents:
                content_text = result3.contents[0].text if hasattr(result3.contents[0], 'text') else str(result3.contents[0])
                size_kb = len(content_text) / 1024
                print(f"  Response size: {size_kb:.2f} KB")
            
        finally:
            # Clean up session
            with ProfilingTimer("ClientSession cleanup", verbose=False):
                await session_context.__aexit__(None, None, None)
    
    finally:
        # Clean up client
        with ProfilingTimer("stdio_client cleanup", verbose=False):
            await client_context.__aexit__(None, None, None)
    
    overall_duration = (time.perf_counter() - overall_start) * 1000
    
    # Summary
    print()
    print("="*80)
    print("PROFILING SUMMARY")
    print("="*80)
    print(f"Total end-to-end time: {overall_duration:.2f}ms")
    print()
    print("If you see 7-8 second delays, check which stage is slow:")
    print("  - stdio_client setup: Should be <100ms")
    print("  - Session initialization: Should be <500ms")
    print("  - Resource read (cold): Should be <1000ms")
    print("  - Resource read (warm): Should be <100ms")
    print()
    print("Any stage taking >1 second indicates a bottleneck in the MCP client library.")


async def profile_with_detailed_timing():
    """Profile with even more detailed timing"""
    
    print()
    print("="*80)
    print("DETAILED TIMING ANALYSIS")
    print("="*80)
    print()
    
    server_params = StdioServerParameters(
        command="python",
        args=["main.py", "--mode", "local"],
        env=None
    )
    
    timings = {}
    
    # Measure each step individually
    start = time.perf_counter()
    client_context = stdio_client(server_params)
    timings['create_stdio_client'] = (time.perf_counter() - start) * 1000
    
    start = time.perf_counter()
    read_write = await client_context.__aenter__()
    timings['stdio_client_enter'] = (time.perf_counter() - start) * 1000
    read, write = read_write
    
    try:
        start = time.perf_counter()
        session_context = ClientSession(read, write)
        timings['create_session'] = (time.perf_counter() - start) * 1000
        
        start = time.perf_counter()
        session = await session_context.__aenter__()
        timings['session_enter'] = (time.perf_counter() - start) * 1000
        
        try:
            start = time.perf_counter()
            await session.initialize()
            timings['session_initialize'] = (time.perf_counter() - start) * 1000
            
            # First read
            start = time.perf_counter()
            result = await session.read_resource("openpages://schema/SOXControl")
            timings['first_read'] = (time.perf_counter() - start) * 1000
            
            # Second read
            start = time.perf_counter()
            result = await session.read_resource("openpages://schema/SOXControl")
            timings['second_read'] = (time.perf_counter() - start) * 1000
            
        finally:
            start = time.perf_counter()
            await session_context.__aexit__(None, None, None)
            timings['session_exit'] = (time.perf_counter() - start) * 1000
    
    finally:
        start = time.perf_counter()
        await client_context.__aexit__(None, None, None)
        timings['stdio_client_exit'] = (time.perf_counter() - start) * 1000
    
    # Print detailed breakdown
    print("Detailed Timing Breakdown:")
    print("-" * 80)
    total = 0
    for operation, duration in timings.items():
        print(f"  {operation:30s}: {duration:10.2f}ms")
        total += duration
    print("-" * 80)
    print(f"  {'TOTAL':30s}: {total:10.2f}ms")
    print()
    
    # Identify bottlenecks
    print("Bottleneck Analysis:")
    print("-" * 80)
    bottlenecks = [(k, v) for k, v in timings.items() if v > 1000]
    if bottlenecks:
        print("  Operations taking >1 second:")
        for operation, duration in sorted(bottlenecks, key=lambda x: x[1], reverse=True):
            print(f"    - {operation}: {duration:.2f}ms ({duration/1000:.1f}s)")
    else:
        print("  No operations taking >1 second detected.")
        print("  If you're experiencing 7-8s delays, they may be intermittent or")
        print("  dependent on specific conditions (network, server load, etc.)")


async def main():
    """Run all profiling tests"""
    try:
        # Test 1: Standard profiling
        await profile_mcp_client()
        
        # Test 2: Detailed timing
        await profile_with_detailed_timing()
        
        print()
        print("="*80)
        print("PROFILING COMPLETE")
        print("="*80)
        print()
        print("Next steps:")
        print("1. If stdio_client setup is slow: Issue with process spawning")
        print("2. If session.initialize() is slow: Issue with MCP handshake")
        print("3. If read_resource() is slow: Issue with request/response handling")
        print("4. If all stages are fast: Delay may be intermittent or environment-specific")
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())