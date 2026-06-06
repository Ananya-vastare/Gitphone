import * as vscode from 'vscode';
import { initConfig, isConfigured, getConfig } from './config';
import { initCache, clearAll as clearCache } from './localCache';
import { initStatusBar, setConnected, setDisconnected, dispose as disposeStatusBar } from './statusBar';
import { onFileSaved, onFileCreated, onFileDeleted, onFileRenamed, resetStagedCount } from './fileWatcher';
import { SetupPanel } from './setupPanel';
import { getVersion, healthCheck, syncFile } from './api';
import { StagedFilesProvider, StagedFileItem } from './stagedFilesProvider';
import axios from 'axios';

// ── Global provider instance (shared between commands) ─────────────────────
let stagedFilesProvider: StagedFilesProvider;

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  console.log('[GitPhone] Extension activating...');

  // ── Initialize modules ────────────────────────────────────────────────────
  initConfig(context);
  initCache(context);
  initStatusBar();

  // ── Sidebar TreeView ──────────────────────────────────────────────────────
  stagedFilesProvider = new StagedFilesProvider();
  const treeView = vscode.window.createTreeView('gitphone.stagedFiles', {
    treeDataProvider: stagedFilesProvider,
    showCollapseAll: false,
  });
  context.subscriptions.push(treeView);
  context.subscriptions.push({ dispose: () => stagedFilesProvider.dispose() });

  // Update tree view title + Activity Bar badge with staged count
  stagedFilesProvider.onDidChangeTreeData(() => {
    const count = stagedFilesProvider.stagedCount;
    treeView.title = count > 0 ? `Staged Files (${count})` : 'Staged Files';
    // Badge on Activity Bar icon
    treeView.badge = count > 0
      ? { tooltip: `${count} file${count === 1 ? '' : 's'} staged`, value: count }
      : undefined;
    setConnected(count);
  });

  // ── Register commands ─────────────────────────────────────────────────────
  context.subscriptions.push(

    // Setup panel
    vscode.commands.registerCommand('gitphone.openSetup', () => {
      SetupPanel.createOrShow(context.extensionUri);
    }),

    // Open panel / status menu
    vscode.commands.registerCommand('gitphone.openPanel', () => {
      if (isConfigured()) {
        showStatusMenu();
      } else {
        SetupPanel.createOrShow(context.extensionUri);
      }
    }),

    // Clear cache
    vscode.commands.registerCommand('gitphone.clearCache', async () => {
      const confirm = await vscode.window.showWarningMessage(
        'Clear GitPhone local cache? This will reset all cached file SHAs.',
        'Clear Cache',
        'Cancel',
      );
      if (confirm === 'Clear Cache') {
        clearCache();
        resetStagedCount(0);
        stagedFilesProvider.refresh();
        vscode.window.showInformationMessage('GitPhone cache cleared.');
      }
    }),

    // Check status
    vscode.commands.registerCommand('gitphone.checkStatus', () => {
      showStatusMenu();
    }),

    // ── Sidebar commands ──────────────────────────────────────────────────

    // Refresh button in sidebar title bar
    vscode.commands.registerCommand('gitphone.refreshStagedFiles', () => {
      stagedFilesProvider.refresh();
      vscode.window.setStatusBarMessage('$(sync~spin) GitPhone: Refreshing...', 2000);
    }),

    // Unstage a file (remove from staged)
    vscode.commands.registerCommand('gitphone.unstageFile', async (item: StagedFileItem) => {
      if (!item?.file) return;
      const config = getConfig();
      if (!config) return;

      const confirm = await vscode.window.showWarningMessage(
        `Unstage "${item.file.filepath}"?`,
        'Unstage',
        'Cancel',
      );
      if (confirm !== 'Unstage') return;

      try {
        await axios.delete(
          `${config.backendUrl}/staged-files/${item.file.id}`,
          {
            timeout: 8_000,
            headers: {
              'X-Telegram-Id': config.telegramId,
              'X-Api-Key': config.apiKey ?? '',
            },
          },
        );
        stagedFilesProvider.removeFile(item.file.id);
        vscode.window.showInformationMessage(`Unstaged: ${item.file.filepath}`);
      } catch {
        vscode.window.showErrorMessage('Failed to unstage file. Try again.');
      }
    }),

    // Open a staged file locally
    vscode.commands.registerCommand('gitphone.openStagedFile', async (filepath: string) => {
      const workspaceFolders = vscode.workspace.workspaceFolders;
      if (!workspaceFolders) return;

      for (const folder of workspaceFolders) {
        const uri = vscode.Uri.joinPath(folder.uri, filepath);
        try {
          await vscode.window.showTextDocument(uri, { preview: true });
          return;
        } catch {
          // File might not exist locally — try next folder
        }
      }
      vscode.window.showWarningMessage(`File not found locally: ${filepath}`);
    }),

    // Manually force-stage the current open file
    vscode.commands.registerCommand('gitphone.stageCurrentFile', async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) {
        vscode.window.showWarningMessage('No file is currently open.');
        return;
      }
      await onFileSaved(editor.document);
      setTimeout(() => stagedFilesProvider.refresh(), 1000);
    }),

    // Diagnose — shows exactly what's wrong
    vscode.commands.registerCommand('gitphone.diagnose', async () => {
      const config = getConfig();
      const lines: string[] = ['\n=== GitPhone Diagnostics ===\n'];

      if (!config) {
        lines.push('❌ NOT CONFIGURED - run Connect GitPhone first');
        vscode.window.showErrorMessage('GitPhone not configured. Open Setup first.');
        return;
      }

      lines.push(`✅ Telegram ID : ${config.telegramId}`);
      lines.push(`✅ Repo         : ${config.defaultRepo}`);
      lines.push(`✅ Branch       : ${config.branch}`);
      lines.push(`✅ Backend URL  : ${config.backendUrl}`);
      lines.push(`✅ Has PAT      : ${config.githubToken ? 'yes (' + config.githubToken.slice(0, 8) + '...)' : 'NO - MISSING'}`);

      try {
        const health = await axios.get(`${config.backendUrl}/health`, { timeout: 8000 });
        lines.push(`✅ Backend health: ${JSON.stringify(health.data)}`);
      } catch (e: any) {
        lines.push(`❌ Backend UNREACHABLE: ${e.message}`);
      }

      try {
        const staged = await axios.get(`${config.backendUrl}/staged-files/${config.telegramId}`, { timeout: 8000 });
        lines.push(`✅ Staged files API: ${JSON.stringify(staged.data)}`);
      } catch (e: any) {
        lines.push(`❌ Staged files API FAILED: ${e.message} - ${e.response?.data?.detail}`);
      }

      // Test sync with a dummy payload
      try {
        const testResp = await axios.post(`${config.backendUrl}/sync-file`, {
          telegram_id: config.telegramId,
          filepath: '__gitphone_test__.txt',
          diff: '@@ -0,0 +1 @@\n+test\n',
          full_content: null,
          base_sha: 'new_file',
          is_binary: false,
          file_size: 4,
        }, { timeout: 8000 });
        lines.push(`✅ Sync-file API: ${JSON.stringify(testResp.data)}`);
      } catch (e: any) {
        lines.push(`❌ Sync-file API FAILED: ${e.message} - ${JSON.stringify(e.response?.data)}`);
      }

      const output = lines.join('\n');
      console.log(output);

      // Show result in output channel
      const channel = vscode.window.createOutputChannel('GitPhone Diagnostics');
      channel.appendLine(output);
      channel.show();
    }),
  );

  // ── File Watchers ─────────────────────────────────────────────────────────

  // 1. Modified files (saved in editor)
  const saveListener = vscode.workspace.onDidSaveTextDocument(async (document) => {
    await onFileSaved(document);
    setTimeout(() => stagedFilesProvider.refresh(), 1500);
  });
  context.subscriptions.push(saveListener);

  // 2. Newly created files (created via file explorer, terminal, or Ctrl+N → Save)
  const createListener = vscode.workspace.onDidCreateFiles(async (event) => {
    for (const uri of event.files) {
      await onFileCreated(uri);
    }
    setTimeout(() => stagedFilesProvider.refresh(), 1500);
  });
  context.subscriptions.push(createListener);

  // 3. Deleted files — stage as deletion so the bot can push the delete to GitHub
  const deleteListener = vscode.workspace.onDidDeleteFiles(async (event) => {
    for (const uri of event.files) {
      await onFileDeleted(uri);
    }
    setTimeout(() => stagedFilesProvider.refresh(), 1500);
  });
  context.subscriptions.push(deleteListener);

  // 4. Renamed files = delete old path + create new path
  const renameListener = vscode.workspace.onDidRenameFiles(async (event) => {
    for (const { oldUri, newUri } of event.files) {
      await onFileDeleted(oldUri);   // old path becomes a deletion
      await onFileCreated(newUri);   // new path becomes a creation
    }
    setTimeout(() => stagedFilesProvider.refresh(), 1500);
  });
  context.subscriptions.push(renameListener);

  // ── Startup logic ─────────────────────────────────────────────────────────
  if (isConfigured()) {
    await onStartupConfigured(context);
    stagedFilesProvider.refresh();
  } else {
    setDisconnected();
    const choice = await vscode.window.showInformationMessage(
      '📱 GitPhone is not configured yet. Set it up to start committing from Telegram!',
      'Open Setup',
      'Later',
    );
    if (choice === 'Open Setup') {
      SetupPanel.createOrShow(context.extensionUri);
    }
  }

  context.subscriptions.push({ dispose: disposeStatusBar });
  console.log('[GitPhone] Extension activated ✅');
}

