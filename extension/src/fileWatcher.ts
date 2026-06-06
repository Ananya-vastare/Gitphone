/**
 * fileWatcher.ts â€” Watches for file saves and syncs diffs to the backend.
 * Auto-detects the git remote repo and sends it with every sync payload.
 */

import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';

import { isConfigured, getConfig } from './config';
import { getContent, getSha } from './localCache';
import { detectBinary, detectMinified, normalizeLineEndings, computeDiff } from './diffEngine';
import { syncFile, extractErrorMessage } from './api';
import { setSyncing, setConnected, setError, increment } from './statusBar';

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

let _stagedCount = 0;

// â”€â”€ Git Remote Detection â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

/**
 * Reads .git/config to detect the GitHub remote URL.
 * Returns "owner/repo" or null if not a GitHub repo.
 */
function detectGitRepo(workspaceRoot: string): { repo: string; branch: string } | null {
  try {
    // Read .git/config
    const gitConfigPath = path.join(workspaceRoot, '.git', 'config');
    if (!fs.existsSync(gitConfigPath)) return null;

    const configContent = fs.readFileSync(gitConfigPath, 'utf8');

    // Extract GitHub remote URL (supports https and ssh)
    // https://github.com/owner/repo.git
    // git@github.com:owner/repo.git
    const httpsMatch = configContent.match(/url\s*=\s*https:\/\/github\.com\/([^\/\s]+\/[^\s\.]+)/i);
    const sshMatch   = configContent.match(/url\s*=\s*git@github\.com:([^\/\s]+\/[^\s\.]+)/i);

    const repoMatch = httpsMatch?.[1] || sshMatch?.[1];
    if (!repoMatch) return null;

    // Normalize: strip trailing .git if present
    const repo = repoMatch.replace(/\.git$/, '');

    // Read current branch from HEAD
    let branch = 'main';
    const headPath = path.join(workspaceRoot, '.git', 'HEAD');
    if (fs.existsSync(headPath)) {
      const headContent = fs.readFileSync(headPath, 'utf8').trim();
      const branchMatch = headContent.match(/^ref: refs\/heads\/(.+)$/);
      if (branchMatch) branch = branchMatch[1];
    }

    return { repo, branch };
  } catch {
    return null;
  }
}

// â”€â”€ Cache detected repo per workspace root (avoid re-reading on every save) â”€â”€
const _repoCache = new Map<string, { repo: string; branch: string; ts: number }>();

function getCachedGitRepo(workspaceRoot: string): { repo: string; branch: string } | null {
  const cached = _repoCache.get(workspaceRoot);
  // Cache for 30 seconds â€” branch can change so we re-check periodically
  if (cached && Date.now() - cached.ts < 30_000) {
    return { repo: cached.repo, branch: cached.branch };
  }
  const detected = detectGitRepo(workspaceRoot);
  if (detected) {
    _repoCache.set(workspaceRoot, { ...detected, ts: Date.now() });
  }
  return detected;
}

// â”€â”€ Main file-save handler â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

/**
 * Called on every file save event.
 * Computes diff and POSTs to /sync-file with auto-detected repo.
 */
