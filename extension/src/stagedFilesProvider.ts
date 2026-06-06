/**
 * stagedFilesProvider.ts — TreeDataProvider for the GitPhone sidebar panel.
 *
 * Shows all staged files from the backend, grouped by change type.
 * Clicking a file shows an inline diff vs. the current local version.
 */

import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import axios from 'axios';
import { getConfig, isConfigured } from './config';

// ── Data Models ───────────────────────────────────────────────────────────────

export interface StagedFile {
  id: string;
  filepath: string;
  file_size: number;
  is_binary: boolean;
  staged_at: string;
  status: 'pending' | 'committed';
  change_type?: 'create' | 'modify' | 'delete';
  diff?: string;
  repo?: string;
}

// ── Tree Item ─────────────────────────────────────────────────────────────────

export class StagedFileItem extends vscode.TreeItem {
  constructor(
    public readonly file: StagedFile,
    public readonly collapsibleState: vscode.TreeItemCollapsibleState,
  ) {
    super(file.filepath, collapsibleState);

    const parts = file.filepath.replace(/\\/g, '/').split('/');
    this.label = parts[parts.length - 1];
    this.description = parts.slice(0, -1).join('/') || '';

    const changeLabel =
      file.change_type === 'create' ? '➕ New' :
      file.change_type === 'delete' ? '🗑️ Deleted' :
      '✏️ Modified';

    this.tooltip = new vscode.MarkdownString(
      `**${file.filepath}**\n\n` +
      `${changeLabel}  •  ${_formatSize(file.file_size)}\n\n` +
      `Staged: ${_timeAgo(file.staged_at)}\n\n` +
      `_Click to view diff_`
    );

    // Icon differs by change type
    if (file.change_type === 'create') {
      this.iconPath = new vscode.ThemeIcon('diff-added', new vscode.ThemeColor('gitDecoration.addedResourceForeground'));
    } else if (file.change_type === 'delete') {
      this.iconPath = new vscode.ThemeIcon('diff-removed', new vscode.ThemeColor('gitDecoration.deletedResourceForeground'));
    } else {
      this.iconPath = file.is_binary
        ? new vscode.ThemeIcon('file-binary', new vscode.ThemeColor('gitDecoration.modifiedResourceForeground'))
        : new vscode.ThemeIcon('diff-modified', new vscode.ThemeColor('gitDecoration.modifiedResourceForeground'));
    }

    this.contextValue = 'stagedFile';

    // Click → show diff
    this.command = {
      command: 'gitphone.showDiff',
      title: 'Show Diff',
      arguments: [file],
    };
  }
}

export class MessageItem extends vscode.TreeItem {
  constructor(label: string, icon: string) {
    super(label, vscode.TreeItemCollapsibleState.None);
    this.iconPath = new vscode.ThemeIcon(icon);
    this.contextValue = 'message';
  }
}

// ── Provider ─────────────────────────────────────────────────────────────────

export class StagedFilesProvider implements vscode.TreeDataProvider<vscode.TreeItem> {
  private _onDidChangeTreeData = new vscode.EventEmitter<vscode.TreeItem | undefined | null>();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  private _stagedFiles: StagedFile[] = [];
  private _loading = false;
  private _error: string | null = null;
  private _lastRefresh: Date | null = null;
  private _refreshTimer: ReturnType<typeof setInterval> | undefined;

  constructor() {
    // Auto-refresh every 30 seconds
    this._refreshTimer = setInterval(() => {
      this.refresh();
    }, 30_000);
  }

  dispose() {
    if (this._refreshTimer) clearInterval(this._refreshTimer);
    this._onDidChangeTreeData.dispose();
  }

  refresh(): void {
    this._lastRefresh = null; // force re-fetch
    this._onDidChangeTreeData.fire(undefined);
  }

  getTreeItem(element: vscode.TreeItem): vscode.TreeItem {
    return element;
  }

  async getChildren(element?: vscode.TreeItem): Promise<vscode.TreeItem[]> {
    if (element) return [];

    if (!isConfigured()) {
      return [new MessageItem('Not configured — click ⚙ Setup', 'warning')];
    }

    await this._fetchStagedFiles();

    if (this._loading) {
      return [new MessageItem('Loading...', 'loading~spin')];
    }

    if (this._error) {
      return [new MessageItem(`Error: ${this._error}`, 'error')];
    }

    if (this._stagedFiles.length === 0) {
      return [
        new MessageItem('No files staged yet', 'inbox'),
        new MessageItem('Save a file in VS Code to stage it', 'info'),
      ];
    }

    return this._stagedFiles.map(
      (f) => new StagedFileItem(f, vscode.TreeItemCollapsibleState.None),
    );
  }

  get stagedCount(): number {
    return this._stagedFiles.length;
  }

  get stagedFiles(): StagedFile[] {
    return [...this._stagedFiles];
  }

  removeFile(fileId: string): void {
    this._stagedFiles = this._stagedFiles.filter((f) => f.id !== fileId);
    this._onDidChangeTreeData.fire(undefined);
  }

  clearAll(): void {
    this._stagedFiles = [];
    this._onDidChangeTreeData.fire(undefined);
  }

  upsertFile(file: StagedFile): void {
    const idx = this._stagedFiles.findIndex((f) => f.filepath === file.filepath);
    if (idx >= 0) {
      this._stagedFiles[idx] = file;
    } else {
      this._stagedFiles.push(file);
    }
    this._onDidChangeTreeData.fire(undefined);
  }

  // ── Private ────────────────────────────────────────────────────────────────

