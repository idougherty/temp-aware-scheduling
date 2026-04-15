#!/bin/bash

stress() {
	echo "Spawning core spinnners..."

	# stress GPU
	# ./clpeak/clpeak -p 0 -d 0 --compute-sp --iters 999999 > /dev/null &

	# stress CPU compute
	stress-ng --cpu 8 > /dev/null &

	# stress NPU
	# ./rknn-toolkit2/rknpu2/examples/rknn_benchmark/rknn_benchmark ./rknn-toolkit2/rknpu2/examples/rknn_yolov5_demo/model/RK3588/yolov5s-640-640.rknn "" 9999999 7 > /dev/null &
}

get_current_temp() {
	TEMP=$(sensors | grep soc -A 2 | grep -o1 "[0-9].\.[0-9]" | head -n 1)
	echo $TEMP
}

unstress() {
	echo "Killing core spinners..."

	# pkill clpeak
	pkill stress-ng
	# pkill rknn_benchmark
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

cleanup() {
	unstress
	exit 1
}

trap cleanup INT

DATA_DIR="data"

echo "Performing cooldown test, target temp=$TARGET_TEMP C"

echo "Spawning temp monitor..."

./thermal_logger.py -o $DATA_DIR &


sleep 5

pulse_for_length 5

#sleep 10

pulse_for_length 5

#sleep 10

pulse_for_length 5

#sleep 10

pulse_for_length 5

#sleep 10

pulse_for_length 5

#sleep 10

pulse_for_length 5

sleep 60

echo "Killing temp monitor..."

pkill -f thermal_logger

echo "DONE!"
