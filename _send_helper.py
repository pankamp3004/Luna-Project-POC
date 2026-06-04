import sys, os, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv; load_dotenv()
from gmail_client import send_reply
d = json.loads(sys.stdin.read())
ok = send_reply(d["to_addr"], d["subject"], d["body"])
sys.exit(0 if ok else 1)
