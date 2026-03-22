import inspect
import re
from typing import Callable, Dict, Any, List, Union

def _python_type_to_json_type(py_type: Any) -> str:
    """Maps Python types to JSON Schema types."""
    # Handle Optional[X] / Union[X, None]
    origin = getattr(py_type, "__origin__", None)
    args = getattr(py_type, "__args__", [])
    
    if origin is Union and type(None) in args:
        py_type = args[0]
        origin = getattr(py_type, "__origin__", None)
        
    if py_type == str: return "string"
    if py_type == int: return "integer"
    if py_type == float: return "number"
    if py_type == bool: return "boolean"
    if py_type == list or origin in (list, List): return "array"
    if py_type == dict or origin in (dict, Dict): return "object"
    return "string"  # Default fallback

def generate_tool_schema(func: Callable) -> Dict[str, Any]:
    """Generates an OpenAI/Ollama compatible tool schema from a Python function."""
    sig = inspect.signature(func)
    doc = inspect.getdoc(func) or ""
    
    # 1. Extract the main description (everything before "Args:")
    description = doc.split("Args:")[0].strip().replace('\n', ' ')
    if not description:
        description = f"Executes the {func.__name__} function."
    
    # 2. Extract parameter descriptions from the "Args:" section
    param_desc = {}
    if "Args:" in doc:
        args_section = doc.split("Args:")[1].split("Returns:")[0]
        # Match pattern: param_name: description
        matches = re.findall(r"(\w+):\s*(.*?)(?=\n\s*\w+:|\Z)", args_section, re.DOTALL)
        for name, desc in matches:
            param_desc[name] = desc.strip().replace('\n', ' ')
            
    # 3. Build the properties dictionary and required list
    properties = {}
    required = []
    
    for name, param in sig.parameters.items():
        if name == "self":
            continue
            
        param_type = "string"
        if param.annotation != inspect.Parameter.empty:
            param_type = _python_type_to_json_type(param.annotation)
            
        properties[name] = {
            "type": param_type,
            "description": param_desc.get(name, "")
        }
        
        # If parameter has no default value, it is required
        if param.default == inspect.Parameter.empty:
            required.append(name)
            
    # 4. Construct the final schema dictionary
    return {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }
    }

def get_schemas_from_registry(tool_registry: Dict[str, Callable]) -> List[Dict[str, Any]]:
    """Generates a list of schemas for all tools in a registry."""
    return [generate_tool_schema(func) for func in tool_registry.values()]
