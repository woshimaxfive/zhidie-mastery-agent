import { rmSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";


export default async function globalTeardown() {
  const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
  const dataRoot = path.resolve(frontendRoot, "..", "backend", "data");
  const databasePath = path.join(dataRoot, "playwright-e2e.db");

  if (path.dirname(databasePath) !== dataRoot || path.basename(databasePath) !== "playwright-e2e.db") {
    throw new Error("Unexpected browser-test database path.");
  }
  rmSync(databasePath, { force: true });
}
