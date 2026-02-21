import json
import re

html_script = """
<script nonce="cd96e4b0b8d9177a8c7429a1541a4b91">window.__reactRouterContext.streamController.enqueue("P12:[{\\\"_11444\\\":11445,\\\"_11446\\\":11447,\\\"_11453\\\":11454,\\\"_11456\\\":11457}]");</script>
"""

# Extract the big string payload from streamController.enqueue("...")
pattern = re.compile(r'streamController\.enqueue\((["\'])(.*?)\1\)', re.DOTALL)
match = pattern.search(html_script)
if match:
    payload_str = match.group(2)
    # The payload often starts with something like "P12:" or just an array/object.
    # It might be double-escaped JSON. Let's see if we can decode it.
    
    # Unescape the string to see what the raw JSON might look like
    try:
        # The regex match extracts the literal string contents. 
        # Python evaluates it as a raw string so we need to process escape sequences.
        decoded_payload = payload_str.encode().decode('unicode_escape')
        print(f"Decoded: {decoded_payload[:100]}...")
        
        # We need to strip off the Prefix like 'P12:' to get the JSON array/object
        json_start = re.search(r'[[{]', decoded_payload)
        if json_start:
            json_str = decoded_payload[json_start.start():]
            data = json.loads(json_str)
            print(f"Parsed JSON keys: {list(data.keys()) if isinstance(data, dict) else len(data)}")
    except Exception as e:
        print(f"Failed: {e}")
