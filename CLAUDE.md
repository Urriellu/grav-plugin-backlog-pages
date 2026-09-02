# Working on this repository

## Changes reach `main` through a pull request, never directly

`main` is what GPM serves to people who install the plugin, so nothing lands on
it that its owner has not read. Every change — however small, however obviously
correct — is delivered as a pull request on github.com and merged there by the
repository owner, in the browser. That includes documentation, CI and this file.

The loop, end to end:

1. Branch off `main`. Name it for the change: `fix/…`, `ci/…`, `docs/…`.
2. Commit the work. Run the tests first where it is cheap to
   (`python3 tests/e2e/run.py --grav <a Grav checkout>`); CI will run the rest.
3. Push the branch and open the pull request:
   `git push -u origin <branch> && gh pr create --fill`
4. Say the pull request is open and hand over the link. **Stop there.**

Do not merge, do not `gh pr merge`, do not push to `main`, and do not close a
pull request that has been opened. Reviewing and merging is the owner's job, and
a pull request that merges itself gives them nothing to review. If review asks
for changes, push more commits to the same branch — the pull request and its CI
results update in place.

## What the pull request shows

`.github/workflows/ci.yml` runs on every pull request: syntax on the PHP floor
and ceiling, the package metadata and changelog checks, end-to-end runs against
the newest release of each supported Grav line, and the Playwright tests.

The `CI` job gathers all of them and reports twice, so the results are visible
without opening the Actions tab:

- as one pass/fail check on the pull request, which is the check to require in
  branch protection — the individual jobs come and go as the matrix changes,
  this one does not;
- as a comment on the pull request listing every job with its verdict and a
  link to its log. Pushing again rewrites that comment rather than adding a
  second one.

A red check means it is not ready to merge. Fix it on the branch and push; do
not ask for a merge around it.
