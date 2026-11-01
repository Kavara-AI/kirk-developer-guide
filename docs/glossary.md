# Glossary

**Binary**  
The build that computes a score. The v1 customer REST contract does not return
build identity. Keep the `X-Kavara-Receipt` value from a metered success with
the result. See [Customer REST API](customer-rest-api.md).

**Change point**  
A time associated with a transition in data-generating behaviour.

**Complex system**  
A system whose behaviour depends on interactions among multiple components or variables.

**Configuration**  
The `hyperparameters` object sent to `POST /v1/kirk-api/create`, including
`visible_nodes`. Learn and score then send the snapshot that create returned.

**Data envelope**  
The input-shape contract a call accepts. For the v1 customer REST contract,
`samples` are `n` squares of `V` × `V`, and every real and imaginary part lies
in [-1, 1]. See [Customer REST API](customer-rest-api.md).

**Feature**  
One measured stream you may place on an axis when you build the square matrix for a step.

**Model**  
/v1/engine, /v1/models, /v1/score-book and /usage* are not part of v1.
Create takes `hyperparameters`. Learn and score take a snapshot and samples.

**Non-stationary**  
Having statistical behaviour that changes over time.

**Operating regime**  
A period with a relatively coherent pattern of system behaviour.

**Point anomaly**  
An individual observation considered unusual relative to a reference.

**Relationship change**  
A change in how two or more variables behave together.

**Score**  
The `entropy` array (float32, one value per submitted square) in a learn or score
response. `outputs=entropy` returns that array alone. `outputs=all` and
`outputs=features` also return `feature_arr`, `feature_vec` and `feature_scalar`.
/v1/engine, /v1/models, /v1/score-book and /usage* are not part of v1.

**Stride**  
How many source observations the next matrix advances. You choose it when you build
the matrices.

**Tensor**  
The square real- or complex-valued matrix Kirk takes at one time step. Typical sizes
are 16 × 16 and 32 × 32.

**Window**  
The recent source observations you summarise into one square matrix. You choose the
length of that window.
