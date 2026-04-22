#!/bin/python3
import pandas as pd
import matplotlib.pyplot as plt
import sys
import os
import re

def plot_power(csv_files):
    # Set up a square plot
    fig, ax = plt.subplots(figsize=(5, 5))
    
    for idx, file in enumerate(csv_files):
        if not os.path.exists(file):
            continue
            
        df = pd.read_csv(file)
        
        label = os.path.basename(file).replace('.csv', '').split('-')[-1]
        ax.plot(df['freq'], df['power'], marker='s', linewidth=2, label=label)

        if(idx == 0):
            ax.set_xticks(df['freq'])

    # Styling
    ax.set_title(f'Thermal Power vs Frequency', fontsize=14, fontweight='bold')
    ax.set_xlabel('Frequency (MHz)', fontsize=12)
    ax.set_ylabel('Thermal Power (W)', fontsize=12)
    
    # Force square aspect ratio
    ax.set_box_aspect(1) 
    
    ax.grid(True, linestyle=':', alpha=0.6)
    ax.legend()
    
    plt.tight_layout()
    plt.savefig("fig.png", dpi=150)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python script.py <file1.csv> <file2.csv> ...")
        sys.exit(1)

    files = sys.argv[1:]
    
    plot_power(files)
