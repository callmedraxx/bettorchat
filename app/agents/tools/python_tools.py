"""
Python REPL tool for data extraction and filtering from betting tool results.
Improved version with better error handling, security, and functionality.
"""
import io
import sys
import logging
import traceback
from typing import Any, Dict, Optional
from contextlib import redirect_stdout, redirect_stderr
from langchain.tools import tool

logger = logging.getLogger(__name__)


class PythonREPL:
    """A Python REPL for executing Python code safely."""
    
    def __init__(self):
        self.globals = {
            '__builtins__': __builtins__,
            'json': __import__('json'),
            're': __import__('re'),
            'datetime': __import__('datetime'),
            'collections': __import__('collections'),
        }
        # Add common data processing modules
        try:
            self.globals['pandas'] = __import__('pandas')
        except ImportError:
            pass
        
        # Add database helper function for fetching large tool results
        def get_tool_result_from_db(tool_call_id: str) -> Optional[str]:
            """
            Fetch a large tool result from the database by tool_call_id.
            
            This function retrieves full tool results that were stored in the database
            when tools like fetch_live_odds returned large results that were truncated.
            
            Args:
                tool_call_id: The tool_call_id from the truncated message (e.g., 'toolu_01XXXXX')
            
            Returns:
                The full tool result as a string, or None if not found
            
            Example:
                # When you see a truncated message like:
                # "Tool result too large, the result was saved at /large_tool_results/toolu_01XXXXX"
                # Extract the tool_call_id and use this function:
                result = get_tool_result_from_db('toolu_01XXXXX')
                if result:
                    data = json.loads(result)
                    # Process the data...
            """
            try:
                from app.core.tool_result_db import get_tool_result_from_db as db_get
                return db_get(tool_call_id)
            except Exception as e:
                logger.error(f"[PythonREPL] Error fetching tool result from database: {e}", exc_info=True)
                return None
        
        self.globals['get_tool_result_from_db'] = get_tool_result_from_db
        
    def run(self, command: str) -> str:
        """Execute Python code and return the output.
        
        Supports both statements (exec) and expressions (eval).
        If the command is a single expression, it will be evaluated and the result returned.
        
        Args:
            command: Python code to execute (can be statement or expression)
            
        Returns:
            Output from executing the code, or error message
        """
        if not command or not command.strip():
            return "Error: Empty command provided."
        
        # Capture stdout and stderr
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        # Maximum output size to prevent issues with large tool results (500KB)
        MAX_OUTPUT_SIZE = 500 * 1024
        
        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                # Try to determine if it's an expression or statement
                # First, try to compile as expression (eval mode)
                is_expression = False
                result_value = None
                
                try:
                    # Try compiling as expression first
                    code_obj = compile(command.strip(), '<string>', 'eval')
                    is_expression = True
                except SyntaxError:
                    # Not an expression, try as statement
                    try:
                        code_obj = compile(command, '<string>', 'exec')
                        is_expression = False
                    except SyntaxError as e:
                        # Syntax error in both modes
                        return f"Syntax Error: {str(e)}\nLine {e.lineno if hasattr(e, 'lineno') else '?'}: {getattr(e, 'text', 'N/A')}"
                
                # Execute the code
                try:
                    if is_expression:
                        # Evaluate expression and capture result
                        result_value = eval(code_obj, self.globals)
                    else:
                        # Execute statement
                        exec(code_obj, self.globals)
                except Exception as e:
                    # Get full traceback for better error messages
                    exc_type = type(e).__name__
                    exc_msg = str(e)
                    tb_str = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
                    
                    # Return concise but informative error
                    error_msg = f"Error: {exc_msg}\nType: {exc_type}"
                    # Include traceback if it's not too long
                    if len(tb_str) < 2000:
                        error_msg += f"\n\nTraceback:\n{tb_str}"
                    
                    return error_msg
            
            # Get output
            stdout_output = stdout_capture.getvalue()
            stderr_output = stderr_capture.getvalue()
            
            # Handle stderr output
            if stderr_output:
                output = f"Warning/Error output:\n{stderr_output}"
                if stdout_output:
                    output += f"\n\nStandard output:\n{stdout_output}"
                # Truncate if too large
                if len(output) > MAX_OUTPUT_SIZE:
                    truncated_size = len(output) - MAX_OUTPUT_SIZE
                    output = output[:MAX_OUTPUT_SIZE] + f"\n\n[Output truncated: {truncated_size} characters removed. Consider filtering or summarizing the data.]"
                return output
            
            # Handle expression result
            if is_expression and result_value is not None:
                # Format the result nicely
                try:
                    import json
                    # Try to serialize as JSON if possible
                    if isinstance(result_value, (dict, list, str, int, float, bool, type(None))):
                        result_str = json.dumps(result_value, indent=2, default=str)
                    else:
                        result_str = repr(result_value)
                except Exception:
                    result_str = repr(result_value)
                
                # Combine with stdout if any
                if stdout_output:
                    return f"{stdout_output}\n\nResult: {result_str}"
                return result_str
            
            # Handle stdout output
            if stdout_output:
                # Truncate if too large
                if len(stdout_output) > MAX_OUTPUT_SIZE:
                    truncated_size = len(stdout_output) - MAX_OUTPUT_SIZE
                    stdout_output = stdout_output[:MAX_OUTPUT_SIZE] + f"\n\n[Output truncated: {truncated_size} characters removed. Consider filtering or summarizing the data.]"
                return stdout_output
            
            # If no output but no error, the code executed successfully
            return "Code executed successfully (no output)."
            
        except Exception as e:
            # Catch-all for unexpected errors
            error_msg = f"Unexpected error: {str(e)}\nType: {type(e).__name__}"
            logger.error(f"[PythonREPL] Unexpected error: {e}", exc_info=True)
            return error_msg


