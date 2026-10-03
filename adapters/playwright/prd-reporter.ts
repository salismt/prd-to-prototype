import type { FullConfig, FullResult, Reporter, TestCase, TestResult } from '@playwright/test/reporter';
import { execSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { acIds, SCREEN_ANNOTATION } from './screens';

export interface PrdReporterOptions {
  /** Results JSON path, relative to the config file (or absolute). */
  outputFile: string;
  /** Root every artifact path in the results is relative to. Pass the same value to check_coverage.py. */
  artifactRoot: string;
  /** Directory under artifactRoot that receives `<AC>/` artifact folders. Wiped at run start. */
  evidenceDir: string;
  prdId: string;
  /** Defaults to env PROTOTYPE_VERSION, else git short SHA of artifactRoot, else "unversioned". */
  prototypeVersion?: string;
}

interface Row {
  id: string;
  status: TestResult['status'];
  entry_screen: string | null;
  visited_screens: string[];
  recording: string | null;
  screenshots: string[];
  error?: string;
}

export default class PrdReporter implements Reporter {
  private readonly opts: PrdReporterOptions;
  private configDir = process.cwd();
  private runnerVersion = 'unknown';
  private startedAt = '';
  private final = new Map<string, { test: TestCase; result: TestResult }>();

  constructor(opts: PrdReporterOptions) {
    for (const k of ['outputFile', 'artifactRoot', 'evidenceDir', 'prdId'] as const) {
      if (!opts?.[k]) throw new Error(`prd-reporter: option "${k}" is required`);
    }
    const rel = path.normalize(opts.evidenceDir);
    if (path.isAbsolute(rel) || rel === '.' || rel.split(path.sep)[0] === '..') {
      throw new Error('prd-reporter: "evidenceDir" must be a subdirectory of artifactRoot (it is wiped at run start)');
    }
    this.opts = opts;
  }

  printsToStdio() {
    return false;
  }

  onBegin(config: FullConfig) {
    this.configDir = config.configFile ? path.dirname(config.configFile) : process.cwd();
    this.runnerVersion = config.version;
    this.startedAt = new Date().toISOString();
    fs.rmSync(this.evidencePath(), { recursive: true, force: true });
  }

  onTestEnd(test: TestCase, result: TestResult) {
    this.final.set(test.id, { test, result }); // retries overwrite: last attempt wins
  }

  async onEnd(_: FullResult) {
    const results: Row[] = [];
    let tagError = false;
    for (const { test, result } of this.final.values()) {
      const ids = acIds(test.tags);
      if (ids.length !== 1) {
        tagError = true;
        const msg = `prd-reporter: "${test.title}" must carry exactly one @AC-<id> tag, found [${test.tags.join(', ')}]`;
        console.error(msg);
        results.push({ id: ids.join('+') || 'untagged', status: 'failed', entry_screen: null, visited_screens: [], recording: null, screenshots: [], error: msg });
        continue;
      }
      results.push(this.row(ids[0], result));
    }
    results.sort((a, b) => a.id.localeCompare(b.id));

    const out = {
      prd_id: this.opts.prdId,
      prototype_version: this.prototypeVersion(),
      run_started_at: this.startedAt,
      runner: { name: 'playwright', version: this.runnerVersion },
      results,
      review: { status: 'pending' },
    };
    const file = path.resolve(this.configDir, this.opts.outputFile);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, JSON.stringify(out, null, 2) + '\n');
    if (tagError) return { status: 'failed' as const };
  }

  private row(id: string, result: TestResult): Row {
    const visited: string[] = [];
    for (const a of result.annotations ?? []) {
      if (a.type === SCREEN_ANNOTATION && a.description && !visited.includes(a.description)) visited.push(a.description);
    }
    const dir = path.join(this.evidencePath(), id);
    fs.mkdirSync(dir, { recursive: true });
    const taken = new Set(fs.readdirSync(dir));
    let recording: string | null = null;
    const screenshots: string[] = [];
    for (const a of result.attachments) {
      const isTrace = a.name === 'trace' && a.contentType === 'application/zip';
      const isShot = a.contentType === 'image/png' && a.name.startsWith(`${id}-`);
      if (!isTrace && !isShot) continue;
      const name = unique(isTrace ? 'trace.zip' : a.name, taken);
      const dest = path.join(dir, name);
      if (a.path) fs.copyFileSync(a.path, dest);
      else if (a.body) fs.writeFileSync(dest, a.body);
      else continue;
      const rel = path.relative(this.artifactRootPath(), dest).split(path.sep).join('/');
      if (isTrace) recording = rel;
      else screenshots.push(rel);
    }
    return { id, status: result.status, entry_screen: visited[0] ?? null, visited_screens: visited, recording, screenshots };
  }

  private artifactRootPath() {
    return path.resolve(this.configDir, this.opts.artifactRoot);
  }

  private evidencePath() {
    return path.join(this.artifactRootPath(), this.opts.evidenceDir);
  }

  private prototypeVersion(): string {
    if (this.opts.prototypeVersion) return this.opts.prototypeVersion;
    if (process.env.PROTOTYPE_VERSION) return process.env.PROTOTYPE_VERSION;
    try {
      return execSync('git rev-parse --short HEAD', { cwd: this.artifactRootPath(), stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim();
    } catch {
      return 'unversioned';
    }
  }
}

function unique(name: string, taken: Set<string>): string {
  const ext = path.extname(name);
  const base = name.slice(0, -ext.length || undefined);
  let candidate = name;
  for (let n = 2; taken.has(candidate); n++) candidate = `${base}-${n}${ext}`;
  taken.add(candidate);
  return candidate;
}
