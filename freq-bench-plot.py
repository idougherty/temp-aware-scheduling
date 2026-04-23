#!/bin/python3
import pandas as pd
import matplotlib.pyplot as plt
import sys
import os
import re

def normalize_mhz(val):
    # Ensure value is a string and handle casing/whitespace
    val = str(val).strip().lower()
    
    # Extract the numeric part and the unit part
    match = re.match(r"([0-9.]+)\s*([a-z]*)", val)
    if not match:
        return None
        
    number = float(match.group(1))
    unit = match.group(2)
    
    # Multiply by 1000 if GHz, otherwise keep as is for MHz
    if 'g' in unit:
        return int(number * 1000)
    else:
        return int(number)

def plot_slowdown(column_name, csv_files):
    # Set up a square plot
    fig, ax = plt.subplots(figsize=(5, 5))
    
    for file in csv_files:
        if not os.path.exists(file):
            continue
            
        df = pd.read_csv(file)
        
        # 1. Clean X-axis: Remove 'GHz' and 'MHz' from labels
        # df['freq_clean'] = pd.to_numeric(df['freq'].str.replace('GHz', '', case=False).str.replace('MHz', '', case=False))
        df['freq_clean'] = df['freq'].apply(normalize_mhz)
        
        # 2. Calculate Slowdown:
        # We assume the last row (or highest freq) is the baseline (min time).
        # Slowdown = Current Time / Minimum Time
        baseline_value = df[column_name].iloc[-1]
        df['slowdown'] = df[column_name] / baseline_value
        
        label = os.path.basename(file).replace('.csv', '')
        ax.plot(df['freq_clean'], df['slowdown'], marker='s', linewidth=2, label=label)
        ax.set_xticks(df['freq_clean'])

    # Styling
    ax.set_title(f'P99 Slowdown vs Frequency', fontsize=14, fontweight='bold')
    ax.set_xlabel('Frequency (MHz)', fontsize=12)
    ax.set_ylabel('Slowdown', fontsize=12)
    
    # Force square aspect ratio
    ax.set_box_aspect(1) 
    
    ax.grid(True, linestyle=':', alpha=0.6)
    ax.legend()
    
    plt.tight_layout()
    plt.savefig("fig.png", dpi=150)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python script.py <column_name> <file1.csv> <file2.csv> ...")
        sys.exit(1)

    target_metric = sys.argv[1]
    files = sys.argv[2:]
    
    plot_slowdown(target_metric, files)
