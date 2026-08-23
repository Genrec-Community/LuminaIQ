import re
with open('index.js', 'r', encoding='utf-16') as f:
    content = f.read()

urls = re.findall(r'https?://[a-zA-Z0-9\-\.]+(?:\:[0-9]+)?(?:/[a-zA-Z0-9\-\.\_\~]+)*', content)
unique_urls = set(urls)
for url in unique_urls:
    if 'w3.org' not in url and 'google' not in url and 'react' not in url and 'github' not in url and 'supabase' not in url:
        print(url)
