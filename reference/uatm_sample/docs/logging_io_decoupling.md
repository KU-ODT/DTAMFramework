# Logging I/O Decoupling

Updated: 2026-02-10

## Goal
- Remove synchronous disk writes from the simulation tick path.
- Keep simulation timing less sensitive to storage latency spikes.

## Changes
- `FlightLogger` now uses an internal bounded queue and a dedicated writer thread.
- `append_positions` and `append_event` enqueue log work instead of writing files inline.
- `stop()` now drains pending queue work (`flush`) and then closes files.
- `read_history()` and log zip generation flush pending writes before reading files.

## Behavior Notes
- Queue is bounded (`maxsize=2048`) to avoid unbounded memory growth.
- If the queue is full, new log batches are dropped with periodic warning output.
- Track files are opened in append mode and write headers only when file is empty.

## Expected Effect
- Main simulation loop is protected from direct file I/O stalls.
- High-load scenarios should show fewer tick delays caused by disk flush/write latency.

