# Worked example: real captured runs

Real, end-to-end passes of `scanning-leaked-secrets`' own Procedure,
captured on 2026-08-15 against throwaway, deliberately-planted
fixtures -- never against this authoring repository's own tracked tree.
Every command, exit code, and quoted JSON value below is a transcript
from an actual run against the real pinned `betterleaks` 1.6.1 binary
on `PATH` -- nothing here is illustrative or invented. Every planted
"secret" is an obviously-fake value invented for this demonstration
alone (an invented RSA key body of garbage base64; an invented
database password), matching this authoring repository's own
established practice for eval fixtures that plant fake credentials to
prove a redaction mechanism works.

**Read this as evidence that the Procedure executes and that both
redaction layers hold, never as a pattern to expect in another
target.** A different target will produce entirely different findings
(or none), and a finding shape seen here is not a reason to expect or
report the same one elsewhere. The Stop boundary against carrying a
conclusion over by analogy applies to this file specifically.

## Contents

1. [Step 1 -- tool version](#step-1----tool-version)
2. [Step 2 -- a planted private key in the working tree](#step-2----a-planted-private-key-in-the-working-tree)
3. [Step 5 -- the CaptureGroups redaction gap, and this skill's own fix](#step-5----the-capturegroups-redaction-gap-and-this-skills-own-fix)
4. [Steps 2-3 -- a secret reachable only through history](#steps-2-3----a-secret-reachable-only-through-history)
5. [What the run demonstrates](#what-the-run-demonstrates)
6. [What the run did not do](#what-the-run-did-not-do)

## Step 1 -- tool version

```console
$ betterleaks --version
betterleaks version 1.6.1
```

Matches the version this repository's own `flake.nix` SHA256-pins, so
every run below reflects what the toolchain actually provisions.

## Step 2 -- a planted private key in the working tree

A scratch directory outside this repository's tracked tree (not staged,
not committed, never part of this change) held one file,
`id_rsa_fake`, containing an obviously-invented RSA private key block
(garbage base64 between real `BEGIN`/`END RSA PRIVATE KEY` markers, not
a real key). Procedure step 2's exact invocation, real output:

    $ betterleaks dir --redact --exit-code 0 --report-format json --report-path - --no-color --no-banner /tmp/.../betterleaks-dir-fixture
    10:19AM INF scanned ~639 bytes (639 bytes) in 52.8ms
    10:19AM WRN leaks found: 1
    [
     {
      "RuleID": "private-key",
      "Description": "Identified a Private Key, which may compromise cryptographic security and sensitive data encryption.",
      "StartLine": 1,
      "EndLine": 11,
      "StartColumn": 1,
      "EndColumn": 30,
      "Match": "REDACTED",
      "Secret": "REDACTED",
      "Attributes": {
       "path": "/tmp/.../betterleaks-dir-fixture/id_rsa_fake",
       "resource": "fs.content"
      },
      "Tags": [],
      "Fingerprint": "/tmp/.../betterleaks-dir-fixture/id_rsa_fake:private-key:1",
      "File": "/tmp/.../betterleaks-dir-fixture/id_rsa_fake",
      "SymlinkFile": "",
      "Commit": "",
      "Entropy": 5.3968034,
      "Author": "",
      "Email": "",
      "Date": "",
      "Message": ""
     }
    ]
    EXIT=0

(The scratch path's own session-specific prefix is abbreviated to
`/tmp/...` above and throughout this file -- the abbreviation touches
only that prefix, never a field the Procedure or Reporting contract
requires; every field name, value, and the full fixture-relative path
segment are exactly as captured.) `--redact` did its job here: `Match`
and `Secret` both read `REDACTED`. This finding carries no
`CaptureGroups` field at all -- `private-key` is a structureless rule,
unlike the connection-string rule in the next section -- so Procedure
step 5 has nothing to do for this particular finding, a real
illustration of "not every rule produces this field."

## Step 5 -- the CaptureGroups redaction gap, and this skill's own fix

A second scratch fixture, `db.env`, held one invented line:
`MONGODB_URI=mongodb+srv://dbuser:MyM0ngoP@ssw0rd@cluster0.mongodb.net/mydb`
-- an invented username and password, not a real credential. Procedure
step 2's exact invocation, real output, **before** step 5's
post-processing:

    $ betterleaks dir --redact --exit-code 0 --report-format json --report-path - --no-color --no-banner /tmp/.../betterleaks-captgroups-fixture
    10:19AM INF scanned ~75 bytes (75 bytes) in 42.9ms
    10:19AM WRN leaks found: 1
    [
     {
      "RuleID": "mongodb-connection-string",
      "Description": "Detected a MongoDB connection string with embedded credentials, potentially exposing direct database access and sensitive application data.",
      "StartLine": 1,
      "EndLine": 1,
      "StartColumn": 13,
      "EndColumn": 48,
      "Match": "REDACTED",
      "Secret": "REDACTED",
      "CaptureGroups": {
       "host": "ssw0rd",
       "password": "MyM0ngoP",
       "username": "dbuser"
      },
      "Attributes": {
       "path": "/tmp/.../betterleaks-captgroups-fixture/db.env",
       "resource": "fs.content"
      },
      "Tags": [],
      "Fingerprint": "/tmp/.../betterleaks-captgroups-fixture/db.env:mongodb-connection-string:1",
      "File": "/tmp/.../betterleaks-captgroups-fixture/db.env",
      "SymlinkFile": "",
      "Commit": "",
      "Entropy": 4.1625733,
      "Author": "",
      "Email": "",
      "Date": "",
      "Message": ""
     }
    ]
    EXIT=0

`Match` and `Secret` read `REDACTED` -- `--redact` covered those two
fields correctly, exactly as in Step 2 above. But `CaptureGroups`
reached stdout with its `password` and `username` values in plaintext,
even with `--redact` at its default value of 100. This is the real,
live-reproduced gap this skill's Procedure step 5 exists to close: the
flag's own redaction does not reach this field. Applying step 5 -- walk
the parsed JSON, replace every value under `CaptureGroups` with the
literal string `REDACTED` -- to this exact finding produces:

    [
      {
        "RuleID": "mongodb-connection-string",
        "Description": "Detected a MongoDB connection string with embedded credentials, potentially exposing direct database access and sensitive application data.",
        "StartLine": 1,
        "EndLine": 1,
        "StartColumn": 13,
        "EndColumn": 48,
        "Match": "REDACTED",
        "Secret": "REDACTED",
        "CaptureGroups": {
          "host": "REDACTED",
          "password": "REDACTED",
          "username": "REDACTED"
        },
        "Attributes": {
          "path": "/tmp/.../betterleaks-captgroups-fixture/db.env",
          "resource": "fs.content"
        },
        "Tags": [],
        "Fingerprint": "/tmp/.../betterleaks-captgroups-fixture/db.env:mongodb-connection-string:1",
        "File": "/tmp/.../betterleaks-captgroups-fixture/db.env",
        "SymlinkFile": "",
        "Commit": "",
        "Entropy": 4.1625733,
        "Author": "",
        "Email": "",
        "Date": "",
        "Message": ""
      }
    ]

Every `CaptureGroups` value now reads `REDACTED`, matching `Match` and
`Secret`. This is the same real finding, the same real fixture, shown
before and after step 5 -- not a separate illustrative example -- so this
is direct evidence the fix holds, not merely that it was written down.

## Steps 2-3 -- a secret reachable only through history

A throwaway git repository (its own local config only, never this
authoring repository's) committed a copy of the same `id_rsa_fake` file
from Step 2, then removed it with `git rm` and a second commit. The
working tree afterward holds neither the file nor any trace of it.

Procedure step 2 (`betterleaks dir`) against that post-removal working
tree:

    $ betterleaks dir --redact --exit-code 0 --report-format json --report-path - --no-color --no-banner /tmp/.../betterleaks-git-fixture
    10:19AM INF scanned ~0 bytes (0) in 38.8ms
    10:19AM INF no leaks found
    null
    EXIT=0

Literal `null`, exit `0` -- Procedure step 4 classifies this as a
completed, clean scan. The working-tree scan genuinely cannot see the
removed file; this is not a tool error, and it is not this skill
failing to redact anything, because there is nothing left to find.

Procedure step 3 (`betterleaks git`) against the same repository's full
history:

    $ betterleaks git --redact --exit-code 0 --report-format json --report-path - --no-color --no-banner /tmp/.../betterleaks-git-fixture
    10:19AM INF scanned ~639 bytes (639 bytes) in 57ms
    10:19AM WRN leaks found: 1
    [
     {
      "RuleID": "private-key",
      "Description": "Identified a Private Key, which may compromise cryptographic security and sensitive data encryption.",
      "StartLine": 1,
      "EndLine": 11,
      "StartColumn": 1,
      "EndColumn": 30,
      "Match": "REDACTED",
      "Secret": "REDACTED",
      "Attributes": {
       "git.author_email": "fixture@example.invalid",
       "git.author_name": "Betterleaks Fixture",
       "git.date": "2026-08-15T10:08:25Z",
       "git.message": "add fake fixture key",
       "git.sha": "1417f5f8e0cbe176d267d853dd52c0d257f16186",
       "path": "id_rsa_fake",
       "resource": "git.patch_content"
      },
      "Tags": [],
      "Fingerprint": "1417f5f8e0cbe176d267d853dd52c0d257f16186:id_rsa_fake:private-key:1",
      "File": "id_rsa_fake",
      "SymlinkFile": "",
      "Commit": "1417f5f8e0cbe176d267d853dd52c0d257f16186",
      "Entropy": 5.3968034,
      "Author": "Betterleaks Fixture",
      "Email": "fixture@example.invalid",
      "Date": "2026-08-15T10:08:25Z",
      "Message": "add fake fixture key"
     }
    ]
    EXIT=0

The same finding step 2 could no longer see is still found here,
attributed to the exact commit that introduced it
(`1417f5f8e0cbe176d267d853dd52c0d257f16186`, "add fake fixture key") --
real evidence that `betterleaks git` covers content the working tree no
longer holds. `Match` and `Secret` are redacted, and there is no
`CaptureGroups` field for this rule, matching Step 2's own result.

## What the run demonstrates

Three real facts, each shown rather than asserted:

- The same fixture (`id_rsa_fake`) produces the same `private-key`
  finding whether scanned in a plain working tree (Step 2) or reached
  only through git history (Steps 2-3) -- betterleaks' own detection is
  consistent across both invocation modes.
- `betterleaks dir` and `betterleaks git` genuinely see different
  content, not merely different metadata: the dir scan on the
  post-removal fixture reports `null`, while the git scan on that exact
  same repository still reports the finding. Running only `dir` on that
  fixture would have produced a confidently wrong "clean" report.
- `--redact` genuinely redacts `Match` and `Secret` in every case shown
  here, and just as genuinely does *not* redact `CaptureGroups` when a
  finding carries one. Both are real, reproduced properties of the
  pinned 1.6.1 binary, not assumptions -- the second one corrects an
  assumption this skill's own drafting started with, caught before
  shipping rather than after.

## What the run did not do

No `--validation` was ever passed, and no validation environment
variable was ever set -- none of the runs above touched the network.
No `github`, `gitlab`, `huggingface`, or `s3` subcommand was invoked.
No `--config` was passed in any run; each scratch fixture had no
`.betterleaks.toml`/`.gitleaks.toml`/`.betterleaksignore` of its own, so
every scan above ran against betterleaks' full default ruleset (325
rules as of 1.6.1) with nothing suppressed. No finding was rotated,
revoked, or remediated -- these are report-only demonstrations, and both
throwaway fixtures were discarded after capture, never staged or
committed to this authoring repository.
