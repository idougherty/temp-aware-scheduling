#!/bin/bash

FREQS=("408MHz" "600MHz" "816MHz" "1GHz" "1.20GHz" "1.42GHz" "1.61GHz" "1.80GHz" "2.02GHz" "2.21GHz" "2.30GHz")

#BENCH=./rt-tacle-bench/bench/sequential/h264_dec/h264_dec
#BENCH=./rt-tacle-bench/bench/kernel/fir2dim/fir2dim
#

BINARY=$1
PARAMS="${@:2}"
RUNS=10
LOG_FILE="timing.csv"

run_benchmark() {
    # -l 2: CSV log, -t: number of iterations, -p: period (back-to-back if omitted)
    "$BINARY" -c 7 -p 1 -d 1 -l 2 -o "$LOG_FILE" -t "$RUNS" $PARAMS
}

calculate_stats() {
    times=($(awk -F, 'NR>1 {print $5}' "$LOG_FILE" | sort -n))
    count=${#times[@]}

    get_val() {
        idx=$(echo "($1 * $count / 100) - 1" | bc)
        echo "${times[${idx%.*} < 0 ? 0 : ${idx%.*}]}"
    }

    sum=$(IFS=+; echo "$(("${times[*]}"))")
    mean=$(echo "scale=2; $sum / $count" | bc)

    echo "--- Internal Metrics for $BINARY ---"
    echo "Mean:   $mean us"
    echo "P0:     $(get_val 0) us"
    echo "Median: $(get_val 50) us"
    echo "P90:    $(get_val 90) us"
    echo "P99:    $(get_val 99) us"
    echo "P100:   $(get_val 100) us"
    
    echo $freq,$mean,$(get_val 50),$(get_val 90),$(get_val 99),$(get_val 100) >> "$bench_name.csv"
}

bench_name=$(basename "$BINARY")
#echo freq,mean,p50,p90,p99,p100 > "$bench_name.csv"
for freq in "${FREQS[@]}"; do
	echo "executing $bench_name @ $freq..."
	sudo cpupower -c all frequency-set -f $freq
	run_benchmark

	calculate_stats
done
