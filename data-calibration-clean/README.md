# Tests to run

ambient (32)

1. get alpha from opp table
test frequenzies: 408Mhz and 1800Mhz

voltage low: 675000
voltage high: 825000 (big cores), 937500 (little cores)

alpha = (1800 * Vhigh^2) / (408 * Vlow^2)
alpha = 6.59 or 3.42

2. find Qlow and Rtotal (if we have Qlow and alpha we can get any Q)
steady state at 408Mhz  get low freq steady temp
steady state at 1800Mhz get high freq steady temp

use steady temps to derive Qlow and Rtotal

3. find tau1
short pulse at 1800Mhz  fit single exp to curve, get tau1

4. find tau2
long cooling tail after 1800Mhz load    fit single exp to curve, get tau2

5. fit beta
fit against all test data using optimization over an ODE prediction

