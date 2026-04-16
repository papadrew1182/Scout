#!/usr/bin/env node
/**
 * Scout Architecture Check
 *
 * Scans the repo for common dual-surface architecture violations:
 *   1. Backend mutation endpoints missing a permission/auth check
 *   2. Frontend admin-action calls missing a useHasPermission gate
 *   3. seedData constants still imported by app/ (INFO — migration targets)
 *   4. Permission key format violations (must match feature.action pattern)
 *
 * Usage:
 *   node scripts/architecture-check.js
 *
 * Exit codes:
 *   0 — no warnings
 *   1 — one or more warnings found
 *
 * Writes arch-check-report.json to repo root for CI artifact upload.
 *
 * Escape hatches:
 *   Backend endpoints that are genuinely public (no auth required) can
 *   suppress the warning by adding a comment on any line of the function:
 *     # noqa: public-route
 */

"use strict";

const fs = require("fs");
const path = require("path");

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

// Repo root is one level up from this script's directory (scripts/)
const REPO_ROOT = path.resolve(__dirname, "..");

const BACKEND_ROUTES_DIR = path.join(REPO_ROOT, "backend", "app", "routes");
const FRONTEND_APP_DIR = path.join(REPO_ROOT, "scout-ui", "app");
const SEED_DATA_FILE = path.join(REPO_ROOT, "scout-ui", "lib", "seedData.ts");

// Permission key regex: feature.action, both tokens lowercase underscore
const PERMISSION_KEY_RE = /^[a-z][a-z_]*\.[a-z][a-z_]*$/;

// Admin-level API functions whose callers should hold a useHasPermission gate.
// These represent state-mutating or governance operations.
const ADMIN_API_FUNCTIONS = [
  "createWeeklyPayout",
  "approveWeeklyPlan",
  "convertPurchaseRequestToGrocery",
  "putFamilyConfig",
  "putMemberConfig",
  "createMember",
  "updateMemberCore",
  "deleteGroceryItem",
  "fetchAllMemberConfigForKey",
  // updateGroceryItem is only admin when setting approval_status
  "updateGroceryItem",
  "resolveActionItem",
  "runAllowancePayout",
  "approveMealPlan",
  "generateMealPlan",
];

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function walkDir(dir, ext, results = []) {
  if (!fs.existsSync(dir)) return results;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name.startsWith(".")) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walkDir(full, ext, results);
    } else if (!ext || full.endsWith(ext)) {
      results.push(full);
    }
  }
  return results;
}

function readLines(filePath) {
  return fs.readFileSync(filePath, "utf8").split("\n");
}

function relPath(absPath) {
  return path.relative(REPO_ROOT, absPath).replace(/\\/g, "/");
}

// ---------------------------------------------------------------------------
// Check 1: Backend mutation endpoints missing permission checks
// ---------------------------------------------------------------------------

