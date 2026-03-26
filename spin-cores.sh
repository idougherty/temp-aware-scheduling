#!/bin/bash

stress() {
	echo "Spawning core spinnners..."

	# stress GPU
	./clpeak/clpeak -p 0 -d 0 --compute-sp --iters 999999 &

	# stress CPU compute
	stress-ng --cpu 8 &

	# stress NPU
	./rknn-toolkit2/rknpu2/examples/rknn_benchmark/rknn_benchmark ./rknn-toolkit2/rknpu2/examples/rknn_yolov5_demo/model/RK3588/yolov5s-640-640.rknn "" 9999999 7 > /dev/null &
}

unstress() {
	echo "Killing core spinners..."

	pkill clpeak
	pkill stress-ng
	pkill rknn_benchmark
}

cleanup() {
	unstress
	exit 1
}

trap cleanup INT

echo "Spawning temp monitor..."

./thermal_logger.py &

sleep 10

for i in {1..10};
do
	stress
	sleep 5
	unstress
	sleep 5
done

sleep 60

echo "Killing temp monitor..."

pkill -f thermal_logger

echo "DONE!"
