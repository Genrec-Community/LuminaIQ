import os
import re

def fix_imports(content):
    if "from db.client import get_supabase_client" in content and "async_db" not in content:
        content = content.replace("from db.client import get_supabase_client", "from db.client import get_supabase_client, async_db")
    return content

def fix_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    original_content = content
    content = fix_imports(content)

    # Basic strategy: find self.client.table(...)...execute() 
    # and wrap it in await async_db(lambda: ...)
    
    # We can use a regex that looks for `self.client.table` up to `.execute()`
    # but we have to be careful about newlines and unbalanced parentheses.
    # Actually, a simpler approach is to search for instances and just replace them manually or via careful regex.
    # The regex approach: find `self\.client\.table\([^)]+\)[\s\S]*?\.execute\(\)`
    # This might match too much if there are multiple. We can use a non-greedy match.
    
    matches = re.finditer(r'(self\.client\.table\([^\)]+\)(?:(?!\bself\.).)*?\.execute\(\))', content, re.DOTALL)
    
    replacements = []
    for match in matches:
        text = match.group(1)
        # Check if it's already wrapped in async_db
        # We look around the match in the original text
        idx = match.start()
        prefix = content[max(0, idx-20):idx]
        if "lambda:" not in prefix:
            replacements.append((text, f"await async_db(lambda: {text})"))

    for old, new in replacements:
        content = content.replace(old, new)
        
    if content != original_content:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"Fixed {filepath} ({len(replacements)} replacements)")
    else:
        print(f"No changes needed in {filepath}")

if __name__ == "__main__":
    base_dir = r"d:\Projects\luminaworking\backend\services"
    files = [
        "mcq_service.py",
        "knowledge_graph_service.py"
    ]
    for filename in files:
        fix_file(os.path.join(base_dir, filename))
