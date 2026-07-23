import { existsSync } from "node:fs";
import { homedir } from "node:os";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);

function moduleDirectories() {
  const configured = [
    process.env.CODEX_NODE_MODULES,
    ...(process.env.NODE_PATH ? process.env.NODE_PATH.split(path.delimiter) : []),
    path.join(
      homedir(),
      ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules",
    ),
  ];
  return configured.filter((value, index, values) =>
    value && values.indexOf(value) === index && existsSync(value));
}

export function loadModule(name) {
  const errors = [];
  try {
    return require(name);
  } catch (error) {
    errors.push(`default resolution: ${String(error.message || error).split("\n")[0]}`);
  }
  for (const directory of moduleDirectories()) {
    try {
      return require(path.join(directory, name));
    } catch (error) {
      errors.push(`${directory}: ${String(error.message || error).split("\n")[0]}`);
    }
  }
  throw new Error(
    `Cannot load ${name}. Run through scripts/run_tool.sh, install pinned dependencies, `
    + `or set CODEX_NODE_MODULES. Attempts: ${errors.join(" | ")}`,
  );
}

export async function launchChromium(chromium, explicitPath = "") {
  const candidates = [
    explicitPath,
    process.env.CHROME_PATH,
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
  ].filter((value, index, values) =>
    value && values.indexOf(value) === index && existsSync(value));
  const errors = [];

  for (const executablePath of candidates) {
    try {
      return await chromium.launch({ headless: true, executablePath });
    } catch (error) {
      errors.push(`${executablePath}: ${String(error.message || error).split("\n")[0]}`);
    }
  }
  try {
    return await chromium.launch({ headless: true });
  } catch (error) {
    errors.push(`bundled Chromium: ${String(error.message || error).split("\n")[0]}`);
  }
  throw new Error(`Unable to launch Chromium. ${errors.join(" | ")}`);
}
