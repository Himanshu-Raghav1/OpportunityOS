import sys
import logging
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
print("Starting hunter test...", flush=True)

from agents.agent_02_hunter import run_hunter
print("Imported run_hunter. Running now...", flush=True)

try:
    res = run_hunter({'scan_id':'test-123'})
    print(f"Found {len(res['raw_opportunities'])} opportunities", flush=True)
    for msg in res['progress_messages']:
        print(msg)
except Exception as e:
    print(f"Error: {e}")