/**
 * Runs when extension starts and is already configured.
 * Checks backend health and shows staged count.
 */
async function onStartupConfigured(context: vscode.ExtensionContext): Promise<void> {
  const config = getConfig()!;

  // Quick health check
  const healthy = await healthCheck();
  if (!healthy) {
    setDisconnected();
    vscode.window.showWarningMessage(
      `GitPhone: Cannot reach backend (${config.backendUrl}). ` +
      'Check your backend URL or try again later.',
    );
    return;
  }

  // Schema version check (non-blocking)
  checkSchemaVersion().catch(console.error);

  // Start with 0 — the status bar updates on next file save
  setConnected(0);
}

/**
 * Schema version check — notifies user if backend has a newer schema.
 */
async function checkSchemaVersion(): Promise<void> {
  try {
    const response = await getVersion();
    const serverVersion = response.schema_version;
    const config = getConfig();
    const localVersion = config?.schemaVersion ?? 1;

    if (serverVersion > localVersion) {
      const choice = await vscode.window.showWarningMessage(
        `GitPhone schema update required (v${localVersion} → v${serverVersion})`,
        'How To Update',
        'Copy SQL',
        'Later',
      );
      if (choice === 'Copy SQL' && response.migration_sql) {
        await vscode.env.clipboard.writeText(response.migration_sql);
        vscode.window.showInformationMessage(
          'Migration SQL copied! Paste it in your Supabase SQL editor.',
        );
      }
      if (choice === 'How To Update') {
        vscode.env.openExternal(vscode.Uri.parse(response.docs_url));
      }
    }
  } catch {
    // Backend unreachable — already handled in onStartupConfigured
  }
}

/**
 * Quick-pick menu when user clicks the status bar while configured.
 */
async function showStatusMenu(): Promise<void> {
  const config = getConfig();
  if (!config) return;

  const items = [
    {
      label: '$(info) GitPhone Status',
      description: `${config.defaultRepo} • ${config.branch}`,
      action: 'status',
    },
    {
      label: '$(gear) Open Setup',
      description: 'Reconfigure your GitPhone connection',
      action: 'setup',
    },
    {
      label: '$(trash) Clear Cache',
      description: 'Reset local diff cache (use if diffs are wrong)',
      action: 'cache',
    },
  ];

  const selected = await vscode.window.showQuickPick(items, {
    placeHolder: 'GitPhone Actions',
  });

  if (!selected) return;

  switch (selected.action) {
    case 'setup':
      SetupPanel.createOrShow(vscode.Uri.parse(''));
      break;
    case 'cache':
      vscode.commands.executeCommand('gitphone.clearCache');
      break;
    case 'status':
      vscode.window.showInformationMessage(
        `GitPhone ✅\nRepo: ${config.defaultRepo} • ${config.branch}\nBackend: ${config.backendUrl}`,
      );
      break;
  }
}


export function deactivate(): void {
  console.log('[GitPhone] Extension deactivated');
}
