import os
import re

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    changed = False
    for i, line in enumerate(lines):
        if '.execute()' in line and 'lambda:' not in line and 'async_db' not in line:
            # We need to wrap the expression that calls .execute()
            # For simplicity, we can just replace `.execute()` with a wrapper around the whole statement?
            # No, if it's `res = query.execute()`, we want `res = await async_db(lambda: query.execute())`
            # Let's match `[something].execute()`
            # A simple way: find the variable/expression before `.execute()`
            # For example: `return query.execute()` -> `return await async_db(lambda: query.execute())`
            # `res = self.client.table("x").execute()` -> `res = await async_db(lambda: self.client.table("x").execute())`
            
            # Find where the statement starts. 
            # We can use regex to find the `x.execute()` part.
            # Actually, let's just do a manual replacement for common patterns.
            
            # Find the start of the method chain or variable
            # e.g., `query.execute()`, `q.execute()`, `self.client.table(...).execute()`
            
            # Since formatting varies, let's just do a regex that captures everything from the first non-space character
            # up to `.execute()`, except if it's `return ` or `res = `
            
            stripped = line.lstrip()
            indent = line[:len(line) - len(stripped)]
            
            if stripped.startswith("return "):
                expr = stripped[7:].strip()
                new_line = f"{indent}return await async_db(lambda: {expr})\n"
            elif "=" in stripped:
                parts = stripped.split("=", 1)
                lhs = parts[0].strip()
                rhs = parts[1].strip()
                if rhs.endswith(".execute()"):
                    new_line = f"{indent}{lhs} = await async_db(lambda: {rhs})\n"
                else:
                    new_line = line
            elif stripped.endswith(".execute()"):
                new_line = f"{indent}await async_db(lambda: {stripped})\n"
            else:
                new_line = line
                
            if new_line != line:
                # Also ensure async_db is imported
                lines[i] = new_line
                changed = True

    if changed:
        # Check imports
        content = "".join(lines)
        if "from db.client import get_supabase_client" in content and "async_db" not in content:
            content = content.replace("from db.client import get_supabase_client", "from db.client import get_supabase_client, async_db")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed {filepath}")

base_dir = r"d:\LuminaIQ\backend\services"
for f in os.listdir(base_dir):
    if f.endswith(".py"):
        fix_file(os.path.join(base_dir, f))
