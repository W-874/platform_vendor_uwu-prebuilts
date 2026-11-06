<!--
SPDX-FileCopyrightText: The uwuAOSP Project
SPDX-License-Identifier: Apache-2.0
-->

# Runa Linux x86_64 prebuilt

`runa` is the Linux x86_64 host executor used by `uwuCLI/uni`. It includes the
runtime control socket interface (`--control-socket`), file-based job admission
(`--parallelism-file`), and API-safe `-d assumeexisting` behavior.

- Source project: `external/runa`
- Source revision: `2172e6e2d1b140341f02e4852e98af570ffa5bc4`
- SHA-256: `6c6879aa187d793fae8f90f319f71e014fdc34c2fa1bcf03ee6c7e2b11dc6459`
- Runtime: Linux x86_64 with glibc and the standard C++ runtime

Refresh this prebuilt when the Runa source or its runtime-control protocol
changes. Keep the artifact and source revision metadata in the same change.
This artifact was built with AOSP's clang-r584948b host
toolchain using `configure.py --bootstrap`, then stripped with `llvm-strip`.

Runtime job limits affect new commands only. They never cancel running commands
and cannot exceed the initial `-j` limit. Missing or invalid control-file values
retain the last valid limit. Uni's recovery, signing, reporting and graph-reuse
options are handled by Uni; they are not forwarded as Runa command-line flags.
