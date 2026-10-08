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
surface: two models can share a binary and the same input contract and differ only in
configuration, and they will score the same input to different values.

**Data envelope**  
The input-shape contract a model accepts. For Kirk, that is one square real- or
complex-valued matrix per step. A published envelope is identified by `envelope_hash`
together with a contract version. A model may report a null envelope, which means no
contract has been derived for it yet — that is stated rather than omitted.

**Engine**  
The term used for a **binary** throughout the API: `engine_sha`, `engine_name`, and the
`kirk_verify_engine` tool. Same object, API spelling.

**Feature**  
One measured stream you may place on an axis when you build the square matrix for a step.

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
An entropy (surprise) value returned for one step, carrying the binary identity that
produced it. Evaluation access can also return an embedding of the evolving structure
or a prediction of masked input. Some public routes return the entropy score only.

**Stride**  
How many source observations the next matrix advances. You choose it when you build
the matrices.

**Tensor**  
The square real- or complex-valued matrix Kirk takes at one time step. Typical sizes
are 16 × 16 and 32 × 32.

**Window**  
The recent source observations you summarise into one square matrix. You choose the
length of that window.
