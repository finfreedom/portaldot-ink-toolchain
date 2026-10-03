# Building and deploying ink! smart contracts on Portaldot

> ## ⚠️ Which chain is this for?
>
> **This recipe is for Portaldot _mainnet_** (`spec_name: portaldot`,
> `spec_version: 1002`, `Contracts.palletVersion: 0`). That runtime dates from
> Substrate 3.0 and needs a 2021 toolchain, which is what the rest of this
> document is about.
>
> **It is NOT needed for the PortaldotV3 testnet**, announced 2 October 2026.
> Measured on `wss://testnetv3-node.feso-apps.xyz`:
>
> | | mainnet | V3 testnet |
> |---|---|---|
> | `spec_name` / `spec_version` | `portaldot` / 1002 | `portaldotV3` / 3000 |
> | pallets | 31 | 70 |
> | `Contracts.palletVersion` | **0** | **16** |
> | `Revive` (PolkaVM / Solidity) | absent | **present** |
> | `NominationPools` | absent | present |
>
> ink! documents that ink! 5 requires `Contracts.palletVersion >= 9`. V3 reports
> **16**, so on V3 you can simply use **current ink! 5 and cargo-contract 4+**,
> or Solidity through `pallet-revive`. None of the 2021 archaeology below
> applies there.
>
> Official V3 testnet guide and samples:
> https://github.com/ItsCogumellum/portaldot-v3-testnet-guide
>
> Everything below remains correct and necessary **for mainnet**, which still
> runs the 2021 runtime at the time of writing.
>
> ### Verified: what building for V3 actually takes
>
> ```bash
> cargo install cargo-contract --version "^5" --locked
> rustup component add rust-src --toolchain stable
> rustup target add wasm32-unknown-unknown --toolchain stable
> cargo contract new my_contract && cd my_contract
> cargo contract build --release
> ```
>
> That is the whole thing. Stock `stable` Rust, no pinned versions, no flags,
> ~90 seconds — and unlike the mainnet path it produces the full bundle
> including `metadata.json`.
>
> | | mainnet | V3 testnet |
> |---|---|---|
> | cargo-contract | 0.12.1 (2021) | 5.0.3 |
> | ink! | 3.0.0-rc3 | 5.1.1 |
> | compiler | `nightly-2021-08-01` | `stable` 1.87 |
> | pins in Cargo.toml | 8 | none |
> | lockfile surgery | dozens of downgrades | none |
> | special flags | `-Z original-manifest` | none |
> | `metadata.json` | **not produced** | produced |
> | wasm size (flipper) | 5221 B | 1692 B |
>
> **The two chains' artifacts are mutually incompatible**, verified by imports:
> an ink! 5 contract imports `seal1 get_storage` / `seal2 set_storage`, host
> functions the mainnet pallet does not have at all. Keep both toolchains
> installed side by side if you target both:
>
> ```bash
> cargo install cargo-contract --version "^5" --root ~/.local/cargo-contract-v5
> ```


