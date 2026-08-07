#!/usr/bin/env bash
# Energy harness. A workload measurement without an idle baseline is not a measurement:
# package RAPL includes the whole socket, so only the DELTA is attributable.
set -euo pipefail
IDLE_SECS="${IDLE_SECS:-40}"
EV="power/energy-pkg/"

joules() { grep -oE '[0-9,]+\.[0-9]+ Joules' | head -1 | tr -d ', Joules'; }
secs()   { grep -oE '[0-9]+\.[0-9]+ seconds time elapsed' | grep -oE '^[0-9.]+'; }

echo "=== idle baseline (${IDLE_SECS}s) ==="
IDLE=$(perf stat -a -e $EV -- sleep "$IDLE_SECS" 2>&1)
IJ=$(echo "$IDLE" | joules); IS=$(echo "$IDLE" | secs)
IW=$(awk -v j="$IJ" -v s="$IS" 'BEGIN{printf "%.2f", j/s}')
echo "idle: ${IJ} J / ${IS} s = ${IW} W"

echo "=== workload: $* ==="
RUN=$(perf stat -a -e $EV -- "$@" 2>&1)
echo "$RUN" | grep -vE 'Joules|seconds time|Performance counter' || true
WJ=$(echo "$RUN" | joules); WS=$(echo "$RUN" | secs)
WW=$(awk -v j="$WJ" -v s="$WS" 'BEGIN{printf "%.2f", j/s}')
DW=$(awk -v a="$WW" -v b="$IW" 'BEGIN{printf "%.2f", a-b}')
DJ=$(awk -v d="$DW" -v s="$WS" 'BEGIN{printf "%.1f", d*s}')
echo "workload: ${WJ} J / ${WS} s = ${WW} W"
echo "ATTRIBUTABLE: ${DW} W over ${WS} s = ${DJ} J"
echo "Divide by the run's output-window count for J per unit of signal."

echo "=== idle re-check (drift bound) ==="
IDLE2=$(perf stat -a -e $EV -- sleep "$IDLE_SECS" 2>&1)
I2J=$(echo "$IDLE2" | joules); I2S=$(echo "$IDLE2" | secs)
awk -v j="$I2J" -v s="$I2S" -v w="$IW" 'BEGIN{
  w2=j/s; printf "idle#2: %.2f W (drift %.2f W, %.1f%%)\n", w2, w2-w, 100*(w2-w)/w }'
