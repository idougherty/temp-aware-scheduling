#!/bin/bash

stress_core() {
	local CPU_ID=$1
	local DURATION=$2
	echo "[$(date +%T)] Stressing core $CPU_ID for ${DURATION}s..."
	taskset -c "$CPU_ID" stress-ng --cpu 1 --timeout "${DURATION}s" > /dev/null 2>&1 &
}

stress_all_cores() {
	local DURATION=$1
	echo "[$(date +%T)] Stressing all cores for ${DURATION}s..."
	#stress-ng --cpu 8 --timeout "${DURATION}s" > /dev/null 2>&1 &
	stress-ng --matrix 8 --matrix-ops 20000 --timeout 2s > /dev/null 2>&1 &
}

stress() {
	# stress CPU compute
	echo "Spawning core spinners..."
	stress-ng --cpu 8 > /dev/null &

	# stress GPU
	# ./clpeak/clpeak -p 0 -d 0 --compute-sp --iters 999999 > /dev/null &

	# stress NPU
	# ./rknn-toolkit2/rknpu2/examples/rknn_benchmark/rknn_benchmark ./rknn-toolkit2/rknpu2/examples/rknn_yolov5_demo/model/RK3588/yolov5s-640-640.rknn "" 9999999 7 > /dev/null &
}

get_current_temp() {
	TEMP=$(sensors | grep soc -A 2 | grep -o1 "[0-9].\.[0-9]" | head -n 1)
	echo $TEMP
}

unstress() {
	echo "Killing core spinners..."
	pkill stress-ng
}

pulse_to_target() {
	TARGET_TEMP=$1
	stress
	current_temp=$(get_current_temp)
	while [[ $(echo "$current_temp < $TARGET_TEMP" | bc -l) -eq 1 ]]; do
		sleep 0.1
		current_temp=$(get_current_temp)
		echo "Current temp: $current_temp"
	done
	echo "Target temperature reached!"
	unstress
	while [[ $(echo "$current_temp > 35" | bc -l) -eq 1 ]]; do
		sleep 1
		current_temp=$(get_current_temp)
		echo "Current temp: $current_temp"
	done
	echo "Core fully cooled!"
}

pulse_for_length() {
	PULSE_LENGTH=$1
	stress
	sleep $PULSE_LENGTH
	unstress
}

# Run tasks from a CSV file.
# CSV format (no header): cpu_id,request_arrival,task_length
# request_arrival is seconds from experiment start (float ok).
# task_length is duration in seconds (float ok).
run_csv_workload() {
	local CSV_FILE=$1

	if [[ ! -f "$CSV_FILE" ]]; then
		echo "ERROR: CSV file not found: $CSV_FILE"
		exit 1
	fi

	echo "Loading workload from: $CSV_FILE"

	local EXPERIMENT_START
	EXPERIMENT_START=$(date +%s%3N)   # ms since epoch

	# Read all tasks, skip blank lines and comment lines
	local tasks=()
	while IFS=',' read -r cpu_id arrival length; do
		# strip whitespace/CR
		cpu_id=$(echo "$cpu_id" | tr -d '[:space:]')
		arrival=$(echo "$arrival" | tr -d '[:space:]')
		length=$(echo "$length"  | tr -d '[:space:]')
		# skip header or empty rows
		[[ -z "$cpu_id" || "$cpu_id" == cpu_id ]] && continue
		tasks+=("$cpu_id,$arrival,$length")
	done < "$CSV_FILE"

	IFS=$'\n' tasks=($(printf '%s\n' "${tasks[@]}" | sort -t',' -k2 -n))
	unset IFS
	echo "Loaded ${#tasks[@]} task(s)."

	PIDS=()

	# Dispatch each task at the right wall-clock moment
	for task in "${tasks[@]}"; do
		IFS=',' read -r cpu_id arrival length <<< "$task"

		# Calculate how many ms to sleep until arrival
		local now
		now=$(date +%s%3N)
		local elapsed_ms=$(( now - EXPERIMENT_START ))
		local arrival_ms
		arrival_ms=$(echo "$arrival * 1000" | bc | cut -d. -f1)
		local wait_ms=$(( arrival_ms - elapsed_ms ))

		if (( wait_ms > 0 )); then
			local wait_sec
			wait_sec=$(echo "scale=3; $wait_ms / 1000" | bc)
			sleep "$wait_sec"
		fi

		# Fire and forget — each stress_core call backgrounds itself
		if (( $cpu_id < 0 )); then
			stress_all_cores "$length"
		else
			stress_core "$cpu_id" "$length"
		fi
		PIDS+=($!)
	done

	# Wait for all background stress-ng jobs to finish
	echo "All tasks dispatched — waiting for completion..."
	wait "${PIDS[@]}"
	echo "All tasks complete."
}

cleanup() {
	unstress
	exit 1
}
trap cleanup INT

# ── Main ──────────────────────────────────────────────────────────────────────

DATA_DIR="data"

CSV_FILE=$1
echo "CSV workload mode: $CSV_FILE"
echo "Spawning temp monitor..."
./thermal_logger.py -o "$DATA_DIR" &

sleep 5

run_csv_workload "$CSV_FILE"

sleep 10
echo "Killing temp monitor..."
pkill -f thermal_logger
echo "DONE!"