A working, end-to-end recipe for compiling an ink! contract and deploying it to
[Portaldot Network](https://www.portaldot.world/).

This is harder than it looks. Portaldot's `Contracts` pallet dates from
Substrate 3.0 (February 2021), and the toolchain that targets it no longer
builds out of the box against today's crates.io. Every modern guide you will
find is wrong for this chain.

Everything below was verified on 29 September 2026 against a local node built
from Portaldot's own published binary.

## Verified result

```
contract address  5EGqHvej3KQk6uWKHB1ummDA3qRFGLgdbcbFivhKUWbZA4U4
code hash         0xa0f32690b5a9034ec71e0570c80dab0cc1e90883db461b3d5cc954f175ac63d1

get()   -> 0x01        (true, as constructed)
flip()  -> included in block
get()   -> 0x00        (false)
contracts.contractInfoOf(addr) -> present
```

A known-good `Cargo.toml` and `Cargo.lock` are in [`reference/`](reference/).
Reproducing them from scratch takes hours; copying them takes seconds.

## Which ink! version, and how we know

Query the chain rather than guessing:

```
contracts.palletVersion   0
schedule.version          4
```

The ink! documentation states that ink! 5 requires `contracts.palletVersion`
to be **9 or higher**. Portaldot reports **0**, so ink! 4 and 5 are out.

The extrinsic signatures date the pallet precisely:

```
call(dest: LookupSource, value: Compact<BalanceOf>,
     gasLimit: Compact<Weight>, data: Bytes)
instantiateWithCode(endowment: Compact<BalanceOf>, gasLimit: Compact<Weight>,
                    code: Bytes, data: Bytes, salt: Bytes)
instantiate(endowment: Compact<BalanceOf>, gasLimit: Compact<Weight>,
            codeHash: CodeHash, data: Bytes, salt: Bytes)
claimSurcharge(dest: AccountId, auxSender: Option<AccountId>)
```

Four signals, and together they pin it down:

1. The parameter is called **`endowment`**, not `value` — that is pre-ink! 4.
2. There is **no** `uploadCode`, `removeCode` or `setCode` — those came later.
3. `gasLimit` is a plain `Compact<Weight>`, not the Weights v2
   `{refTime, proofSize}` struct.
4. The rent/tombstone model is still there: `claimSurcharge`,
   `tombstoneDeposit`, `rentFraction`, `depositPerStorageByte`.

That is **pallet-contracts 3.0.0 from Substrate 3.0.0**, so the target is
**ink! 3.0.0-rc3** with **cargo-contract 0.12.1**.

## The compiler window

Here is the part that costs people an evening.

`ink_storage` 3.0.0-rc3 hard-enables the `const-generics` feature of
`array-init` 1.0.0, which relies on `#![feature(const_generics)]`. That
compiler feature was **removed** in autumn 2021, split into `adt_const_params`
and `generic_const_exprs`.

So the compiler must be:

- **new enough** to understand edition 2021, stabilised in Rust 1.56 — otherwise
  `cargo metadata` cannot even parse a third of the dependency tree;
- **old enough** to still accept `feature(const_generics)`.

That window is roughly **August 2021**. We use `nightly-2021-08-01`
(rustc 1.56.0-nightly). Nightlies from 2021-09-15 onward already reject
`const_generics`; anything older than ~2021-09 cannot read edition 2021.

## Recipe

### 1. Tools

```bash
rustup toolchain install nightly-2021-08-01 --profile minimal --component rust-src
rustup target add wasm32-unknown-unknown --toolchain nightly-2021-08-01
cargo install cargo-contract --version 0.12.1 --locked
brew install binaryen     # or apt-get install binaryen
```

`cargo-contract 0.12.1` builds natively with a current stable Rust (tested with
1.87 on aarch64-apple-darwin). No Docker needed.

`binaryen` provides `wasm-opt`. Without it the build stops at step 3 of 5.

### 2. Cargo.toml

Pin every ink! crate with `=`. A plain `"3.0.0-rc3"` requirement resolves to
**ink 3.4.0** under semver, which uses `parity-scale-codec` 3.x while rc3 needs
2.x, and the build dies on `Mismatching versions of parity-scale-codec`.

```toml
ink_primitives = { version = "=3.0.0-rc3", default-features = false }
ink_metadata   = { version = "=3.0.0-rc3", default-features = false, features = ["derive"], optional = true }
ink_env        = { version = "=3.0.0-rc3", default-features = false }
ink_storage    = { version = "=3.0.0-rc3", default-features = false }
ink_lang       = { version = "=3.0.0-rc3", default-features = false }

# Transitive, but they must be direct dependencies to be pinned:
ink_lang_ir    = { version = "=3.0.0-rc3", default-features = false }
ink_prelude    = { version = "=3.0.0-rc3", default-features = false }
ink_allocator  = { version = "=3.0.0-rc3", default-features = false }

scale      = { package = "parity-scale-codec", version = "=2.3.1", default-features = false, features = ["derive"] }
scale-info = { version = "=0.6.0", default-features = false, features = ["derive"], optional = true }
```

Without those three transitive pins, `ink_lang_macro` 3.0.0-rc3 fails with
`cannot find InkTrait in ink_lang_ir` — the type was renamed after rc3.

See [`reference/Cargo.toml`](reference/Cargo.toml).

### 3. Cargo.lock

The lockfile has to describe the crates.io of autumn 2021. Three rules, each
learned the hard way:

**Edit the lockfile with a modern cargo, not the one you build with.**
Cargo 1.55 cannot downgrade a crate whose current version has an edition-2021
manifest, because to perform the downgrade it must first parse that manifest.
Chicken and egg. A current cargo parses it fine and writes a lockfile the old
one can then consume.

**Reset the lockfile format afterwards.** A modern cargo writes `version = 4`
in the header; cargo 1.55 refuses it. Change it back to `version = 3`.

**Select by version number among semver-compatible releases, not by date.**
For `crossbeam-deque`, the most recent release *by date* before the cutoff is
0.7.4 — a backport published after 0.8.1 — which does not satisfy `^0.8`.

One more trap: the crates.io API returns only the ~44 most recent versions of a
crate and rejects `per_page` with HTTP 400. Automated version selection is blind
for crates with long histories, so [`scripts/fix_lock.py`](scripts/fix_lock.py)
carries a small table of manual pins.

[`scripts/fix_lock.py`](scripts/fix_lock.py) drives off the old cargo's own
error messages: it asks cargo what broke, downgrades that crate with the modern
cargo, restores the header, and repeats until the tree resolves.

The simplest path is to copy [`reference/Cargo.lock`](reference/Cargo.lock).

### 4. Build

```bash
cargo +nightly-2021-08-01 contract build -Z original-manifest --generate code-only
```

**`-Z original-manifest` is mandatory.** Without it cargo-contract copies the
project into a temporary directory and re-resolves dependencies from scratch,
ignoring your `Cargo.lock` entirely. This is the single most confusing failure
mode: you pin a version, you can see it in the lockfile, and the error does not
change.

**`--generate code-only` is mandatory alongside it.** `-Z original-manifest`
suppresses the synthesised `metadata-gen` helper package, so step 4 of 5 fails
with `package(s) 'metadata-gen' not found in workspace`.

Output: `target/ink/<name>.wasm`, about 5 KB, importing `seal0` host functions —
exactly what pallet-contracts 3.0.0 provides:

```
(import "seal0" "seal_get_storage")
(import "seal0" "seal_input")
(import "seal0" "seal_return")
(import "seal0" "seal_set_storage")
(import "seal0" "seal_value_transferred")
```

### 5. A local chain to test against

Portaldot publishes node binaries in
[`portaldotVolunteer/Portaldot-node`](https://github.com/portaldotVolunteer/Portaldot-node).

```bash
tar xzf portaldot-testnet-macos.tar.gz
./portaldot-testnet-macos/portaldot_dev --dev --tmp \
    --rpc-port 9933 --ws-port 9944 --rpc-cors all --rpc-methods unsafe
```

The binaries are x86_64; on Apple Silicon they run under Rosetta. The `--dev`
chain matches mainnet exactly — spec `portaldot` 1002, `palletVersion` 0, same
extrinsic signatures — and Alice starts with 50,000 POT. There is no reason to
touch mainnet while developing.

### 6. Deploy and call

The signatures are the old ones, so copy-pasted examples from current tutorials
will not work.

```js
api.tx.contracts.instantiateWithCode(endowment, gasLimit, codeHex, data, salt)
api.tx.contracts.call(dest, value, gasLimit, data)
```

`data` is the selector — the first four bytes of `blake2-256(name)` — followed by
SCALE-encoded arguments. For the flipper example:

```
new  0x9bae9d5e      get  0x2f865bd9      flip  0x633aa551
```

`endowment` must exceed `tombstoneDeposit`, which is 6.87 POT on this chain.
`gasLimit` is a plain integer, not `{refTime, proofSize}`.

**Call the read RPC through the provider directly.** Portaldot's
`contracts_call` accepts exactly five fields, while a current `@polkadot/api`
adds `storageDepositLimit` and gets back:

```
-32602: Invalid params: unknown field `storageDepositLimit`,
        expected one of `origin`, `dest`, `value`, `gasLimit`, `inputData`.
```

So:

```js
await provider.send('contracts_call', [{
  origin, dest, value: 0, gasLimit: 500000000000, inputData: selector,
}]);
```

## Bonus trap: the Python SDK

Portaldot's docs tell you to connect like this:

```python
portaldot = SubstrateInterface(url="wss://mainnet.portaldot.io",
                               ss58_format=42,
                               type_registry_preset='default')
```

`'default'` no longer exists in current `scalecodec` — you get
`ValueError: Unsupported type registry preset "default"`. Omitting the preset
fails differently: `NotImplementedError: Decoder class for "ActiveEraInfo" not found`.

The preset that works against this runtime is **`legacy`**:

```python
from substrateinterface import SubstrateInterface

substrate = SubstrateInterface(
    url="wss://mainnet.portaldot.io",
    ss58_format=42,
    type_registry_preset="legacy",
)
```

With that, storage reads, `query_map`, and **event decoding** all work.

Worth noting: current `@polkadot/api` fails to decode this chain's
`system.events` (`Decoded input doesn't match input`) and produces
`Invalid Transaction: Transaction has a bad signature` for some extrinsics.
`py-substrate-interface` with the `legacy` preset handles both correctly. If
you are choosing a client for Portaldot today, that is a point for Python.

### Proxy pallet types are missing from the `legacy` preset

Reading `Proxy.Proxies` or `Proxy.Announcements` fails with

```
NotImplementedError: Decoder class for "ProxyDefinition<AccountId, ProxyType" not found
```

The type strings in this runtime's metadata are also malformed — double
spaces and trailing commas — so aliases must be registered against the
**exact** strings. `BoundedVec` is SCALE-encoded identically to `Vec`, so
substituting it loses nothing:

```python
PD = "(BoundedVec<ProxyDefinition<AccountId, ProxyType,  BlockNumber>, MaxProxies,>, BalanceOf)"
AN = "(BoundedVec<Announcement<AccountId, CallHashOf,  BlockNumber>, MaxPending,>, BalanceOf,)"

PROXY_TYPES = {"types": {
    "ProxyType": {"type": "enum",
                  "value_list": ["Any", "NonTransfer", "Governance", "Staking"]},
    "ProxyDefinition": {"type": "struct", "type_mapping": [
        ["delegate", "AccountId"], ["proxy_type", "ProxyType"], ["delay", "BlockNumber"]]},
    "Announcement": {"type": "struct", "type_mapping": [
        ["real", "AccountId"], ["call_hash", "Hash"], ["height", "BlockNumber"]]},
    "ProxiesOf": {"type": "struct", "type_mapping": [
        ["definitions", "Vec<ProxyDefinition>"], ["deposit", "Balance"]]},
    "AnnouncementsOf": {"type": "struct", "type_mapping": [
        ["announcements", "Vec<Announcement>"], ["deposit", "Balance"]]},
    PD: "ProxiesOf",
    AN: "AnnouncementsOf",
}}

substrate = SubstrateInterface(url=..., ss58_format=42,
                               type_registry_preset="legacy",
                               type_registry=PROXY_TYPES)
```

### A note on `ProxyType::Staking`

Worth knowing before you build anything on proxies here. The runtime defines
the filter as:

```rust
ProxyType::Staking => matches!(c, Call::Staking(..)),
```

That is **every** call in `pallet_staking`, with no exceptions — including
`set_payee`, which lets the delegate redirect all future staking rewards to
an arbitrary account. A `Staking` proxy is not "can only nominate".

`pallet_proxy` here does support delayed proxies, and the delay genuinely
closes the direct path:

```rust
ensure!(def.delay.is_zero(), Error::<T>::Unannounced);
```

So with `add_proxy(delegate, Staking, delay)` the delegate must `announce`,
wait, and then `proxy_announced`, and the principal can `reject_announcement`
in between. Verified end to end against a local `--dev` chain built from the
published `Portaldot-node` binary.

## Still open

Generating `metadata.json` and the bundled `.contract` file. Both are produced
by the `metadata-gen` helper package that `-Z original-manifest` disables.
They are not required for deployment — selectors can be computed by hand — but
they are needed for a comfortable front end. Contributions welcome.

## A note on the chain

At the time of writing, Portaldot mainnet has produced over 2.7 million blocks
and `contracts.contractInfoOf` and `contracts.codeStorage` are both **empty**.
No contract has ever been deployed on it. That is probably why the working
toolchain versions were not documented anywhere: nobody had needed them yet.

## Why this exists

Written while preparing for the
[Portaldot Hacker House 2026](https://dorahacks.io/hackathon/portaldot-hacker-house-2026/detail).
Deploying to the Portaldot testnet is a submission requirement, so every team
with a contract will hit this wall. Published so they do not each lose an
evening to it.

Corrections and additions are welcome — especially from the Portaldot team, if
V3.0 replaces the `Contracts` pallet and makes all of this obsolete.

## License

Apache-2.0. The `example/lib.rs` contract is the stock `cargo-contract`
template by Parity Technologies, also Apache-2.0.
