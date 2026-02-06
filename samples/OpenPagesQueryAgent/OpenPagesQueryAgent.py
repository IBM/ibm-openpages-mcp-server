"""
OpenPages Query Agent - Based on OOB Langflow Agent Component

This agent extends the standard Langflow Agent component with OpenPages-specific
query generation capabilities, including schema caching and MCP server integration.
"""

import json
import re
from typing import Any, Dict, List, Optional
import time

from langchain_core.tools import StructuredTool, Tool
from pydantic import BaseModel, Field, ValidationError

from lfx.base.agents.agent import LCToolsAgentComponent
from lfx.base.agents.events import ExceptionWithMessageError
from lfx.base.models.model_input_constants import (
    ALL_PROVIDER_FIELDS,
    MODEL_DYNAMIC_UPDATE_FIELDS,
    MODEL_PROVIDERS_DICT,
    MODEL_PROVIDERS_LIST,
    MODELS_METADATA,
)
from lfx.base.models.model_utils import get_model_name
from lfx.components.helpers import CurrentDateComponent
from lfx.components.langchain_utilities.tool_calling import ToolCallingAgentComponent
from lfx.components.models_and_agents.memory import MemoryComponent
from lfx.custom.custom_component.component import get_component_toolkit
from lfx.custom.utils import update_component_build_config
from lfx.helpers.base_model import build_model_from_schema
from lfx.inputs.inputs import BoolInput, SecretStrInput, StrInput
from lfx.io import DropdownInput, IntInput, MessageTextInput, MultilineInput, Output, TableInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dotdict import dotdict
from lfx.schema.message import Message
from lfx.schema.table import EditMode


# OpenPages-specific system prompt
OPENPAGES_QUERY_SYSTEM_PROMPT = """# YOUR ROLE
You are an OpenPages Query Expert that helps users query OpenPages data.

# YOUR WORKFLOW

1. **Understand the Request**: Identify what object types and data the user needs
2. **Check Conversation History**: Look for schemas already retrieved in this conversation
3. **Read Schemas ONLY if needed**: Use read_openpages_schema tool ONLY for object types not yet seen
4. **Construct Query**: Build the query using information from schemas
5. **Execute Query**: Use openpages_query tool (it will validate and provide detailed grammar rules)
6. **Present Results**: Show the data clearly to the user

# KEY PRINCIPLES

⚠️ **Reuse Schema Information**: If you already have schema information from earlier in the conversation, USE IT - don't fetch it again
⚠️ **Schema First (for new types)**: Only read schemas for object types you haven't seen yet in this conversation
⚠️ **Use JOINs for Multiple Objects**: When the request involves multiple related object types, construct a single query with JOINs from the start
⚠️ **Trust the Tool**: The openpages_query tool has comprehensive grammar rules and validation
⚠️ **Learn from Errors**: If a query fails, read the error message carefully - it contains recovery instructions

# SCHEMA CACHING & REUSE

**IMPORTANT**: Schemas are cached and persist throughout the conversation:
- If you've already retrieved a schema for an object type (e.g., SOXControl, SOXIssue), you have that information
- DO NOT call read_openpages_schema again for the same object type in the same conversation
- The schema information remains valid for the entire session
- Only fetch schemas for NEW object types you haven't seen yet
- Example: If you fetched SOXControl schema earlier, and the user asks another question about controls, USE the schema you already have

**When to call read_openpages_schema:**
- ✅ First time encountering an object type in this conversation
- ❌ Object type already retrieved earlier in this conversation
- ❌ Just to "refresh" or "verify" - schemas don't change during a session

# QUERY STRATEGY

**When to Use JOINs:**
Use a single query with JOINs when ALL of these conditions are met:
1. Multiple object types are mentioned in the request
2. The objects have direct hierarchical relationships (check schemas for hierarchical_relationships)
3. The user wants data from multiple related objects together

**Example Scenarios:**
- "Show me controls and their issues" → Use JOIN (Control and Issue are related)
- "List risks with their parent business entities" → Use JOIN (Risk and BusinessEntity are related)
- "Find policies and their associated controls" → Use JOIN (Policy and Control are related)

**When NOT to Use JOINs:**
- Single object type queries
- Queries with aggregate functions (COUNT, SUM, etc.) - aggregates only work with single object types
- When objects are not directly related

# IMPORTANT NOTES

- Field names are case-sensitive and include prefixes (e.g., "OPSS-Iss:Status")
- The openpages_query tool will guide you on correct syntax
- When queries fail, the tool provides specific recovery steps
- Always use exact field names from schemas
- Check hierarchical_relationships in schemas to determine if objects can be joined
"""


