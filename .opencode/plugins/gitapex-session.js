// gitapex OpenCode session provisioning (issue #1812).
//
// OpenCode parity for `.claude/hooks/session-start.sh` (Claude-only):
// on `session.created`, provision the flake.nix-pinned Class B toolchain
// (`skills/setup-gitapex-toolchain/scripts/gitapex_provision_class_b.py`,
// which also runs `apm install` for the devDependencies) and mirror this
// checkout's own skills/agents into OpenCode discovery paths
// (`hooks/gitapex_sync_opencode.py`). `shell.env` puts the provisioned
// binaries on PATH for every shell the session spawns.
//
// Fail-soft by contract: every step is best-effort and never throws out
// of a hook -- a provisioning hiccup must degrade to a log line, never a
// broken session start.
//
// Only stdlib `node:` imports: no `package.json`, no `bun install` step,
// nothing for OpenCode to fetch at startup.

import { execFile } from "node:child_process";
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { join, delimiter } from "node:path";

function isGitapexCheckout(directory) {
  try {
    return (
      existsSync(join(directory, "apm.yml")) &&
      existsSync(join(directory, "skills")) &&
      existsSync(join(directory, "hooks", "gitapex_sync_opencode.py"))
    );
  } catch {
    return false;
  }
}

function toolchainBinDir() {
  const base = process.env.XDG_CACHE_HOME || join(homedir(), ".cache");
  return join(base, "gitapex", "toolchain", "bin");
}

function runFile(client, label, file, args, timeoutMs) {
  return new Promise((resolve) => {
    execFile(file, args, { timeout: timeoutMs }, async (error) => {
      if (!error) {
        resolve(true);
        return;
      }
      try {
        await client.app.log({
          body: {
            service: "gitapex",
            level: "warn",
            message: `${label} reported a failure; continuing without it: ${String(
              (error && error.message) || error
            ).slice(0, 300)}`,
          },
        });
      } catch {
        // Logging itself must never break session start either.
      }
      resolve(false);
    });
  });
}

export const GitapexSession = async ({ client, directory }) => {
  return {
    event: async ({ event }) => {
      if (!event || event.type !== "session.created") return;
      if (!directory || !isGitapexCheckout(directory)) return;
      const python = process.env.GITAPEX_PYTHON || "python3";
      // Sync FIRST: it is local-only (<1s, no network), so even a
      // short-lived `opencode run` one-shot converges skill visibility
      // before the process can exit. Provisioning (downloads + apm
      // install) follows; its own idempotency receipts make the
      // steady-state run a fast no-op, and only a first-ever session pays
      // for downloads (with a generous timeout for a cold cache).
      await runFile(
        client,
        "gitapex opencode skill sync",
        python,
        [join(directory, "hooks", "gitapex_sync_opencode.py"), "--project-dir", directory],
        60000
      );
      await runFile(
        client,
        "gitapex toolchain provisioning",
        python,
        [
          join(
            directory,
            "skills",
            "setup-gitapex-toolchain",
            "scripts",
            "gitapex_provision_class_b.py"
          ),
          "--project-dir",
          directory,
        ],
        300000
      );
    },
    "shell.env": async (input, output) => {
      try {
        const bin = toolchainBinDir();
        if (!existsSync(bin)) return;
        const current = (output.env && output.env.PATH) || process.env.PATH || "";
        if (current.split(delimiter).includes(bin)) return;
        output.env = output.env || {};
        output.env.PATH = current ? `${bin}${delimiter}${current}` : bin;
      } catch {
        // PATH injection is an optimization, never a requirement.
      }
    },
  };
};