export async function onFileSaved(document: vscode.TextDocument): Promise<void> {
  if (!isConfigured()) return;

  const config = getConfig()!;
  const filePath = document.uri.fsPath;

  const workspaceFolders = vscode.workspace.workspaceFolders;
  if (!workspaceFolders || workspaceFolders.length === 0) return;
  const workspaceRoot = workspaceFolders[0].uri.fsPath;

  if (!filePath.startsWith(workspaceRoot)) return;

  const relativePath = path.relative(workspaceRoot, filePath).replace(/\\/g, '/');

  if (shouldIgnore(relativePath)) return;

  let stats: fs.Stats;
  try {
    stats = fs.statSync(filePath);
  } catch {
    return;
  }

  if (stats.size > MAX_FILE_SIZE) {
    const sizeMB = (stats.size / (1024 * 1024)).toFixed(1);
    vscode.window.showWarningMessage(
      `âš ï¸ GitPhone: ${path.basename(relativePath)} skipped (${sizeMB}MB). Exceeds 10MB limit.`
    );
    return;
  }

  const isBinary = detectBinary(filePath);
  const isMinified = detectMinified(relativePath);

  let diffText: string | null = null;
  let fullContent: string | null = null;

  if (isBinary || isMinified) {
    try {
      const rawBytes = fs.readFileSync(filePath);
      fullContent = rawBytes.toString('base64');
    } catch (err) {
      console.error(`[GitPhone] Failed to read binary file: ${err}`);
      return;
    }
  } else {
    let rawContent: string;
    try {
      rawContent = fs.readFileSync(filePath, 'utf8');
    } catch (err) {
      console.error(`[GitPhone] Failed to read file: ${err}`);
      return;
    }

    const normalizedNew = normalizeLineEndings(rawContent);
    const cachedContent = getContent(relativePath) ?? '';
    const normalizedOld = normalizeLineEndings(cachedContent);

    diffText = computeDiff(normalizedOld, normalizedNew, relativePath);
    if (!diffText) return; // No changes
  }

  const baseSha = getSha(relativePath) ?? 'new_file';

  // ── Auto-detect git repo & branch ──────────────────────────────────────────
  const gitInfo = getCachedGitRepo(workspaceRoot);
  const activeRepo   = gitInfo?.repo   || config.defaultRepo || undefined;
  const activeBranch = gitInfo?.branch || config.branch     || undefined;

  setSyncing();
  console.log(`[GitPhone] Syncing ${relativePath} → ${activeRepo ?? 'unknown repo'} [modify]`);

  try {
    await syncFile({
      telegram_id: config.telegramId,
      filepath: relativePath,
      diff: diffText,
      full_content: fullContent,
      base_sha: baseSha,
      is_binary: isBinary,
      file_size: stats.size,
      active_repo: activeRepo,
      active_branch: activeBranch,
      change_type: 'modify',
    });

    _stagedCount++;
    setConnected(_stagedCount);
    increment();

  } catch (err) {
    const message = extractErrorMessage(err);
    console.error(`[GitPhone] Sync failed for ${relativePath}: ${message}`);
    setError(`Sync failed: ${message}`);

    vscode.window.showWarningMessage(
      `GitPhone: Failed to stage "${path.basename(relativePath)}" â€” ${message}`,
      'Open Setup',
    ).then(choice => {
      if (choice === 'Open Setup') {
        vscode.commands.executeCommand('gitphone.openSetup');
      }
    });

    setTimeout(() => setConnected(_stagedCount), 3000);
  }
}

export function resetStagedCount(count: number = 0): void {
  _stagedCount = count;
  setConnected(_stagedCount);
}

function shouldIgnore(relativePath: string): boolean {
  const ignoredPrefixes = [
    '.git/', 'node_modules/', '.next/', '__pycache__/',
    '.venv/', 'venv/', 'dist/', 'build/', '.DS_Store',
  ];
  const ignoredExtensions = ['.log', '.lock'];

  for (const prefix of ignoredPrefixes) {
    if (relativePath.startsWith(prefix) || relativePath.includes(`/${prefix}`)) return true;
  }
  for (const ext of ignoredExtensions) {
    if (relativePath.endsWith(ext)) return true;
  }
  return false;
}


// ── onFileCreated — handles new files added to workspace ─────────────────────

/**
 * Called by onDidCreateFiles.
 * Sends the full file content as a "create" type staged entry.
 * Skips ignored paths, binaries, and files > 10MB.
 */
