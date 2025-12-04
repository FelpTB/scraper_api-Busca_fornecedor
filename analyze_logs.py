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
    if len(data) > 0:
        print(f"First entry sample: {str(data[0])[:200]}")

    # Counters
    levels = Counter()
    errors = Counter()
    warnings = Counter()
    health_checks = []
    timeouts = []
    patterns = []
    chunk_metrics = []
    
    # Performance Metrics
    profile_processing_times = []
    model_inference_times = []
    e2e_times = []
    
    # Regex for cleaner aggregation
    error_cleaner = re.compile(r'(url=https?://[^ ]+|request_id=[^ ]+|chunk: \d+ chars)')
    
    # Regex for performance
    perf_total_regex = re.compile(r'step=analyze_content_total duration=([\d\.]+)s')
    perf_inference_regex = re.compile(r'step=model_inference .* duration=([\d\.]+)s')
    perf_e2e_regex = re.compile(r'analyze_company end .* total=([\d\.]+)s')

    for entry in data:
        # Normalize fields
        msg = entry.get('message', '')
        attrs = entry.get('attributes', {})
        
        # Level Logic
        level = attrs.get('level', 'UNKNOWN').upper()
        if not level or level == 'UNKNOWN':
             # Try to infer from message if level attribute is missing
             if '[ERROR]' in msg or '❌' in msg: level = 'ERROR'
             elif '[WARNING]' in msg or '⚠️' in msg: level = 'WARNING'
             elif '[INFO]' in msg or '✅' in msg: level = 'INFO'

        levels[level] += 1

        # Performance Extraction
        if '[PERF]' in msg:
            total_match = perf_total_regex.search(msg)
            if total_match:
                try:
                    profile_processing_times.append(float(total_match.group(1)))
                except ValueError:
                    pass
            
            inference_match = perf_inference_regex.search(msg)
            if inference_match:
                try:
                    model_inference_times.append(float(inference_match.group(1)))
                except ValueError:
                    pass
            
            e2e_match = perf_e2e_regex.search(msg)
            if e2e_match:
                try:
                    e2e_times.append(float(e2e_match.group(1)))
                except ValueError:
                    pass

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
        if level in ('ERROR', 'ERR'):
            clean_msg = error_cleaner.sub('...', msg)
            errors[clean_msg] += 1
        elif level in ('WARNING', 'WARN'):
            clean_msg = error_cleaner.sub('...', msg)
            warnings[clean_msg] += 1

    print("\n" + "="*50)
    print("⏱️ PERFORMANCE METRICS")
    print("="*50)
    
    if e2e_times:
        avg_e2e = sum(e2e_times) / len(e2e_times)
        max_e2e = max(e2e_times)
        print(f"End-to-End Processing (Scrape + LLM):")
        print(f"  Count: {len(e2e_times)}")
        print(f"  Average: {avg_e2e:.2f}s")
        print(f"  Max: {max_e2e:.2f}s")
    else:
        print("No end-to-end processing times found.")

    if profile_processing_times:
        avg_time = sum(profile_processing_times) / len(profile_processing_times)
        max_time = max(profile_processing_times)
        min_time = min(profile_processing_times)
        print(f"\nLLM Analysis Phase:")
        print(f"  Count: {len(profile_processing_times)}")
        print(f"  Average: {avg_time:.2f}s")
        print(f"  Min: {min_time:.2f}s")
        print(f"  Max: {max_time:.2f}s")
    else:
        print("No LLM analysis times found.")

    if model_inference_times:
        avg_inf = sum(model_inference_times) / len(model_inference_times)
        print(f"\nModel Inference (LLM only):")
        print(f"  Count: {len(model_inference_times)}")
        print(f"  Average: {avg_inf:.2f}s")
    else:
        print("\nNo model inference times found.")

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
    import sys
    file_path = sys.argv[1] if len(sys.argv) > 1 else "logs.1764795759440.json"
    analyze_logs(file_path)
