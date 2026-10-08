# Frequently Asked Questions

## Is Kirk an LLM?

No. This guide treats Kirk as an inference engine for multistream, non-stationary systems rather than a language-generation model.

## Does Kirk directly diagnose faults?

Not necessarily. A state-change output can indicate that behaviour changed without identifying the cause.

## Does Kirk require labels?

The intended evaluation focuses on settings where labels may be absent, incomplete or delayed. Ground-truth events remain useful for benchmark evaluation.

## Why a square matrix?

Each step, Kirk takes one square matrix of real or complex values, and you build
it. Rows and columns might be recent lags of one stream, channels against an
equal number of recent time steps, or channel-by-channel products over a recent
interval. See [tensor generation](tensor-generation.md).

## Is Benchmark 001 a validated result?

Not yet. It is a reproducible experiment specification until actual Kirk outputs are committed.

## Why compare with an LSTM?

An LSTM is one possible sequence-model baseline. The comparison must be implemented and tuned fairly; the documentation should not assume the result in advance.
