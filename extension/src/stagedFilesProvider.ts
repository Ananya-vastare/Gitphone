/**
 * stagedFilesProvider.ts — TreeDataProvider for the GitPhone sidebar panel.
 *
 * Shows all staged files fetched from the backend.
 * Users can manually unstage files or refresh the list.
 */

import * as vscode from 'vscode';
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
}

// ── Tree Item ─────────────────────────────────────────────────────────────────

export class StagedFileItem extends vscode.TreeItem {
  constructor(
    public readonly file: StagedFile,
    public readonly collapsibleState: vscode.TreeItemCollapsibleState,
  ) {
    super(file.filepath, collapsibleState);

    // Show just the filename as label, full path as description
    const parts = file.filepath.replace(/\\/g, '/').split('/');
    this.label = parts[parts.length - 1];
    this.description = parts.slice(0, -1).join('/') || '';

    this.tooltip = `${file.filepath}\n${_formatSize(file.file_size)}\nStaged: ${_timeAgo(file.staged_at)}`;
    this.iconPath = file.is_binary
      ? new vscode.ThemeIcon('file-binary', new vscode.ThemeColor('gitDecoration.modifiedResourceForeground'))
      : new vscode.ThemeIcon('file-code', new vscode.ThemeColor('gitDecoration.modifiedResourceForeground'));

    this.contextValue = 'stagedFile';

    // Command: clicking opens the file if it exists locally
    this.command = {
      command: 'gitphone.openStagedFile',
      title: 'Open File',
      arguments: [file.filepath],
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

  // Auto-refresh interval handle
  private _refreshTimer: NodeJS.Timer | undefined;

  constructor() {
    // Auto-refresh every 30 seconds when panel is visible
    this._refreshTimer = setInterval(() => {
      this.refresh();
    }, 30_000);
  }

  dispose() {
    if (this._refreshTimer) {
      clearInterval(this._refreshTimer as NodeJS.Timeout);
    }
    this._onDidChangeTreeData.dispose();
  }

  /** Force a refresh from the backend */
  refresh(): void {
    this._onDidChangeTreeData.fire(undefined);
  }

  /** Called by VS Code to get root items or children */
  getTreeItem(element: vscode.TreeItem): vscode.TreeItem {
    return element;
  }

  async getChildren(element?: vscode.TreeItem): Promise<vscode.TreeItem[]> {
    if (element) return []; // flat list, no nesting

    if (!isConfigured()) {
      return [
        new MessageItem('Not configured — click ⚙ Setup', 'warning'),
      ];
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

  /** Get current staged count for status bar */
  get stagedCount(): number {
    return this._stagedFiles.length;
  }

  /** Remove a file from local list immediately (optimistic update) */
  removeFile(fileId: string): void {
    this._stagedFiles = this._stagedFiles.filter((f) => f.id !== fileId);
    this._onDidChangeTreeData.fire(undefined);
  }

  /** Add/update a file in the local list (called after a save sync) */
  upsertFile(file: StagedFile): void {
    const idx = this._stagedFiles.findIndex(
      (f) => f.filepath === file.filepath,
    );
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

    // Skip if fetched within last 5 seconds (avoid hammering)
    if (
      this._lastRefresh &&
      Date.now() - this._lastRefresh.getTime() < 5_000
    ) {
      return;
    }

    this._loading = true;
    this._error = null;

    try {
      const response = await axios.get(
        `${config.backendUrl}/staged-files/${config.telegramId}`,
        { timeout: 8_000 },
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