const MUTATION_DECORATOR_RE = /^\s*@router\.(post|put|patch|delete)\s*\(/i;
const PERMISSION_CHECK_RE = /actor\.(require_permission|require_adult)\s*\(/;
const NOQA_PUBLIC_RE = /#\s*noqa:\s*public-route/;
// Detects the start of the next function/class at the same indent level,
// used to bound how many lines we scan after a decorator.
const NEXT_TOP_LEVEL_RE = /^(def |class |@router\.)/;

function checkBackendMutationEndpoints() {
  const warnings = [];
  const pyFiles = walkDir(BACKEND_ROUTES_DIR, ".py");

  for (const filePath of pyFiles) {
    const lines = readLines(filePath);
    for (let i = 0; i < lines.length; i++) {
      if (!MUTATION_DECORATOR_RE.test(lines[i])) continue;

      const decoratorLine = i + 1; // 1-indexed
      // Scan forward up to 80 lines to find the function body
      // Stop at the next top-level definition (but not immediately — skip
      // stacked decorators and the `def` line itself)
      let foundPermission = false;
      let foundNoqa = false;
      let passedDef = false;

      for (let j = i + 1; j < Math.min(i + 80, lines.length); j++) {
        const line = lines[j];

        if (NOQA_PUBLIC_RE.test(line)) { foundNoqa = true; break; }
        if (PERMISSION_CHECK_RE.test(line)) { foundPermission = true; break; }

        // Once we've passed the function signature line (def ...), stop if
        // we hit another top-level item (next function/class/decorator)
        if (passedDef && NEXT_TOP_LEVEL_RE.test(line) && !line.startsWith("    ") && !line.startsWith("\t")) {
          break;
        }
        if (/^\s*def /.test(line)) passedDef = true;
      }

      if (!foundPermission && !foundNoqa) {
        warnings.push({
          type: "BACKEND_MISSING_PERMISSION",
          severity: "WARN",
          file: relPath(filePath),
          line: decoratorLine,
          message: `Mutation endpoint without permission check: ${relPath(filePath)}:${decoratorLine}`,
        });
      }
    }
  }
  return warnings;
}

// ---------------------------------------------------------------------------
// Check 2: Frontend admin-action calls missing useHasPermission gate
// ---------------------------------------------------------------------------

function checkFrontendAdminActions() {
  const warnings = [];
  const tsxFiles = walkDir(FRONTEND_APP_DIR, ".tsx");

  for (const filePath of tsxFiles) {
    const content = fs.readFileSync(filePath, "utf8");
    const hasGate = content.includes("useHasPermission(");

    const calledAdminFns = ADMIN_API_FUNCTIONS.filter((fn) => {
      // Match function call — either direct call or as onPress value
      const re = new RegExp(`\\b${fn}\\s*\\(`);
      return re.test(content);
    });

    if (calledAdminFns.length > 0 && !hasGate) {
      warnings.push({
        type: "FRONTEND_MISSING_GATE",
        severity: "WARN",
        file: relPath(filePath),
        line: null,
        message: `Admin action without permission gate: ${relPath(filePath)} (calls: ${calledAdminFns.join(", ")})`,
      });
    }
  }
  return warnings;
}

// ---------------------------------------------------------------------------
// Check 3: seedData exports still imported by app/ (INFO — migration targets)
// ---------------------------------------------------------------------------

function checkSeedDataDrift() {
  const infos = [];
  if (!fs.existsSync(SEED_DATA_FILE)) return infos;

  const seedContent = fs.readFileSync(SEED_DATA_FILE, "utf8");
  // Extract all export const NAME identifiers
  const exportRe = /^export\s+(?:const|type|interface|enum|function)\s+([A-Z_][A-Z0-9_]*)/gm;
  const exportedNames = [];
  let m;
  while ((m = exportRe.exec(seedContent)) !== null) {
    exportedNames.push(m[1]);
  }

  if (exportedNames.length === 0) return infos;

  const tsxFiles = walkDir(FRONTEND_APP_DIR, ".tsx");
  const tsFiles = walkDir(path.join(REPO_ROOT, "scout-ui", "app"), ".ts");
  const allFiles = [...tsxFiles, ...tsFiles];

  const stillImported = new Set();
  for (const filePath of allFiles) {
    const content = fs.readFileSync(filePath, "utf8");
    if (!content.includes("seedData")) continue;
    for (const name of exportedNames) {
      if (content.includes(name)) {
        stillImported.add(name);
      }
    }
  }

  if (stillImported.size > 0) {
    infos.push({
      type: "SEED_DATA_DRIFT",
      severity: "INFO",
      file: relPath(SEED_DATA_FILE),
      line: null,
      message: `seedData constants still imported by app/ (de-hardcode targets): ${[...stillImported].sort().join(", ")}`,
    });
  }
  return infos;
}

// ---------------------------------------------------------------------------
// Check 4: Permission key format violations
// ---------------------------------------------------------------------------

// Matches: actor.require_permission("some.key") or useHasPermission("some.key")
const PERM_KEY_EXTRACT_RE = /(?:require_permission|useHasPermission)\(\s*["']([^"']+)["']/g;

function checkPermissionKeyFormat() {
  const warnings = [];

  const pyFiles = walkDir(BACKEND_ROUTES_DIR, ".py");
  const serviceDir = path.join(REPO_ROOT, "backend", "app", "services");
  const serviceFiles = walkDir(serviceDir, ".py");

  const libDir = path.join(REPO_ROOT, "scout-ui", "lib");
  const libTsFiles = walkDir(libDir, ".ts");
  const appTsxFiles = walkDir(FRONTEND_APP_DIR, ".tsx");
  const appTsFiles = walkDir(FRONTEND_APP_DIR, ".ts");

  const allFiles = [
    ...pyFiles,
    ...serviceFiles,
    ...libTsFiles,
    ...appTsxFiles,
    ...appTsFiles,
  ];

  for (const filePath of allFiles) {
    const content = fs.readFileSync(filePath, "utf8");
    let match;
    PERM_KEY_EXTRACT_RE.lastIndex = 0;
    while ((match = PERM_KEY_EXTRACT_RE.exec(content)) !== null) {
      const key = match[1];
      if (!PERMISSION_KEY_RE.test(key)) {
        // Find approximate line number
        const upTo = content.slice(0, match.index);
        const lineNum = upTo.split("\n").length;
        warnings.push({
          type: "PERMISSION_KEY_FORMAT",
          severity: "WARN",
          file: relPath(filePath),
          line: lineNum,
          message: `Permission key does not match feature.action format: "${key}" in ${relPath(filePath)}:${lineNum}`,
        });
      }
    }
  }
  return warnings;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function main() {
  console.log("Scout Architecture Check");
  console.log("========================\n");

  const backendWarnings = checkBackendMutationEndpoints();
  const frontendWarnings = checkFrontendAdminActions();
  const seedInfos = checkSeedDataDrift();
  const keyFormatWarnings = checkPermissionKeyFormat();

  const allEntries = [
    ...backendWarnings,
    ...frontendWarnings,
    ...seedInfos,
    ...keyFormatWarnings,
  ];

  const warnings = allEntries.filter((e) => e.severity === "WARN");
  const infos = allEntries.filter((e) => e.severity === "INFO");

  // Print results grouped by check type
  const groups = {
    BACKEND_MISSING_PERMISSION: "Check 1: Backend mutation endpoints missing permission check",
    FRONTEND_MISSING_GATE: "Check 2: Frontend admin actions missing useHasPermission gate",
    SEED_DATA_DRIFT: "Check 3: seedData drift (de-hardcode targets — INFO only)",
    PERMISSION_KEY_FORMAT: "Check 4: Permission key format violations",
  };

  for (const [type, label] of Object.entries(groups)) {
    const entries = allEntries.filter((e) => e.type === type);
    if (entries.length === 0) {
      console.log(`[OK]  ${label}`);
    } else {
      const isInfo = entries[0].severity === "INFO";
      console.log(`\n[${isInfo ? "INFO" : "WARN"}] ${label}:`);
      for (const entry of entries) {
        const prefix = entry.severity === "INFO" ? "  INFO " : "  WARN ";
        console.log(`${prefix} ${entry.message}`);
      }
    }
  }

  console.log("\n---");
  console.log(`Warnings: ${warnings.length}  |  Info: ${infos.length}`);

  // Write JSON report
  const report = {
    timestamp: new Date().toISOString(),
    summary: {
      warnings: warnings.length,
      infos: infos.length,
      passed: warnings.length === 0,
    },
    entries: allEntries,
  };

  const reportPath = path.join(REPO_ROOT, "arch-check-report.json");
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
  console.log(`\nReport written to: ${path.relative(process.cwd(), reportPath)}`);

  if (warnings.length > 0) {
    console.log(
      "\nFix warnings before merge. For genuinely public backend endpoints,\n" +
        "add a comment `# noqa: public-route` in the function body to suppress."
    );
    process.exit(1);
  } else {
    console.log("\nAll checks passed.");
    process.exit(0);
  }
}

main();