export async function onFileCreated(uri: vscode.Uri): Promise<void> {
  if (!isConfigured()) return;
  const config = getConfig()!;

  const workspaceFolders = vscode.workspace.workspaceFolders;
  if (!workspaceFolders || workspaceFolders.length === 0) return;
  const workspaceRoot = workspaceFolders[0].uri.fsPath;

  const filePath = uri.fsPath;
  if (!filePath.startsWith(workspaceRoot)) return;

  const relativePath = path.relative(workspaceRoot, filePath).replace(/\\/g, '/');
  if (shouldIgnore(relativePath)) return;

  // Skip directories
  try {
    const stat = fs.statSync(filePath);
    if (stat.isDirectory()) return;
    if (stat.size > MAX_FILE_SIZE) return;
  } catch {
    return; // File may have been deleted between create and handler
  }

  const gitInfo = getCachedGitRepo(workspaceRoot);
  const activeRepo   = gitInfo?.repo   || config.defaultRepo || undefined;
  const activeBranch = gitInfo?.branch || config.branch     || undefined;

  // Read full content (new file — no diff to compute)
  let fullContent: string | null = null;
  let diffText: string | null = null;
  const isBinary = detectBinary(filePath);

  try {
    if (isBinary) {
      fullContent = fs.readFileSync(filePath).toString('base64');
    } else {
      const rawContent = fs.readFileSync(filePath, 'utf8');
      const normalizedNew = normalizeLineEndings(rawContent);
      // For a brand new file the old content is empty — diff shows all lines as additions
      diffText = computeDiff('', normalizedNew, relativePath);
      if (!diffText && !normalizedNew) return; // Truly empty file — skip
      if (!diffText) {
        // computeDiff returned null for an empty-to-something diff — use full content
        fullContent = Buffer.from(rawContent).toString('base64');
      }
    }
  } catch (err) {
    console.error(`[GitPhone] Failed to read created file: ${err}`);
    return;
  }

  if (!diffText && !fullContent) return;

  setSyncing();
  console.log(`[GitPhone] Staging new file: ${relativePath}`);

  try {
    const stat = fs.statSync(filePath);
    await syncFile({
      telegram_id: config.telegramId,
      filepath: relativePath,
      diff: diffText,
      full_content: fullContent,
      base_sha: 'new_file',
      is_binary: isBinary,
      file_size: stat.size,
      active_repo: activeRepo,
      active_branch: activeBranch,
      change_type: 'create',
    });
    setConnected(++_stagedCount);
    increment();
  } catch (err) {
    console.error(`[GitPhone] Failed to stage created file: ${extractErrorMessage(err)}`);
    setError(`Create failed: ${extractErrorMessage(err)}`);
    setTimeout(() => setConnected(_stagedCount), 3000);
  }
}


// ── onFileDeleted — handles files removed from workspace ─────────────────────

/**
 * Called by onDidDeleteFiles.
 * Sends a "delete" type staged entry. No content needed — the bot will
 * call GitHub's delete blob API when committing.
 */
export async function onFileDeleted(uri: vscode.Uri): Promise<void> {
  if (!isConfigured()) return;
  const config = getConfig()!;

  const workspaceFolders = vscode.workspace.workspaceFolders;
  if (!workspaceFolders || workspaceFolders.length === 0) return;
  const workspaceRoot = workspaceFolders[0].uri.fsPath;

  const filePath = uri.fsPath;
  if (!filePath.startsWith(workspaceRoot)) return;

  const relativePath = path.relative(workspaceRoot, filePath).replace(/\\/g, '/');
  if (shouldIgnore(relativePath)) return;

  const gitInfo = getCachedGitRepo(workspaceRoot);
  const activeRepo   = gitInfo?.repo   || config.defaultRepo || undefined;
  const activeBranch = gitInfo?.branch || config.branch     || undefined;

  setSyncing();
  console.log(`[GitPhone] Staging deletion: ${relativePath}`);

  try {
    await syncFile({
      telegram_id: config.telegramId,
      filepath: relativePath,
      diff: null,
      full_content: null,
      base_sha: 'delete',          // sentinel value — tells backend this is a deletion
      is_binary: false,
      file_size: 0,
      active_repo: activeRepo,
      active_branch: activeBranch,
      change_type: 'delete',
    });
    setConnected(++_stagedCount);
    increment();
  } catch (err) {
    console.error(`[GitPhone] Failed to stage deletion: ${extractErrorMessage(err)}`);
    setError(`Delete stage failed: ${extractErrorMessage(err)}`);
    setTimeout(() => setConnected(_stagedCount), 3000);
  }
}


// ── onFileRenamed — convenience export (extension.ts uses delete+create) ──────
export async function onFileRenamed(
  oldUri: vscode.Uri,
  newUri: vscode.Uri
): Promise<void> {
  await onFileDeleted(oldUri);
  await onFileCreated(newUri);
}

