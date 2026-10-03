# Agent entry point

For a user bringing data to Kirk, preparing a discovery brief, connecting a runtime,
or passing evidence to Jev, follow [the agent guide](docs/agent-guide.md). It gives
the task sequence, reference branches, output artifacts and completion criteria.
Start from the user's data; a domain label or known phenomenon is optional.

For customer REST access, Postman setup or the `api.kavara.ai` contract, follow
[Customer REST API](docs/customer-rest-api.md) and its
[OpenAPI specification](docs/customer-rest-api.openapi.json). The MCP quickstart
is a separate surface, not the only direct API. Use the client's secret mechanism
for credentials; do not assume a user must paste a key into chat.

For repository changes, read [CONTRIBUTING.md](CONTRIBUTING.md) and
[CLAUDE.md](CLAUDE.md). For catalogue changes, edit
`catalogues/phenomena.json` and follow the generation instructions in
[Tensor Generation](docs/tensor-generation.md#maintain-one-catalogue).
