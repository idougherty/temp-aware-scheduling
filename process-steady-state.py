#!/bin/python3
import os
import pandas as pd
import sys

def normalize_to_mhz(freq_str):
    freq_str = freq_str.lower()
    if 'ghz' in freq_str:
        return int(float(freq_str.replace('ghz', '')) * 1000)
    if 'mhz' in freq_str:
        return int(float(freq_str.replace('mhz', '')))
    # Assume raw Hz if just an integer
    return int(int(freq_str) / 1000000)

def process_benchmark(bench_dir):
    results = []
    bench_name = os.path.basename(bench_dir.strip('/'))

    for subdir in os.listdir(bench_dir):
        if not subdir.startswith("data-freq-"):
            continue
            
        # Extract freq string: data-freq-[bench]-[freq]
        # We split from the right to handle bench names with hyphens
        freq_raw = subdir.split('-')[-1]
        mhz = normalize_to_mhz(freq_raw)
        
        csv_path = os.path.join(bench_dir, subdir, "soc-thermal.csv")
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            
            # Filter for last 50s (50,000 ms)
            max_time = df['timestamp_ms'].max()
            last_50s = df[df['timestamp_ms'] >= (max_time - 50000)]
            avg_temp = last_50s['temp_celsius'].mean()

            T_amb = 22
            R_coupling = 1.208
            R_amb = 1.875
            Q_base = 2.546

            # estimate power usage
            power = (avg_temp - T_amb) / (R_coupling + R_amb) - 2.546
            
            results.append({'freq': mhz, 'avg_temp': avg_temp, 'power': power})

    # Sort by frequency and save
    out_df = pd.DataFrame(results).sort_values('freq')
    out_df.to_csv(f"{bench_name}.csv", index=False)
    print(f"Generated {bench_name}.csv")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python script.py <benchmark_directory>")
    else:
        process_benchmark(sys.argv[1])
