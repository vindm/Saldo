# Pack file contracts

The shape of each pack file (`manifest.yaml`, `authorities.yaml`, `regimes.yaml`,
`pipeline.yaml`, `lint.yaml`) is documented in `../README.md` → "A pack's files".
Use the `ru/` pack as the reference implementation.

Formal machine-readable JSON Schemas for validation are a planned addition; until
then the contract is the README plus the `ru/` pack, and `state_lint` /
`generate.py` surface malformed packs at render time.
