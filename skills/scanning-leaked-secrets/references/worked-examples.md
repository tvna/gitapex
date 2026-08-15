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

**Read this as evidence that the Procedure executes and that all three
redaction layers hold, never as a pattern to expect in another
target.** A different target will produce entirely different findings
(or none), and a finding shape seen here is not a reason to expect or
report the same one elsewhere. The Stop boundary against carrying a
conclusion over by analogy applies to this file specifically.

## Contents

1. [Step 1 -- tool version](#step-1----tool-version)
2. [Step 2 -- a planted private key in the working tree](#step-2----a-planted-private-key-in-the-working-tree)
3. [Step 5 -- the CaptureGroups redaction gap, and this skill's own fix](#step-5----the-capturegroups-redaction-gap-and-this-skills-own-fix)
4. [Step 6 -- a commit message carries the credential past both other layers](#step-6----a-commit-message-carries-the-credential-past-both-other-layers)
5. [Steps 2-3 -- a secret reachable only through history](#steps-2-3----a-secret-reachable-only-through-history)
6. [What the run demonstrates](#what-the-run-demonstrates)
7. [What the run did not do](#what-the-run-did-not-do)

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
a real key). Procedure step 2's invocation, plus the two presentation-only
flags noted below, real output:

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

(Two notes on the transcripts, both applying throughout this file. First,
every command above and below carries `--no-color --no-banner` in addition
to Procedure step 2's and step 3's own flags. Both are presentation-only
and affect stderr alone -- `--no-banner` suppresses the startup banner,
`--no-color` drops ANSI codes from the log lines -- and were added so a
captured transcript reads cleanly here. Verified rather than assumed: the
stdout each command produces is byte-identical with and without them, so
the Procedure has no reason to carry either flag and deliberately does not.
Second, the scratch path's own session-specific prefix is abbreviated to
`/tmp/...` -- the abbreviation touches only that prefix, never a field the
Procedure or Reporting contract requires; every field name, value, and the
full fixture-relative path segment are exactly as captured.) `--redact`
did its job here: `Match` and `Secret` both read `REDACTED`. This
finding carries no
`CaptureGroups` field at all -- `private-key` is a structureless rule,
unlike the connection-string rule in the next section -- so Procedure
step 5 has nothing to do for this particular finding, a real
illustration of "not every rule produces this field."

## Step 5 -- the CaptureGroups redaction gap, and this skill's own fix

A second scratch fixture, `db.env`, held one invented line:
`MONGODB_URI=mongodb+srv://dbuser:MyM0ngoP@ssw0rd@cluster0.mongodb.net/mydb`
-- an invented username and password, not a real credential. Procedure
step 2's invocation again, real output, **before** step 5's
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

## Step 6 -- a commit message carries the credential past both other layers

A third scratch fixture: a throwaway git repository whose first commit
added `app.conf` holding an invented MongoDB connection string, then
documented rotating that credential in the *commit message itself* --
pasting the old connection string in full, a realistic mistake a
developer makes when writing a terse changelog-style commit rather than
a contrived one -- before a second commit removed the file. Procedure
step 2 against the resulting working tree:

    $ betterleaks dir --redact --exit-code 0 --report-format json --report-path - --no-color --no-banner /tmp/.../betterleaks-commitmsg-fixture
    12:23PM INF scanned ~0 bytes (0) in 37.4ms
    12:23PM INF no leaks found
    null
    EXIT=0

The file is gone from the working tree, so `dir` genuinely has nothing
to find. Procedure step 3 against the same repository's full history:

    $ betterleaks git --redact --exit-code 0 --report-format json --report-path - --no-color --no-banner /tmp/.../betterleaks-commitmsg-fixture
    12:23PM WRN leaks found: 1
    [
     {
      "RuleID": "mongodb-connection-string",
      "Description": "Detected a MongoDB connection string with embedded credentials, potentially exposing direct database access and sensitive application data.",
      "StartLine": 1,
      "EndLine": 1,
      "StartColumn": 11,
      "EndColumn": 71,
      "Match": "REDACTED",
      "Secret": "REDACTED",
      "CaptureGroups": {
       "authdb": "appdb",
       "host": "db.internal.example:27017",
       "password": "S3cr3tPassw",
       "username": "svcuser"
      },
      "Attributes": {
       "git.author_email": "dev@example.invalid",
       "git.author_name": "Fixture Dev",
       "git.date": "2026-08-15T12:23:32Z",
       "git.message": "chore: rotate db creds (old uri was mongodb://svcuser:S3cr3tPassw@db.internal.example:27017/appdb)",
       "git.sha": "28473cd4b1e5fed9b441467452af64716eaa1e92",
       "path": "app.conf",
       "resource": "git.patch_content"
      },
      "Tags": [],
      "Fingerprint": "28473cd4b1e5fed9b441467452af64716eaa1e92:app.conf:mongodb-connection-string:1",
      "File": "app.conf",
      "SymlinkFile": "",
      "Commit": "28473cd4b1e5fed9b441467452af64716eaa1e92",
      "Entropy": 4.729357,
      "Author": "Fixture Dev",
      "Email": "dev@example.invalid",
      "Date": "2026-08-15T12:23:32Z",
      "Message": "chore: rotate db creds (old uri was mongodb://svcuser:S3cr3tPassw@db.internal.example:27017/appdb)"
     }
    ]
    EXIT=0

`Match` and `Secret` both read `REDACTED`. Applying step 5 -- this
finding's `CaptureGroups` all replaced with `REDACTED` -- produces a
finding that looks fully redacted at a glance. It is not: `Message` and
`Attributes.git.message` still carry the connection string in full,
verbatim, in the exact same JSON. Assembling this step-5-redacted
finding into a report and piping it through step 6's own check:

    $ betterleaks stdin --redact --exit-code 0 --report-format json --report-path - --no-color --no-banner < assembled-report.json
    12:23PM WRN leaks found: 2
    [
     {
      "RuleID": "mongodb-connection-string",
      "Description": "Detected a MongoDB connection string with embedded credentials, potentially exposing direct database access and sensitive application data.",
      "StartLine": 21,
      "EndLine": 21,
      "StartColumn": 57,
      "EndColumn": 117,
      "Match": "REDACTED",
      "Secret": "REDACTED",
      "CaptureGroups": {
       "authdb": "appdb",
       "host": "db.internal.example:27017",
       "password": "S3cr3tPassw",
       "username": "svcuser"
      },
      "Attributes": {
       "path": "",
       "resource": "fs.content"
      },
      "Tags": [],
      "Fingerprint": ":mongodb-connection-string:21",
      "File": "",
      "SymlinkFile": "",
      "Commit": "",
      "Entropy": 4.729357,
      "Author": "",
      "Email": "",
      "Date": "",
      "Message": ""
     },
     {
      "RuleID": "mongodb-connection-string",
      "Description": "Detected a MongoDB connection string with embedded credentials, potentially exposing direct database access and sensitive application data.",
      "StartLine": 35,
      "EndLine": 35,
      "StartColumn": 52,
      "EndColumn": 112,
      "Match": "REDACTED",
      "Secret": "REDACTED",
      "CaptureGroups": {
       "authdb": "appdb",
       "host": "db.internal.example:27017",
       "password": "S3cr3tPassw",
       "username": "svcuser"
      },
      "Attributes": {
       "path": "",
       "resource": "fs.content"
      },
      "Tags": [],
      "Fingerprint": ":mongodb-connection-string:35",
      "File": "",
      "SymlinkFile": "",
      "Commit": "",
      "Entropy": 4.729357,
      "Author": "",
      "Email": "",
      "Date": "",
      "Message": ""
     }
    ]
    EXIT=0

Two hits, not `[]` -- one for `Attributes.git.message`, one for the
top-level `Message`, the report's own two copies of the same commit
message. Neither step 5 nor `--redact` itself ever looked at either
field, so both still held the connection string in full going into this
check. Redacting both fields' values to `REDACTED` and re-running the
identical check:

    $ betterleaks stdin --redact --exit-code 0 --report-format json --report-path - --no-color --no-banner < assembled-report-redacted.json
    12:23PM INF scanned ~1177 bytes (1.18 KB) in 50.5ms
    12:23PM INF no leaks found
    []
    EXIT=0

`[]`, not `null` -- `betterleaks stdin`'s own clean-result shape, a
different literal than `dir`/`git`'s `null` seen everywhere else in this
file. Reading `[]` as "still not clean" here would loop forever against
a report that is, at this point, actually clean; reading `dir`/`git`'s
own `null` as "not yet clean" would make the opposite mistake there.
Both literals were captured directly from this run, not asserted.

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

Four real facts, each shown rather than asserted:

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
- Step 5's own fix is not the end of the story: `Message` and
  `Attributes.git.message` carry a credential past both `--redact` and
  step 5 untouched, step 6's re-scan genuinely catches both occurrences
  in Step 6's finding above, and that same re-scan's own clean-result
  shape (`[]`) is a different literal than `dir`/`git`'s `null` -- a
  distinction this skill's own first draft of step 6 conflated, caught
  the same way the `CaptureGroups` gap was: by running the real binary
  rather than assuming its output shape.

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
