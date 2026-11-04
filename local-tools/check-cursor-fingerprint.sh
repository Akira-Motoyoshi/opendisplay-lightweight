#!/bin/zsh
set -eu
cd "$(dirname "$0")/.."
mkdir -p build/local-checks
nice -n 15 xcrun swiftc -O -swift-version 5 \
  Mac/CursorImageFingerprint.swift local-tools/CursorFingerprintChecks.swift \
  -o build/local-checks/cursor-fingerprint-checks
build/local-checks/cursor-fingerprint-checks
