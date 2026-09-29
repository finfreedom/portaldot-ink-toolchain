# Known-good manifests

Copy these into your contract project.

- `Cargo.toml` — every ink! crate pinned with `=`, including the three
  transitive ones that must be listed as direct dependencies.
- `Cargo.lock` — a dependency tree that `cargo 1.55` can actually parse.
  Header says `version = 3` on purpose; do not let a modern cargo rewrite it
  to `4` without changing it back.

Verified with `nightly-2021-08-01` and `cargo-contract 0.12.1`.
