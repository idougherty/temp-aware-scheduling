# Temperature Aware Scheduling

This is a collection of scripts and data used for Ian's Temperature Aware Scheduling course project for RTOS.
The project was in many ways an exploratory data science project, motivating systems optimizations through empirical testing on the Rockchip Orange PI 5.

I apologize for the not-so-organized nature of this repository, as structure was largely abandoned for the sake of rapid iteration. Unfortunately, logic is duplicated in many places due to a "copy the whole thing and rewrite just the part I need to change" strategy. Disclaimers aside, here is an overview of the project.

## Subrepos

rt-bench: A collection of real-time scheduling benchmarks.

clpeak: A utility for stressing GPUs to determine peak compute capabilities.

rknn-toolkit2: A collection of benchmarks for the proprietary Rockchip NPU.

## Scripts

thermal\_logger.py: A monitoring script that samples the temperature of all thermal zones every 100ms. Writes to an output directory to [zone\_name]-thermal.csv files.

spin\_cores.sh: A multipurposed shell script that runs thermal stress tests on the platform. Takes care of launching the thermal logger and cleaning up. Uses stress-ng and taskset for CPU core stressing. Can execute an example schedule provided as a csv with core\_id, task\_arrival, and execution\_length.

plot.py: A multipurpose plotting script. Takes in thermal logging data and plots it over time, optionally smoothing it with EMA. Can optionally draw gantt charts for a given schedule csv or plot the core frequency alongside temperature.

calibrate.py: Python script that fits thermal model parameters to empirical test data. A set of cleaned test data is available in data-calibration-clean, which is trimmed to remove long cooling trails that might throw off fits. The script uses sci-py's dual annealing optimization function to fit parameters and spits the results to stdout.

simulate.py: Takes in parameters from calibration as command line arguments and plots a simulation pass, can take empirical results to overlay on the plot. Resulting figure is written to fig.png.

freq-temp.sh: Executes a target workload at multiple core frequencies, using the thermal logger to gather temperature data. Used to determine steady state temperatures to back out thermal power data.

process-steady-state.py: Read results from freq-temp.sh thermal logging, trim the observed data to the last 50s (just the steady state) and find average temperature. This steady state temperature is fed through equation 6 from the paper to back out thermal power for the task. Produces a csv of frequency, avg\_temp, thermal\_power.

freq-power-plot.py: Takes resulting csvs from process-steady-state.py as commandline parameters and creates a plot of thermal power vs frequency for each benchmark.

freq-bench.sh: Executes a target workload at multiple core frequencies and outputs csv of execution time statistics: freq,mean,P50,P90,P99,max

freq-bench-plot.py: Takes resulting csvs from freq-bench.sh and produces plot of P99 slowdown vs core frequency for each benchmark. 