# Create a global REPL instance
_repl = PythonREPL()


@tool
def python_repl(command: str, data: Optional[str] = None) -> str:
    """Execute Python code for data extraction, filtering, sorting, and processing.
    
    This tool is IDEAL for processing large tool results quickly and efficiently.
    Use this tool instead of read_file when you need to:
    - Sort large datasets (much faster than read_file)
    - Filter and extract specific data from large results
    - Transform or aggregate data
    - Perform calculations on betting data
    - Fetch large tool results from the database (instead of filesystem)
    - Evaluate expressions and get return values
    
    The code runs in a safe environment with access to common Python libraries
    like json, re, datetime, and collections. If pandas is available, it will
    also be accessible.
    
    IMPORTANT: 
    - You can use print() to display results OR return values from expressions
    - Single expressions (like "2 + 2" or "len(data)") will automatically return their result
    - Statements (like "x = 5" or "for item in data: print(item)") use print() for output
    - The 'data' parameter can contain JSON strings or other data to process
    - Variables persist across multiple calls in the same session
    - When you see a truncated tool result message mentioning "/large_tool_results/toolu_XXXXX",
      use get_tool_result_from_db('toolu_XXXXX') to fetch the full result from the database
      instead of using read_file on the filesystem (which may not be accessible)
    - For large results from fetch_live_odds or fetch_upcoming_games, use this tool to:
      * Sort by any field (date, team, odds, etc.)
      * Filter by conditions (specific teams, date ranges, etc.)
      * Extract specific fields quickly
      * Aggregate data (counts, averages, etc.)
    
    Examples:
        # Simple expression (automatically returns result)
        python_repl(command="2 + 2")  # Returns: 4
        python_repl(command="len([1, 2, 3])")  # Returns: 3
        
        # Extract specific fields from a JSON result
        python_repl(
            command='''
import json
result = json.loads(data)
for game in result.get("games", []):
    print(f"{game.get('home_team')} vs {game.get('away_team')}")
            ''',
            data='{"games": [{"home_team": "Lakers", "away_team": "Warriors"}]}'
        )
        
        # Filter results (expression returns value)
        python_repl(
            command='''
import json
result = json.loads(data)
json.dumps([g for g in result.get("games", []) if g.get("sport") == "NBA"], indent=2)
            ''',
            data='{"games": [...]}'
        )
        
        # Fetch large tool result from database and sort/filter it (when tool result was truncated)
        python_repl(
            command='''
import json
# Extract tool_call_id from truncated message (e.g., 'toolu_01XXXXX')
tool_call_id = 'toolu_01XXXXX'  # Replace with actual tool_call_id from the message
full_result = get_tool_result_from_db(tool_call_id)
if full_result:
    # Process the full result - much faster than read_file!
    # For fetch_live_odds results, you can sort by odds, filter by team, etc.
    # For fetch_upcoming_games results, you can sort by date, filter by league, etc.
    data = json.loads(full_result)
    # Example: Sort upcoming games by date
    # games = sorted(data.get('games', []), key=lambda x: x.get('start_time', ''))
    # Example: Filter odds by specific team
    # filtered_odds = [o for o in data.get('odds', []) if 'Lakers' in str(o)]
    print(f"Retrieved {len(full_result)} characters of data")
else:
    print("Tool result not found in database")
            '''
        )
        
        # Sort large dataset quickly (much faster than read_file)
        python_repl(
            command='''
import json
# Sort fixtures by date
fixtures = json.loads(data)
sorted_fixtures = sorted(fixtures, key=lambda x: x.get('start_time', ''))
print(json.dumps(sorted_fixtures[:10], indent=2))  # Show first 10
            ''',
            data='[{"start_time": "2024-12-01", ...}, ...]'
        )
    
    Args:
        command: Python code to execute. Use print() to output results.
        data: Optional JSON string or data to process. Access it via the 'data' variable.
    
    Returns:
        Output from executing the Python code, or error message if execution fails.
    """
    try:
        # If data is provided, make it available in the REPL
        if data:
            try:
                import json
                # Try to parse as JSON
                parsed_data = json.loads(data)
                _repl.globals['data'] = parsed_data
                _repl.globals['raw_data'] = data
            except (json.JSONDecodeError, ValueError):
                # If not JSON, store as string
                _repl.globals['data'] = data
                _repl.globals['raw_data'] = data
        else:
            # Clear data if not provided
            _repl.globals.pop('data', None)
            _repl.globals.pop('raw_data', None)
        
        # Execute the command
        result = _repl.run(command)
        
        # Ensure result is a string and handle any edge cases
        if not isinstance(result, str):
            result = str(result)
        
        # Additional safety check for very large outputs
        MAX_RESULT_SIZE = 500 * 1024  # 500KB
        if len(result) > MAX_RESULT_SIZE:
            truncated = result[:MAX_RESULT_SIZE]
            result = truncated + f"\n\n[Output truncated: {len(result) - MAX_RESULT_SIZE} characters removed. Consider filtering or summarizing the data to reduce output size.]"
        
        return result
        
    except Exception as e:
        return f"Error setting up Python REPL: {str(e)}\nType: {type(e).__name__}"

