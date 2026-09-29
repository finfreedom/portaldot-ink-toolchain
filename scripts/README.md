# Lockfile helpers

Only needed if you are building a tree from scratch instead of copying
`reference/Cargo.lock`.

- `fix_lock.py` — drives off the old cargo's error messages: asks what broke,
  downgrades that crate with the modern cargo, restores `version = 3` in the
  lockfile header, repeats until the tree resolves.
- `date_pin.py` — bulk pass that moves every crate in the lockfile to the
  release current as of the cutoff date.

Both assume the contract lives at the path set in the script header; adjust
`DIR` before running.

Note: the crates.io API returns only the ~44 most recent versions of a crate
and rejects `per_page` with HTTP 400, so version selection is blind for crates
with long histories. `fix_lock.py` carries a table of manual pins for the ones
that matter here.
