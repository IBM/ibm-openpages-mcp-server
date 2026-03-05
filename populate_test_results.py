#!/usr/bin/env python3
"""
Script to populate Orchestrate test cases with actual results from OpenPages MCP server.
This script reads the CSV file, executes each prompt, and writes the results back.
"""

import csv
import json
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def execute_query(session, query, limit=5):
    """Execute an OpenPages query and return the result."""
    try:
        result = await session.call_tool(
            "execute_openpages_query",
            arguments={
                "query": query,
                "limit": limit
            }
        )
        return result.content[0].text if result.content else "No result"
    except Exception as e:
        return f"Error: {str(e)}"

async def access_resource(session, uri):
    """Access an OpenPages resource and return the content."""
    try:
        result = await session.read_resource(uri)
        if result.contents:
            content = result.contents[0]
            if hasattr(content, 'text'):
                # Truncate long responses for readability
                text = content.text
                if len(text) > 500:
                    return text[:500] + "... (truncated)"
                return text
            return str(content)
        return "No content"
    except Exception as e:
        return f"Error: {str(e)}"

async def process_test_cases():
    """Process all test cases and populate results."""
    
    # Read the CSV file
    with open('orchestrate_test_cases.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        test_cases = list(reader)
    
    # Connect to MCP server
    server_params = StdioServerParameters(
        command="python",
        args=["main.py", "--mode", "local"],
        env=None
    )
    
    results = []
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            print(f"Processing {len(test_cases)} test cases...")
            
            for i, test_case in enumerate(test_cases, 1):
                prompt = test_case['Prompt']
                current_answer = test_case['Answer']
                
                print(f"\n[{i}/{len(test_cases)}] Processing: {prompt[:60]}...")
                
                # Determine the type of test and execute accordingly
                if current_answer.startswith("SELECT"):
                    # It's a query - execute it
                    result = await execute_query(session, current_answer)
                elif current_answer.startswith("Read resource"):
                    # Extract URI and access resource
                    uri = current_answer.split("openpages://")[1].split()[0]
                    uri = f"openpages://{uri}"
                    result = await access_resource(session, uri)
                elif current_answer.startswith("Use "):
                    # It's a tool invocation - for now, just note it
                    result = f"Tool invocation test: {current_answer}"
                else:
                    # Unknown format
                    result = f"Test format: {current_answer}"
                
                # Store result
                results.append({
                    'Prompt': prompt,
                    'Answer': result
                })
                
                # Small delay to avoid overwhelming the server
                await asyncio.sleep(0.1)
    
    # Write results back to CSV
    with open('orchestrate_test_results.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['Prompt', 'Answer'])
        writer.writeheader()
        writer.writerows(results)
    
    print(f"\n✓ Results written to orchestrate_test_results.csv")
    print(f"  Processed {len(results)} test cases")

if __name__ == "__main__":
    asyncio.run(process_test_cases())