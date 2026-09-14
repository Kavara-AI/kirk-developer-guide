# Glossary

**Binary**  
The sealed Kirk build that computes a score. Its identity is a SHA-256 digest, stamped on
every scoring response as `engine_sha` — see **Engine**. Two results are only comparable if
they carry the same binary identity.

**Change point**  
A time associated with a transition in data-generating behaviour.

**Complex system**  
A system whose behaviour depends on interactions among multiple components or variables.

**Configuration**  
The parameter set and state policy under which a model is served. Not exposed on this
surface: two models can share a binary and a render and differ only in configuration, and
they will score the same input to different values.

**Data envelope**  
The input-shape contract a model accepts, identified by `envelope_hash` together with a
contract version. A model may report a null envelope, which means no contract has been
derived for it yet — that is stated rather than omitted.

**Engine**  
The term used for a **binary** throughout the API: `engine_sha`, `engine_name`, and the
`kirk_verify_engine` tool. Same object, API spelling.

**Feature**  
One input variable supplied to the tensor-generation process.

**Model**  
A registered model id, servable by a binary, and the thing you name when you call a tool.
A model is not the same as the combination of binary, configuration and input contract that
serves it: those can change while the model id stays the same, and two model ids can share
everything except configuration. Keep the model id with any result you record.

**Non-stationary**  
Having statistical behaviour that changes over time.

**Operating regime**  
A period with a relatively coherent pattern of system behaviour.

**Point anomaly**  
An individual observation considered unusual relative to a reference.

**Relationship change**  
A change in how two or more variables behave together.

**Score**  
One entropy value returned for one input, carrying the binary identity that produced it.

**Stride**  
The number of observations by which a sliding window advances.

**Tensor**  
An ordered multidimensional array. This guide primarily uses 2D time-by-feature tensors.

**Window**  
A contiguous segment of observations converted into one tensor.
