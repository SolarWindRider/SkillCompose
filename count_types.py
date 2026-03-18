import json
from collections import Counter

with open('datasets/attack_samples.jsonl') as f:
    types = [json.loads(line)['attack_type'] for line in f]

print('Total:', len(types))
print('By type:', Counter(types))
