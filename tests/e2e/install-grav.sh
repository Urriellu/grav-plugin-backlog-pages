#!/usr/bin/env bash
# Install a Grav release next to this repository so run.py has something to boot.
#
#   tests/e2e/install-grav.sh 2.0 /tmp/grav20
#   python3 tests/e2e/run.py --grav /tmp/grav20
#
# The first argument is a release *line* (1.7 or 2.0), not an exact version:
# the newest release on that line is what a user installing today would get,
# and is what CI resolves too.
set -euo pipefail

line="${1:?usage: install-grav.sh <1.7|2.0> <target-dir>}"
target="${2:?usage: install-grav.sh <1.7|2.0> <target-dir>}"

tag=$(git ls-remote --tags --refs https://github.com/getgrav/grav.git "${line}.*" \
      | sed 's|.*refs/tags/||' | sort -V | tail -1)
[ -n "$tag" ] || { echo "no Grav release matched ${line}.*" >&2; exit 1; }

echo "Installing Grav $tag into $target"
rm -rf "$target"
git clone -q --depth 1 --branch "$tag" https://github.com/getgrav/grav.git "$target"
cd "$target"
composer install --no-dev --no-interaction --no-progress --quiet
# Fetches the default theme -- Quark on 1.7, Quark2 on 2.0 -- plus the error
# and problems plugins. Without a theme there is no base template to extend.
php bin/grav install
echo "Ready: python3 tests/e2e/run.py --grav $target"
