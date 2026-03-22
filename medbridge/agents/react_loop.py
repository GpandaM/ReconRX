"""
Native Tool Engine

Implements agent reasoning using native LLM tool calling APIs.
"""

import json
import logging
import time
import inspect
from typing import List, Dict, Any, Callable, Optional

from medbridge.models.react import ReActStep, ReActTrace
from medbridge.models.agent_state import RunContext
from medbridge.llm.base_provider import LLMProvider

logger = logging.getLogger(__name__)

class ReActEngine:
    def __init__(self, llm: LLMProvider, tool_registry: Dict[str, Callable], tool_schemas: List[Dict[str, Any]]):
        self.llm = llm
        self.tool_registry = tool_registry
        self.tool_schemas = tool_schemas
    
    def execute(
        self,
        system_prompt: str,
        initial_observation: str,
        context: RunContext,
        max_iterations: int = 5
    ) -> ReActTrace:
        start_time = time.time()
        steps = []
        total_tokens = 0
        error = None
        
        # Initialize conversation state
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": initial_observation}
        ]
        
        logger.info(f"Starting Native ReAct loop: run_id={context.run_id[:8]}..., max_iterations={max_iterations}")
        
        try:
            for i in range(max_iterations):
                step_start = time.time()
                
                logger.debug(f"Iteration {i+1}/{max_iterations}: Calling LLM...")
                
                response = self.llm.generate(
                    messages=messages,
                    tools=self.tool_schemas,
                    temperature=0.1 # Keep temperature low for tool calling
                )

                print(f"\n{'='*20} RAW LLM RESPONSE {'='*20}")
                print(response.model_dump_json(indent=2))
                # print(response.json(indent=2))
                
                print(f"{'='*60}\n")
                # -----------------------------------------------
                
                total_tokens += response.tokens_used or 0
                
                # Append assistant response to history
                assistant_msg = {"role": "assistant", "content": response.text or ""}
                if response.tool_calls:
                    assistant_msg["tool_calls"] = response.tool_calls
                messages.append(assistant_msg)
                
                # Exit condition: LLM returned text but no tool calls
                if not response.tool_calls:
                    final_output = response.text
                    total_latency = (time.time() - start_time) * 1000
                    
                    logger.info(f"Agent finished reasoning: {final_output[:100]}...")
                    return ReActTrace(
                        run_id=context.run_id,
                        thread_id=context.thread_id,
                        agent_name=context.agent_name,
                        steps=steps,
                        final_output=final_output,
                        total_latency_ms=total_latency,
                        total_tokens=total_tokens,
                        stopped_reason="completed",
                        error=None
                    )
                
                # Execute Tools
                for tool_call in response.tool_calls:
                    func_name = tool_call["function"]["name"]
                    arguments = tool_call["function"]["arguments"]
                    
                    print("~"*50)
                    logger.info(f"Iteration {i+1}: Tool Name={func_name} Arguments={arguments}")
                    
                    if func_name not in self.tool_registry:
                        observation = f"ERROR: Tool '{func_name}' not found."
                        logger.warning(observation)
                    else:
                        try:
                            tool_func = self.tool_registry[func_name]
                            sanitized_arguments = self._sanitize_arguments(tool_func, arguments)
                            tool_result = tool_func(**sanitized_arguments)
                            observation = self._format_observation(tool_result)
                            logger.debug(f"Tool {func_name} executed successfully")
                        except Exception as tool_error:
                            observation = f"ERROR: Tool execution failed: {str(tool_error)}"
                            logger.error(f"Tool {func_name} failed: {tool_error}", exc_info=True)
                    
                    # Add tool response back to messages
                    messages.append({
                        "role": "tool",
                        "content": observation,
                        "name": func_name
                    })
                    
                    # Record step
                    steps.append(ReActStep(
                        iteration=i + 1,
                        thought=response.text or "", # The model's reasoning before the tool call
                        action=func_name,
                        action_input=arguments,
                        observation=observation,
                        latency_ms=(time.time() - step_start) * 1000,
                        tokens_used=response.tokens_used or 0
                    ))

            # Loop finished without completing
            total_latency = (time.time() - start_time) * 1000
            logger.warning("Max iterations reached without final answer.")
            return ReActTrace(
                run_id=context.run_id,
                thread_id=context.thread_id,
                agent_name=context.agent_name,
                steps=steps,
                final_output=steps[-1].observation if steps else "Max iterations reached.",
                total_latency_ms=total_latency,
                total_tokens=total_tokens,
                stopped_reason="max_iterations",
                error=None
            )
            
        except Exception as e:
            logger.error(f"ReAct loop failed: {e}", exc_info=True)
            return ReActTrace(
                run_id=context.run_id,
                thread_id=context.thread_id,
                agent_name=context.agent_name,
                steps=steps,
                final_output=f"ERROR: {str(e)}",
                total_latency_ms=(time.time() - start_time) * 1000,
                total_tokens=total_tokens,
                stopped_reason="error",
                error=str(e)
            )
            
    def _format_observation(self, tool_result: Any, max_length: int = 2000) -> str:
        if isinstance(tool_result, str):
            observation = tool_result
        elif isinstance(tool_result, (dict, list, tuple)):
            observation = json.dumps(tool_result)
        else:
            observation = str(tool_result)
        
        if len(observation) > max_length:
            observation = f"{observation[:max_length]}\n\n[... truncated {len(observation) - max_length} chars ...]"
        return observation


    def _sanitize_arguments(self, func: Callable, arguments: Dict[str, Any]) -> Dict[str, Any]:
            """Cleans up LLM hallucinations in tool arguments."""
            sanitized = {}
            valid_params = inspect.signature(func).parameters

            for key, val in arguments.items():
                # 1. Drop hallucinated keys (ghost arguments)
                if key not in valid_params:
                    logger.warning(f"Dropping unexpected argument '{key}' for tool '{func.__name__}'")
                    continue

                # 2. Unwrap hallucinated schema dictionaries
                if isinstance(val, dict):
                    # If the LLM returned a schema-like dict instead of the raw value
                    if "type" in val or "description" in val:
                        # The LLM usually stuffs the actual value into 'description' or 'value'
                        actual_val = val.get("value", val.get("description", str(val)))
                        logger.warning(f"Unwrapped hallucinated dict for '{key}'. Using: {actual_val}")
                        sanitized[key] = actual_val
                    else:
                        sanitized[key] = val
                else:
                    sanitized[key] = val

            return sanitized