  private async _fetchStagedFiles(): Promise<void> {
    const config = getConfig();
    if (!config) return;

    // Debounce: skip if fetched within 3s
    if (this._lastRefresh && Date.now() - this._lastRefresh.getTime() < 3_000) {
      return;
    }

    this._loading = true;
    this._error = null;

    try {
      const response = await axios.get(
        `${config.backendUrl}/staged-files/${config.telegramId}`,
        {
          timeout: 8_000,
          headers: {
            'X-Telegram-Id': config.telegramId,
            'X-Api-Key': config.apiKey ?? '',
          },
        },
      );
      this._stagedFiles = response.data?.files ?? [];
      this._lastRefresh = new Date();
    } catch (err: any) {
      this._error = err?.response?.data?.detail ?? 'Cannot reach backend';
      this._stagedFiles = [];
    } finally {
      this._loading = false;
    }
  }
}

// ── Diff View Helpers ─────────────────────────────────────────────────────────

/**
 * Show an inline VS Code diff for a staged file.
 * Left = current local disk version, Right = staged (what will be committed).
 */
export async function showStagedDiff(
  file: StagedFile,
  context: vscode.ExtensionContext,
): Promise<void> {
  const workspaceFolders = vscode.workspace.workspaceFolders;
  if (!workspaceFolders) {
    vscode.window.showWarningMessage('No workspace open.');
    return;
  }

  const workspaceRoot = workspaceFolders[0].uri.fsPath;
  const localPath = path.join(workspaceRoot, file.filepath);

  if (file.change_type === 'delete') {
    // Deleted file — show a message, nothing to diff
    vscode.window.showInformationMessage(
      `🗑️ "${file.filepath}" is staged for deletion. It will be removed from GitHub on commit.`,
      'OK'
    );
    return;
  }

  // Read current local file content
  let localContent = '';
  try {
    if (fs.existsSync(localPath)) {
      localContent = fs.readFileSync(localPath, 'utf8');
    }
  } catch {
    localContent = '';
  }

  // For new files: "before" is empty
  // For modifications: "before" is the current local file (what exists now)
  // "after" = the staged diff applied to the before content
  let stagedContent = localContent; // fallback: same as local (no diff available)

  if (file.diff) {
    // Apply the staged diff to reconstruct what will be committed
    try {
      stagedContent = applyUnifiedDiff(
        file.change_type === 'create' ? '' : localContent,
        file.diff
      );
    } catch {
      // If diff apply fails, show the raw diff text
      stagedContent = file.diff;
    }
  }

  // Create virtual documents for diff view
  const scheme = 'gitphone-staged';
  const beforeLabel = file.change_type === 'create' ? '(new file)' : file.filepath;
  const afterLabel = `${file.filepath} (staged)`;

  // Register a simple content provider
  const provider = vscode.workspace.registerTextDocumentContentProvider(scheme, {
    provideTextDocumentContent(uri: vscode.Uri): string {
      const which = uri.query;
      return which === 'before'
        ? (file.change_type === 'create' ? '' : localContent)
        : stagedContent;
    },
  });

  const beforeUri = vscode.Uri.parse(`${scheme}:${encodeURIComponent(beforeLabel)}?before`);
  const afterUri  = vscode.Uri.parse(`${scheme}:${encodeURIComponent(afterLabel)}?after`);

  try {
    const changeIcon = file.change_type === 'create' ? '➕' : '✏️';
    await vscode.commands.executeCommand(
      'vscode.diff',
      beforeUri,
      afterUri,
      `${changeIcon} GitPhone: ${path.basename(file.filepath)}`,
      { preview: true },
    );
  } finally {
    // Dispose the provider after a short delay
    setTimeout(() => provider.dispose(), 5000);
  }
}

/**
 * Minimal unified diff applier — handles simple +/- line diffs.
 * Falls back gracefully if the diff is malformed.
 */
function applyUnifiedDiff(original: string, diff: string): string {
  try {
    const origLines = original.split('\n');
    const result: string[] = [];
    let origIdx = 0;

    const diffLines = diff.split('\n');
    let i = 0;

    // Skip header lines (---, +++, @@...@@)
    while (i < diffLines.length && !diffLines[i].startsWith('@@')) i++;

    for (; i < diffLines.length; i++) {
      const line = diffLines[i];
      if (line.startsWith('@@')) {
        // Parse hunk header: @@ -a,b +c,d @@
        const match = line.match(/@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@/);
        if (match) {
          const oldStart = parseInt(match[1]) - 1;
          // Copy unchanged lines up to this hunk
          while (origIdx < oldStart) {
            result.push(origLines[origIdx++]);
          }
        }
      } else if (line.startsWith('-')) {
        // Remove line from original
        origIdx++;
      } else if (line.startsWith('+')) {
        // Add new line
        result.push(line.slice(1));
      } else if (line.startsWith(' ') || line === '') {
        // Context line — keep from original
        if (origIdx < origLines.length) {
          result.push(origLines[origIdx++]);
        }
      }
    }

    // Append remaining original lines
    while (origIdx < origLines.length) {
      result.push(origLines[origIdx++]);
    }

    return result.join('\n');
  } catch {
    return original; // fallback
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function _formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

function _timeAgo(iso: string): string {
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const s = Math.floor(diff / 1000);
    if (s < 60) return 'just now';
    if (s < 3600) return `${Math.floor(s / 60)}m ago`;
    if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
    return `${Math.floor(s / 86400)}d ago`;
  } catch {
    return '';
  }
}
