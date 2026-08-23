import json
import os

with open('old_env.json') as f:
    env = json.load(f)

settings = []
for item in env:
    name = item.get('name')
    val = item.get('value')
    # skip some built-in vars if necessary, but az appsettings set overwrites
    if name and val is not None:
        val = val.replace('"', '\\"') # escape quotes
        settings.append(f'{name}="{val}"')

command = f'az webapp config appsettings set --name luminaiq-api-v2 --resource-group rg-tabble-prod-cin-01 --settings ' + ' '.join(settings)
with open('set_env.bat', 'w') as f:
    f.write(command)
