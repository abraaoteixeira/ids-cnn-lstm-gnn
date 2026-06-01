import json, collections

data = [json.loads(l) for l in open('/mnt/c/Users/abraa/Documents/ids-cnn-lstm-gnn/data/honeypot_real_attacks.jsonl')]
print(f'Total eventos: {len(data)}')

# Top IPs
ips = collections.Counter(d['src_ip'] for d in data)
print('\nTop 10 IPs:')
for ip, n in ips.most_common(10): print(f'  {ip}: {n}')

# Top portas
ports = collections.Counter(d['port'] for d in data)
print('\nTop 10 Portas:')
for p, n in ports.most_common(10): print(f'  {p}: {n}')

# Top paises
countries = collections.Counter(d.get('country','?') for d in data)
print('\nTop Paises:')
for c, n in countries.most_common(10): print(f'  {c}: {n}')

# Top cidades
cities = collections.Counter(d.get('city','?') for d in data if d.get('city','?') not in ['Unknown','?'])
print('\nTop Cidades:')
for c, n in cities.most_common(10): print(f'  {c}: {n}')

# Periodo
dates = sorted(d['timestamp'][:10] for d in data)
print(f'\nPeriodo: {dates[0]} a {dates[-1]}')

# Probabilidades
probs = [d['probability'] for d in data]
print(f'\nProb media: {sum(probs)/len(probs):.3f}')
print(f'Prob > 0.8: {sum(1 for p in probs if p>0.8)}')
print(f'Prob > 0.5: {sum(1 for p in probs if p>0.5)}')

# IPs unicos
print(f'\nIPs unicos: {len(ips)}')
print(f'Paises unicos: {len(countries)}')
