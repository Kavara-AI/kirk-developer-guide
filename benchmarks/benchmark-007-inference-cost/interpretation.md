# Interpretation

## The number that matters

**Joules per unit of output signal.** Not joules per call. The per-call figure flatters
whichever system does less work per call, and the two do different amounts.

## Four ways to get this wrong

**1. Reporting without an idle baseline.** `power/energy-pkg/` is system-wide across the
socket. On the reference machine, idle alone was ~193 W while the entire measured
workload added under 6 W. Report the raw workload figure and you have reported the idle
power of the machine, accurate to about 3%.

**2. Letting the delta sink into the noise.** If your attributable delta is a few percent
of idle, your error bars are dominated by idle repeatability. Bracket every workload with
two idle measurements and quote the drift. A 5 W delta measured against a baseline that
wanders 1.5 W carries roughly ±30% — say so, and do not quote three significant figures.

**3. Assuming core isolation is thermal isolation.** Pinning to a core range does not
partition shared L3, memory bandwidth, or the AVX-512 frequency licence. A heavily
threaded run can depress the all-core clock and change the measured cost of an unrelated
workload on nominally free cores. If the machine is shared, either own it for the duration
or state that you did not.

**4. Comparing a CPU number with a GPU number.** These do not transfer. Package RAPL does
not observe accelerator power, and the two systems do not port to a GPU equally. A GPU
column is a *different benchmark*, not a faster version of this one.

## What a large gap does and does not mean

A large cost gap says one method produces the same shaped output far more
cheaply. It says nothing about whether that output is *better*. The honest reading is:

> at equal output shape, method A costs Nx less; whether A's output is as useful is
> Benchmark 001's question, and must be answered before the cost figure means anything.

If your Kirk run is cheaper and its signal does not track the injected break in
`MOMENT_MATCHED`, you have measured the cost of a detector that does not detect. Report
that outcome — it is a real finding, and the more useful one.
