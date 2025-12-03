import json
from collections import Counter, defaultdict
import re
from datetime import datetime

def analyze_logs(file_path):
    print(f"Analyzing {file_path}...")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError:
        print("File is not a valid JSON array. Trying line-by-line JSON (NDJSON)...")
        with open(file_path, 'r', encoding='utf-8') as f:
            data = []
            for line in f:
                if line.strip():
                    try:
                        data.append(json.loads(line))
                    except:
                        pass

    print(f"Total log entries: {len(data)}")

    # Counters
    levels = Counter()
    errors = Counter()
    warnings = Counter()
    health_checks = []
    timeouts = []
    patterns = []
    chunk_metrics = []
    
    # Regex for cleaner aggregation
    error_cleaner = re.compile(r'(url=https?://[^ ]+|request_id=[^ ]+|chunk: \d+ chars)')

    for entry in data:
        # Normalize fields
        msg = entry.get('message', '')
        attrs = entry.get('attributes', {})
        level = attrs.get('level', 'UNKNOWN').upper()
        if not level or level == 'UNKNOWN':
             # Try to infer from message if level attribute is missing
             if '[ERROR]' in msg or '❌' in msg: level = 'ERROR'
             elif '[WARNING]' in msg or '⚠️' in msg: level = 'WARNING'
             elif '[INFO]' in msg or '✅' in msg: level = 'INFO'

        levels[level] += 1

        # Health Checks
        if '[HEALTH_CHECK]' in msg:
            health_checks.append(msg)

        # Timeouts
        if '[LLM_TIMEOUT]' in msg or 'Request timed out' in msg:
            timeouts.append(msg)
            
        # Patterns
        if '[PATTERN_DETECTED]' in msg:
            patterns.append(msg)
            
        # Chunk Metrics
        if '[CHUNK_METRICS]' in msg:
            chunk_metrics.append(msg)

        # Errors & Warnings Aggregation
        if level == 'ERROR':
            clean_msg = error_cleaner.sub('...', msg)
            errors[clean_msg] += 1
        elif level == 'WARNING':
            clean_msg = error_cleaner.sub('...', msg)
            warnings[clean_msg] += 1

    print("\n" + "="*50)
    print("📊 LOG LEVEL DISTRIBUTION")
    print("="*50)
    for l, c in levels.most_common():
        print(f"{l}: {c}")

    print("\n" + "="*50)
    print("🚨 TOP 10 ERRORS")
    print("="*50)
    for msg, count in errors.most_common(10):
        print(f"[{count}] {msg}")

    print("\n" + "="*50)
    print("⚠️ TOP 10 WARNINGS")
    print("="*50)
    for msg, count in warnings.most_common(10):
        print(f"[{count}] {msg}")

    print("\n" + "="*50)
    print("🏥 HEALTH CHECK REPORT")
    print("="*50)
    if health_checks:
        # Show first, middle and last health checks to see progression
        samples = [health_checks[0]]
        if len(health_checks) > 1:
            samples.append(health_checks[len(health_checks)//2])
        if len(health_checks) > 2:
            samples.append(health_checks[-1])
            
        print(f"Total Health Checks: {len(health_checks)}")
        print("\n--- Samples ---")
        for h in samples:
            print(h)
    else:
        print("No Health Checks found.")

    print("\n" + "="*50)
    print("⏰ TIMEOUT ANALYSIS")
    print("="*50)
    print(f"Total Timeouts: {len(timeouts)}")
    if timeouts:
        print("\n--- Recent Timeouts ---")
        for t in timeouts[-5:]:
            print(t)

    print("\n" + "="*50)
    print("📉 PATTERN DETECTION")
    print("="*50)
    if patterns:
        for p in patterns:
            print(p)
    else:
        print("No problematic patterns detected by the system.")

if __name__ == "__main__":
    analyze_logs("logs.1764794329321.json")

