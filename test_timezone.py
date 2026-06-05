from datetime import datetime
from zoneinfo import ZoneInfo
import os
from dotenv import load_dotenv

load_dotenv()

tz = os.getenv('TIMEZONE', 'Asia/Kolkata')
now = datetime.now(ZoneInfo(tz))
start = int(os.getenv('SENDING_HOUR_START', '10'))
end = int(os.getenv('SENDING_HOUR_END', '19'))
within = start <= now.hour < end

print(f'Current time ({tz}): {now.strftime("%Y-%m-%d %H:%M:%S %Z")}')
print(f'Current hour: {now.hour}')
print(f'Business hours: {start}:00 - {end}:00')
print(f'Within business hours: {within}')

if within:
    print('\n✅ Currently WITHIN business hours - emails will be SENT')
else:
    print('\n❌ Currently OUTSIDE business hours - emails will be HELD')
