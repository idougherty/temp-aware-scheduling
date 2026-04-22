#!/bin/bash

#bench=./rt-bench/IsolBench/bandwidth
#params="-c 7 -p 0.000001 -d 0.000001"

#bench=./rt-bench/rt-tacle-bench/bench/kernel/sha/sha
#params="-c 7 -p 0.000001 -d 0.000001"

#bench=./rt-bench/vision/benchmarks/mser/data/fullhd/mser
#params=-"c 7 -p 0.000001 -d 0.000001 -b ./rt-bench/vision/benchmarks/mser/data/fullhd"

#bench=./clpeak/clpeak
#params="-p 0 -d 0 --compute-sp --iters 999999"
#device=fb000000.gpu

bench=./rknn-toolkit2/rknpu2/examples/rknn_benchmark/rknn_benchmark
params='./rknn-toolkit2/rknpu2/examples/rknn_yolov5_demo/model/RK3588/yolov5s-640-640.rknn "" 9999999 7'
device=fdab0000.npu

bench_name=$(basename "$bench")

cleanup() {
	pkill -f thermal_logger
	pkill -f $bench
	exit 1
}
trap cleanup INT


#FREQS=("408MHz" "816MHz" "1.20GHz" "1.61GHz" "1.80GHz" "2.02GHz" "2.30GHz")
#FREQS=(300000000 400000000 500000000 600000000 700000000 800000000 900000000 1000000000)
FREQS=(800000000 900000000 1000000000)

for freq in "${FREQS[@]}"; do
	sleep 1

	echo "Executing $bench_name @ $freq..."
	#sudo cpupower -c all frequency-set -f $freq
	echo $freq | sudo tee /sys/devices/platform/$device/devfreq/$device/userspace/set_freq

	echo "Spawning temp monitor..."
	DATA_DIR="./data-freq-$bench_name-$freq"
	./thermal_logger.py -o "$DATA_DIR" &

	sleep 1

	echo "Starting benchmark $bench_name!"
	eval "$bench $params" > /dev/null &

	sleep 600

	echo "killing benchmarks"

	pkill -f $bench

	echo "Killing temp monitor..."
	pkill -f thermal_logger
done

echo "DONE!"