def set_advanced_true(component_input):
    component_input.advanced = True
    return component_input


class OpenPagesQueryAgent(ToolCallingAgentComponent):
    display_name: str = "OpenPages Query Agent"
    description: str = "AI agent specialized in generating correct and performant OpenPages queries with schema caching."
    documentation: str = "https://docs.langflow.org/agents"
    icon = "bot"
    beta = False
    name = "OpenPagesQueryAgent"

    # Class-level schema cache (shared across instances)
    _schema_cache: Dict[str, Dict[str, Any]] = {}
    _cache_timestamps: Dict[str, float] = {}
    _cache_ttl: int = 3600  # 1 hour TTL
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._session_schema_cache: Dict[str, Any] = {}
        if hasattr(self, 'schema_cache_ttl') and self.schema_cache_ttl > 0:
            self.__class__._cache_ttl = self.schema_cache_ttl

    memory_inputs = [set_advanced_true(component_input) for component_input in MemoryComponent().inputs]

    # Filter out json_mode from OpenAI inputs since we handle structured output differently
    if "OpenAI" in MODEL_PROVIDERS_DICT:
        openai_inputs_filtered = [
            input_field
            for input_field in MODEL_PROVIDERS_DICT["OpenAI"]["inputs"]
            if not (hasattr(input_field, "name") and input_field.name == "json_mode")
        ]
    else:
        openai_inputs_filtered = []

    inputs = [
        DropdownInput(
            name="agent_llm",
            display_name="Model Provider",
            info="The provider of the language model that the agent will use to generate responses.",
            options=[*MODEL_PROVIDERS_LIST],
            value="OpenAI",
            real_time_refresh=True,
            refresh_button=False,
            input_types=[],
            options_metadata=[MODELS_METADATA[key] for key in MODEL_PROVIDERS_LIST if key in MODELS_METADATA],
            external_options={
                "fields": {
                    "data": {
                        "node": {
                            "name": "connect_other_models",
                            "display_name": "Connect other models",
                            "icon": "CornerDownLeft",
                        }
                    }
                },
            },
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="The API key to use for the model.",
            required=True,
        ),
        StrInput(
            name="base_url",
            display_name="Base URL",
            info="The base URL of the API.",
            required=True,
            show=False,
        ),
        StrInput(
            name="project_id",
            display_name="Project ID",
            info="The project ID of the model.",
            required=True,
            show=False,
        ),
        IntInput(
            name="max_output_tokens",
            display_name="Max Output Tokens",
            info="The maximum number of tokens to generate.",
            show=False,
        ),
        *openai_inputs_filtered,
        MultilineInput(
            name="system_prompt",
            display_name="Agent Instructions",
            info="System Prompt: Initial instructions and context provided to guide the agent's behavior.",
            value=OPENPAGES_QUERY_SYSTEM_PROMPT,
            advanced=False,
        ),
        MessageTextInput(
            name="context_id",
            display_name="Context ID",
            info="The context ID of the chat. Adds an extra layer to the local memory.",
            value="",
            advanced=True,
        ),
        IntInput(
            name="n_messages",
            display_name="Number of Chat History Messages",
            value=100,
            info="Number of chat history messages to retrieve.",
            advanced=True,
            show=True,
        ),
        BoolInput(
            name="enable_schema_caching",
            display_name="Enable Schema Caching",
            value=True,
            info="Cache schemas to reduce MCP server calls and improve performance.",
            advanced=True,
        ),
        IntInput(
            name="schema_cache_ttl",
            display_name="Schema Cache TTL (seconds)",
            value=3600,
            info="Time-to-live for cached schemas in seconds. Set to 0 to disable caching. Default: 3600 (1 hour).",
            advanced=True,
        ),
        MultilineInput(
            name="format_instructions",
            display_name="Output Format Instructions",
            info="Generic Template for structured output formatting. Valid only with Structured response.",
            value=(
                "You are an AI that extracts structured JSON objects from unstructured text. "
                "Use a predefined schema with expected types (str, int, float, bool, dict). "
                "Extract ALL relevant instances that match the schema - if multiple patterns exist, capture them all. "
                "Fill missing or ambiguous values with defaults: null for missing values. "
                "Remove exact duplicates but keep variations that have different field values. "
                "Always return valid JSON in the expected format, never throw errors. "
                "If multiple objects can be extracted, return them all in the structured format."
            ),
            advanced=True,
        ),
        TableInput(
            name="output_schema",
            display_name="Output Schema",
            info=(
                "Schema Validation: Define the structure and data types for structured output. "
                "No validation if no output schema."
            ),
            advanced=True,
            required=False,
            value=[],
            table_schema=[
                {
                    "name": "name",
                    "display_name": "Name",
                    "type": "str",
                    "description": "Specify the name of the output field.",
                    "default": "field",
                    "edit_mode": EditMode.INLINE,
                },
                {
                    "name": "description",
                    "display_name": "Description",
                    "type": "str",
                    "description": "Describe the purpose of the output field.",
                    "default": "description of field",
                    "edit_mode": EditMode.POPOVER,
                },
                {
                    "name": "type",
                    "display_name": "Type",
                    "type": "str",
                    "edit_mode": EditMode.INLINE,
                    "description": ("Indicate the data type of the output field (e.g., str, int, float, bool, dict)."),
                    "options": ["str", "int", "float", "bool", "dict"],
                    "default": "str",
                },
                {
                    "name": "multiple",
                    "display_name": "As List",
                    "type": "boolean",
                    "description": "Set to True if this output field should be a list of the specified type.",
                    "default": "False",
                    "edit_mode": EditMode.INLINE,
                },
            ],
        ),
        *LCToolsAgentComponent.get_base_inputs(),
        BoolInput(
            name="add_current_date_tool",
            display_name="Current Date",
            advanced=True,
            info="If true, will add a tool to the agent that returns the current date.",
            value=True,
        ),
    ]
    outputs = [
        Output(name="response", display_name="Response", method="message_response"),
    ]

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached schema is still valid."""
        if cache_key not in self._cache_timestamps:
            return False
        return (time.time() - self._cache_timestamps[cache_key]) < self._cache_ttl
    
    def _get_cached_schema(self, object_type: str) -> Optional[Dict[str, Any]]:
        """Get schema from cache if available."""
        cache_key = object_type
        
        # Check session cache first
        if object_type in self._session_schema_cache:
            return self._session_schema_cache[object_type]
        
        # Check class-level cache
        if cache_key in self._schema_cache and self._is_cache_valid(cache_key):
            schema = self._schema_cache[cache_key]
            self._session_schema_cache[object_type] = schema
            return schema
        
        return None

    def _cache_schema(self, object_type: str, schema: Dict[str, Any]) -> None:
        """Cache schema at both session and class levels."""
        cache_key = object_type
        self._session_schema_cache[object_type] = schema
        self._schema_cache[cache_key] = schema
        self._cache_timestamps[cache_key] = time.time()

    async def _create_openpages_schema_tools(self) -> List[StructuredTool]:
        """Create schema reading and validation tools with caching."""
        
        class ReadSchemaInput(BaseModel):
            object_type: str = Field(description="Object type to read schema for (e.g., SOXControl, SOXIssue)")
        
        def read_schema_tool(object_type: str) -> str:
            """Read OpenPages schema with automatic caching."""
            try:
                # Check cache first if caching is enabled
                if getattr(self, 'schema_cache_ttl', 3600) > 0:
                    cached = self._get_cached_schema(object_type)
                    if cached:
                        logger.debug(f"Schema cache HIT for {object_type}")
                        return f"✅ Schema for {object_type} (from cache)\n{json.dumps(cached, indent=2)}"
                
                logger.debug(f"Schema cache MISS for {object_type} - would fetch from MCP server")
                
                # In production, this would call the MCP server's resource handler
                # For now, return a placeholder that indicates caching is working
                schema_data = {
                    "type_id": object_type,
                    "note": "This would be fetched from MCP server: openpages://schema/" + object_type,
                    "fields": []
                }
                
                # Cache the result if caching is enabled
                if getattr(self, 'schema_cache_ttl', 3600) > 0:
                    self._cache_schema(object_type, schema_data)
                    logger.debug(f"Cached schema for {object_type} (TTL: {self._cache_ttl}s)")
                    return f"✅ Schema for {object_type} (cached for {self._cache_ttl}s)\n{json.dumps(schema_data, indent=2)}"
                
                return f"Schema for {object_type}\n{json.dumps(schema_data, indent=2)}"
            except Exception as e:
                logger.error(f"Error reading schema for {object_type}: {e}")
                return f"Error reading schema: {str(e)}"
        
        class ValidateQueryInput(BaseModel):
            query: str = Field(description="OpenPages query to validate")
        
        def validate_query_tool(query: str) -> str:
            """Validate OpenPages query syntax."""
            errors = []
            
            # Check for unsupported AS keyword
            if re.search(r'\bAS\b', query, re.IGNORECASE):
                errors.append("❌ AS keyword not supported in OpenPages queries")
            
            # Check for unsupported DISTINCT
            if re.search(r'\bDISTINCT\b', query, re.IGNORECASE):
                errors.append("❌ DISTINCT not supported")
            
            # Check for aggregates with JOINs (not allowed)
            if re.search(r'\b(COUNT|SUM|AVG|MIN|MAX)\b', query, re.IGNORECASE):
                if re.search(r'\b(JOIN|PARENT|CHILD|ANCESTOR|DESCENDANT)\b', query, re.IGNORECASE):
                    errors.append("❌ Aggregate functions (COUNT, SUM, etc.) cannot be used with JOINs")
            
            # Check for proper bracket usage
            if not re.search(r'\[[^\]]+\]', query):
                errors.append("⚠️ Use square brackets for object and field names: [ObjectType].[FieldName]")
            
            # Check for balanced brackets
            open_count = query.count('[')
            close_count = query.count(']')
            if open_count != close_count:
                errors.append(f"❌ Unbalanced brackets: {open_count} opening vs {close_count} closing")
            
            if errors:
                return "Query validation failed:\n" + "\n".join(errors)
            return "✅ Query syntax appears valid"
        
        return [
            StructuredTool(
                name="read_openpages_schema",
                description="Read schema for an OpenPages object type. ALWAYS use this BEFORE generating queries to get exact field names. Schemas are automatically cached.",
                func=read_schema_tool,
                args_schema=ReadSchemaInput,
            ),
            StructuredTool(
                name="validate_openpages_query",
                description="Validate OpenPages query syntax. Use AFTER generating a query but BEFORE executing it with openpages_query tool.",
                func=validate_query_tool,
                args_schema=ValidateQueryInput,
            ),
        ]

    async def get_agent_requirements(self):
        """Get the agent requirements for the agent."""
        llm_model, display_name = await self.get_llm()
        if llm_model is None:
            msg = "No language model selected. Please choose a model to proceed."
            raise ValueError(msg)
        self.model_name = get_model_name(llm_model, display_name=display_name)

        # Get memory data
        self.chat_history = await self.get_memory_data()
        await logger.adebug(f"Retrieved {len(self.chat_history)} chat history messages")
        if isinstance(self.chat_history, Message):
            self.chat_history = [self.chat_history]

        # Initialize tools list if not already set
        if not isinstance(self.tools, list):  # type: ignore[has-type]
            self.tools = []
        
        # Add OpenPages schema tools with caching
        openpages_tools = await self._create_openpages_schema_tools()
        self.tools.extend(openpages_tools)
        await logger.adebug(f"Added {len(openpages_tools)} OpenPages schema tools with caching")

        # Add current date tool if enabled
        if self.add_current_date_tool:
            current_date_tool = (await CurrentDateComponent(**self.get_base_args()).to_toolkit()).pop(0)

            if not isinstance(current_date_tool, StructuredTool):
                msg = "CurrentDateComponent must be converted to a StructuredTool"
                raise TypeError(msg)
            self.tools.append(current_date_tool)

        # Set shared callbacks for tracing the tools used by the agent
        self.set_tools_callbacks(self.tools, self._get_shared_callbacks())

        return llm_model, self.chat_history, self.tools

    async def message_response(self) -> Message:
        try:
            llm_model, self.chat_history, self.tools = await self.get_agent_requirements()
            # Set up and run agent
            self.set(
                llm=llm_model,
                tools=self.tools or [],
                chat_history=self.chat_history,
                input_value=self.input_value,
                system_prompt=self.system_prompt,
            )
            agent = self.create_agent_runnable()
            result = await self.run_agent(agent)

            # Store result for potential JSON output
            self._agent_result = result

        except (ValueError, TypeError, KeyError) as e:
            await logger.aerror(f"{type(e).__name__}: {e!s}")
            raise
        except ExceptionWithMessageError as e:
            await logger.aerror(f"ExceptionWithMessageError occurred: {e}")
            raise
        # Avoid catching blind Exception; let truly unexpected exceptions propagate
        except Exception as e:
            await logger.aerror(f"Unexpected error: {e!s}")
            raise
        else:
            return result

    def _preprocess_schema(self, schema):
        """Preprocess schema to ensure correct data types for build_model_from_schema."""
        processed_schema = []
        for field in schema:
            processed_field = {
                "name": str(field.get("name", "field")),
                "type": str(field.get("type", "str")),
                "description": str(field.get("description", "")),
                "multiple": field.get("multiple", False),
            }
            # Ensure multiple is handled correctly
            if isinstance(processed_field["multiple"], str):
                processed_field["multiple"] = processed_field["multiple"].lower() in [
                    "true",
                    "1",
                    "t",
                    "y",
                    "yes",
                ]
            processed_schema.append(processed_field)
        return processed_schema

    async def build_structured_output_base(self, content: str):
        """Build structured output with optional BaseModel validation."""
        json_pattern = r"\{.*\}"
        schema_error_msg = "Try setting an output schema"

        # Try to parse content as JSON first
        json_data = None
        try:
            json_data = json.loads(content)
        except json.JSONDecodeError:
            json_match = re.search(json_pattern, content, re.DOTALL)
            if json_match:
                try:
                    json_data = json.loads(json_match.group())
                except json.JSONDecodeError:
                    return {"content": content, "error": schema_error_msg}
            else:
                return {"content": content, "error": schema_error_msg}

        # If no output schema provided, return parsed JSON without validation
        if not hasattr(self, "output_schema") or not self.output_schema or len(self.output_schema) == 0:
            return json_data

        # Use BaseModel validation with schema
        try:
            processed_schema = self._preprocess_schema(self.output_schema)
            output_model = build_model_from_schema(processed_schema)

            # Validate against the schema
            if isinstance(json_data, list):
                # Multiple objects
                validated_objects = []
                for item in json_data:
                    try:
                        validated_obj = output_model.model_validate(item)
                        validated_objects.append(validated_obj.model_dump())
                    except ValidationError as e:
                        await logger.aerror(f"Validation error for item: {e}")
                        # Include invalid items with error info
                        validated_objects.append({"data": item, "validation_error": str(e)})
                return validated_objects

            # Single object
            try:
                validated_obj = output_model.model_validate(json_data)
                return [validated_obj.model_dump()]  # Return as list for consistency
            except ValidationError as e:
                await logger.aerror(f"Validation error: {e}")
                return [{"data": json_data, "validation_error": str(e)}]

        except (TypeError, ValueError) as e:
            await logger.aerror(f"Error building structured output: {e}")
            # Fallback to parsed JSON without validation
            return json_data

    async def json_response(self) -> Data:
        """Convert agent response to structured JSON Data output with schema validation."""
        # Always use structured chat agent for JSON response mode for better JSON formatting
        try:
            system_components = []

            # 1. Agent Instructions (system_prompt)
            agent_instructions = getattr(self, "system_prompt", "") or ""
            if agent_instructions:
                system_components.append(f"{agent_instructions}")

            # 2. Format Instructions
            format_instructions = getattr(self, "format_instructions", "") or ""
            if format_instructions:
                system_components.append(f"Format instructions: {format_instructions}")

            # 3. Schema Information from BaseModel
            if hasattr(self, "output_schema") and self.output_schema and len(self.output_schema) > 0:
                try:
                    processed_schema = self._preprocess_schema(self.output_schema)
                    output_model = build_model_from_schema(processed_schema)
                    schema_dict = output_model.model_json_schema()
                    schema_info = (
                        "You are given some text that may include format instructions, "
                        "explanations, or other content alongside a JSON schema.\n\n"
                        "Your task:\n"
                        "- Extract only the JSON schema.\n"
                        "- Return it as valid JSON.\n"
                        "- Do not include format instructions, explanations, or extra text.\n\n"
                        "Input:\n"
                        f"{json.dumps(schema_dict, indent=2)}\n\n"
                        "Output (only JSON schema):"
                    )
                    system_components.append(schema_info)
                except (ValidationError, ValueError, TypeError, KeyError) as e:
                    await logger.aerror(f"Could not build schema for prompt: {e}", exc_info=True)

            # Combine all components
            combined_instructions = "\n\n".join(system_components) if system_components else ""
            llm_model, self.chat_history, self.tools = await self.get_agent_requirements()
            self.set(
                llm=llm_model,
                tools=self.tools or [],
                chat_history=self.chat_history,
                input_value=self.input_value,
                system_prompt=combined_instructions,
            )

            # Create and run structured chat agent
            try:
                structured_agent = self.create_agent_runnable()
            except (NotImplementedError, ValueError, TypeError) as e:
                await logger.aerror(f"Error with structured chat agent: {e}")
                raise
            try:
                result = await self.run_agent(structured_agent)
            except (
                ExceptionWithMessageError,
                ValueError,
                TypeError,
                RuntimeError,
            ) as e:
                await logger.aerror(f"Error with structured agent result: {e}")
                raise
            # Extract content from structured agent result
            if hasattr(result, "content"):
                content = result.content
            elif hasattr(result, "text"):
                content = result.text
            else:
                content = str(result)

        except (
            ExceptionWithMessageError,
            ValueError,
            TypeError,
            NotImplementedError,
            AttributeError,
        ) as e:
            await logger.aerror(f"Error with structured chat agent: {e}")
            # Fallback to regular agent
            content_str = "No content returned from agent"
            return Data(data={"content": content_str, "error": str(e)})

        # Process with structured output validation
        try:
            structured_output = await self.build_structured_output_base(content)

            # Handle different output formats
            if isinstance(structured_output, list) and structured_output:
                if len(structured_output) == 1:
                    return Data(data=structured_output[0])
                return Data(data={"results": structured_output})
            if isinstance(structured_output, dict):
                return Data(data=structured_output)
            return Data(data={"content": content})

        except (ValueError, TypeError) as e:
            await logger.aerror(f"Error in structured output processing: {e}")
            return Data(data={"content": content, "error": str(e)})

    async def get_memory_data(self):
        # TODO: This is a temporary fix to avoid message duplication. We should develop a function for this.
        messages = (
            await MemoryComponent(**self.get_base_args())
            .set(
                session_id=self.graph.session_id,
                context_id=self.context_id,
                order="Ascending",
                n_messages=self.n_messages,
            )
            .retrieve_messages()
        )
        return [
            message for message in messages if getattr(message, "id", None) != getattr(self.input_value, "id", None)
        ]

    async def get_llm(self):
        if not isinstance(self.agent_llm, str):
            return self.agent_llm, None

        try:
            provider_info = MODEL_PROVIDERS_DICT.get(self.agent_llm)
            if not provider_info:
                msg = f"Invalid model provider: {self.agent_llm}"
                raise ValueError(msg)

            component_class = provider_info.get("component_class")
            display_name = component_class.display_name
            inputs = provider_info.get("inputs")
            prefix = provider_info.get("prefix", "")

            return self._build_llm_model(component_class, inputs, prefix), display_name

        except (AttributeError, ValueError, TypeError, RuntimeError) as e:
            await logger.aerror(f"Error building {self.agent_llm} language model: {e!s}")
            msg = f"Failed to initialize language model: {e!s}"
            raise ValueError(msg) from e

    def _build_llm_model(self, component, inputs, prefix=""):
        model_kwargs = {}
        for input_ in inputs:
            if hasattr(self, f"{prefix}{input_.name}"):
                model_kwargs[input_.name] = getattr(self, f"{prefix}{input_.name}")
        return component.set(**model_kwargs).build_model()

    def set_component_params(self, component):
        provider_info = MODEL_PROVIDERS_DICT.get(self.agent_llm)
        if provider_info:
            inputs = provider_info.get("inputs")
            prefix = provider_info.get("prefix")
            # Filter out json_mode and only use attributes that exist on this component
            model_kwargs = {}
            for input_ in inputs:
                if hasattr(self, f"{prefix}{input_.name}"):
                    model_kwargs[input_.name] = getattr(self, f"{prefix}{input_.name}")

            return component.set(**model_kwargs)
        return component

    def delete_fields(self, build_config: dotdict, fields: dict | list[str]) -> None:
        """Delete specified fields from build_config."""
        for field in fields:
            if build_config is not None and field in build_config:
                build_config.pop(field, None)

    def update_input_types(self, build_config: dotdict) -> dotdict:
        """Update input types for all fields in build_config."""
        for key, value in build_config.items():
            if isinstance(value, dict):
                if value.get("input_types") is None:
                    build_config[key]["input_types"] = []
            elif hasattr(value, "input_types") and value.input_types is None:
                value.input_types = []
        return build_config

    async def update_build_config(
        self, build_config: dotdict, field_value: str, field_name: str | None = None
    ) -> dotdict:
        # Iterate over all providers in the MODEL_PROVIDERS_DICT
        # Existing logic for updating build_config
        if field_name in ("agent_llm",):
            build_config["agent_llm"]["value"] = field_value
            provider_info = MODEL_PROVIDERS_DICT.get(field_value)
            if provider_info:
                component_class = provider_info.get("component_class")
                if component_class and hasattr(component_class, "update_build_config"):
                    # Call the component class's update_build_config method
                    build_config = await update_component_build_config(
                        component_class, build_config, field_value, "model_name"
                    )

            provider_configs: dict[str, tuple[dict, list[dict]]] = {
                provider: (
                    MODEL_PROVIDERS_DICT[provider]["fields"],
                    [
                        MODEL_PROVIDERS_DICT[other_provider]["fields"]
                        for other_provider in MODEL_PROVIDERS_DICT
                        if other_provider != provider
                    ],
                )
                for provider in MODEL_PROVIDERS_DICT
            }
            if field_value in provider_configs:
                fields_to_add, fields_to_delete = provider_configs[field_value]

                # Delete fields from other providers
                for fields in fields_to_delete:
                    self.delete_fields(build_config, fields)

                # Add provider-specific fields
                if field_value == "OpenAI" and not any(field in build_config for field in fields_to_add):
                    build_config.update(fields_to_add)
                else:
                    build_config.update(fields_to_add)
                # Reset input types for agent_llm
                build_config["agent_llm"]["input_types"] = []
                build_config["agent_llm"]["display_name"] = "Model Provider"
            elif field_value == "connect_other_models":
                # Delete all provider fields
                self.delete_fields(build_config, ALL_PROVIDER_FIELDS)
                # # Update with custom component
                custom_component = DropdownInput(
                    name="agent_llm",
                    display_name="Language Model",
                    info="The provider of the language model that the agent will use to generate responses.",
                    options=[*MODEL_PROVIDERS_LIST],
                    real_time_refresh=True,
                    refresh_button=False,
                    input_types=["LanguageModel"],
                    placeholder="Awaiting model input.",
                    options_metadata=[MODELS_METADATA[key] for key in MODEL_PROVIDERS_LIST if key in MODELS_METADATA],
                    external_options={
                        "fields": {
                            "data": {
                                "node": {
                                    "name": "connect_other_models",
                                    "display_name": "Connect other models",
                                    "icon": "CornerDownLeft",
                                },
                            }
                        },
                    },
                )
                build_config.update({"agent_llm": custom_component.to_dict()})
            # Update input types for all fields
            build_config = self.update_input_types(build_config)

            # Validate required keys
            default_keys = [
                "code",
                "_type",
                "agent_llm",
                "tools",
                "input_value",
                "add_current_date_tool",
                "system_prompt",
                "agent_description",
                "max_iterations",
                "handle_parsing_errors",
                "verbose",
            ]
            missing_keys = [key for key in default_keys if key not in build_config]
            if missing_keys:
                msg = f"Missing required keys in build_config: {missing_keys}"
                raise ValueError(msg)
        if (
            isinstance(self.agent_llm, str)
            and self.agent_llm in MODEL_PROVIDERS_DICT
            and field_name in MODEL_DYNAMIC_UPDATE_FIELDS
        ):
            provider_info = MODEL_PROVIDERS_DICT.get(self.agent_llm)
            if provider_info:
                component_class = provider_info.get("component_class")
                component_class = self.set_component_params(component_class)
                prefix = provider_info.get("prefix")
                if component_class and hasattr(component_class, "update_build_config"):
                    # Call each component class's update_build_config method
                    # remove the prefix from the field_name
                    if isinstance(field_name, str) and isinstance(prefix, str):
                        field_name_without_prefix = field_name.replace(prefix, "")
                    else:
                        field_name_without_prefix = field_name
                    build_config = await update_component_build_config(
                        component_class, build_config, field_value, field_name_without_prefix
                    )
        return dotdict({k: v.to_dict() if hasattr(v, "to_dict") else v for k, v in build_config.items()})

    async def _get_tools(self) -> list[Tool]:
        component_toolkit = get_component_toolkit()
        tools_names = self._build_tools_names()
        agent_description = self.get_tool_description()
        # TODO: Agent Description Depreciated Feature to be removed
        description = f"{agent_description}{tools_names}"

        tools = component_toolkit(component=self).get_tools(
            tool_name="Call_Agent",
            tool_description=description,
            # here we do not use the shared callbacks as we are exposing the agent as a tool
            callbacks=self.get_langchain_callbacks(),
        )
        if hasattr(self, "tools_metadata"):
            tools = component_toolkit(component=self, metadata=self.tools_metadata).update_tools_metadata(tools=tools)

        return tools