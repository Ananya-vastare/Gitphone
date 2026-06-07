"""
diff_service.py - Apply unified diffs via Google's diff-match-patch library.
Used at commit time to reconstruct file content from stored diff + GitHub base.
"""

import diff_match_patch as dmp_module

_dmp = dmp_module.diff_match_patch()


def apply_diff(original_content: str, patch_text: str) -> tuple[str, bool]:
    """
    Applies a unified diff patch to original content.
    Returns (new_content, success).

    success=False means one or more patches could not be applied cleanly.
    In that case new_content is returned but may be incomplete.
    """
    try:
        # Normalize line endings before applying
        original_content = original_content.replace("\r\n", "\n").replace("\r", "\n")
        patch_text = patch_text.replace("\r\n", "\n").replace("\r", "\n")

        patches = _dmp.patch_fromText(patch_text)
        new_content, results = _dmp.patch_apply(patches, original_content)
        success = all(results)
        return new_content, success
    except Exception as e:
        print(f"[diff_service] apply_diff error: {e}")
        return original_content, False


def detect_conflict(stored_base_sha: str, current_github_sha: str) -> bool:
    """
    Returns True if file was modified on GitHub after staging.
    SHA mismatch = conflict.
    'new_file' base_sha is never a conflict (new file creation).
    """
    if stored_base_sha == "new_file":
        return False
    return stored_base_sha != current_github_sha
