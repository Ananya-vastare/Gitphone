# 09 — Diff Strategy

## Why Diffs?

```
Full file size:      24KB → 300 bytes diff = 98% saving
Supabase limit:      500MB free tier
Users supported:     ~16,000 with diffs vs ~200 with full files

Storing diffs instead of full files:
  ✅ Fits more users on free tier
  ✅ Faster network transfer
  ✅ Lower latency for bot loading
  ✅ Allows conflict detection via base_sha
```

---

## What Gets Stored Where

```
VS Code Extension                 Backend
────────────────────────────────────────────────────────
CRLF → LF normalize               diff-match-patch apply
diff npm compute diff             SHA conflict check
localCache read old version       commit via PyGithub
detect binary/minified            handled pass-through
detect change_type                stored as-is
```

---

## Library Usage

### Client Side: diff (npm)

```typescript
import { createTwoFilesPatch } from 'diff';

function computeDiff(oldContent: string, newContent: string) {
  const patch = createTwoFilesPatch(
    'original', 'modified',
    normalizeLineEndings(oldContent),
    normalizeLineEndings(newContent)
  );
  return patch;
}
```

### Server Side: diff-match-patch (Python)

```python
import diff_match_patch as dmp_module
dmp = dmp_module.diff_match_patch()

def apply_diff(original: str, patch_text: str) -> str:
    patches = dmp.patch_fromText(patch_text)
    merged, _ = dmp.patch_apply(patches, original)
    return merged
```

---

## Change Type Handling

### modify (most common)
```
diff computed against local cached version
base_sha = SHA of last committed version
Stored in staged_files.diff

Example output:
  @@ -10,7 +10,7 @@
   function authenticate() {
  -  return null;
  +  return checkToken();
   }
```

### create (new file)
```
No old content to diff against
full_content = base64 encoded file content
diff = null
base_sha = "0000000" (no prior commit)
change_type = "create"
```

### delete (removed file)
```
diff = unified diff that deletes all content
full_content = null
change_type = "delete"
base_sha = SHA of last committed version
```

### rename (file moved)
```
Handled client-side by fileWatcher:
  old path + new path sent to backend
  Backend treats as delete(old) + create(new)
  FUTURE: Proper rename tracking
```

---

## Binary File Handling

```
Detection: diffEngine.ts checks file content
  - Contains null bytes (0x00)
  - Contains Unicode replacement character (0xFFFD)
  - Extension blacklist: .png, .jpg, .gif, .ico, .pdf, .zip, etc.

Storage:
  full_content = base64 encoded file
  diff = null
  is_binary = true

Size limit: 10MB (same as text files)
  >10MB → rejected with inline warning
```

---

## Minified File Handling

```
Detection:
  - Filename ends with .min.js, .min.css, .bundle.js
  - OR file is a single long line (>500 chars)

Storage: Same as binary (full content, no diff)
  diff = null
  full_content = base64

Rationale: Diffs on minified files are meaningless.
  Single line changes produce massive useless diffs.
```

---

## base_sha Tracking

```
Purpose: Know which version the diff was computed against.

Flow:
  1. Extension reads current file HEAD SHA via localCache
     (populated from GitHub API at first sync)
  2. Diff computed against this SHA
  3. base_sha stored alongside diff in Supabase
  4. At commit time:
     a. Backend fetches current SHA from GitHub
     b. If current SHA == base_sha → no conflict → commit directly
     c. If different → conflict detected → warn user

After successful commit:
  Extension receives new SHA
  Updates localCache with new SHA + content
```

---

## Conflict Detection

```python
# github_service.py (simplified)
def commit_files(repo_name, branch, message, files_to_commit):
    for file in files:
        if file["base_sha"] != "0000000":
            current_sha = repo.get_contents(file["filepath"],
                            ref=branch).sha
            if current_sha != file["base_sha"]:
                raise ConflictError(file["filepath"])
```

---

## Manual Sync vs Auto-Save Difference

### Auto-Save (file watcher triggered)
```
  diff === unified diff patch (compact)
  full_content === null
  Used for automatic saves on every file change
```

### Manual Sync (user triggered via sidebar button)
```
  diff === null
  full_content === base64 encoded file content
  Used for:
    - Initial setup
    - Files where local cache is missing
    - Force re-sync
    - Troubleshooting
```

---

## Staleness (FUTURE: 72hr Warning)

```
Not currently implemented:
  - Track staged_at timestamp
  - After 72 hours, mark file as stale
  - Bot warns before committing: "Some files are X hours old..."
  - Status bar turns yellow
```

---

## Size Estimates

```
Per diff:
  Text file 24KB → diff ~300 bytes (1.25%)
  Binary file 5MB → full content 5MB (100%)
  Minified file 2MB → full content 2MB (100%)

50 diffs/commit_logs per user per month:
  Text only:  50 × 500 bytes  = 25KB
  Mixed:      40 text + 10 binary × 50KB = 500KB
  Still well within limits ✅
```
