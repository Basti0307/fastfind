#!/usr/bin/env python3
"""
fastfind – Clean cross-platform search engine library for Windows & Linux.
"""

from __future__ import annotations

import os
import re
import string
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

# ┌─────────────────────────────────────────────────────────────────────────┐
# │  CONFIGURATION – Directories and prefixes to skip for speed              │
# └─────────────────────────────────────────────────────────────────────────┘

DEFAULT_SKIP_DIRS: frozenset = frozenset({
    # Windows specific
    "windows", "system32", "syswow64", "winsxs", "winside",
    "system volume information", "systemvolumeinformation",
    "$windows.~ws", "$windows.~bt", "$winreagent", "recovery", "boot",
    "driverstore", "drivers", "inf", "catroot", "catroot2",
    "appdata", "application data", "local settings",
    
    # Linux / macOS specific
    "proc", "sys", "dev", "run", "snap", "flatpak", "lost+found",
    
    # Universal developer & temp folders
    "node_modules", ".git", ".hg", ".svn", "__pycache__", ".vs",
    ".vscode", "packages", ".nuget","prefetch",
    "gpucache", "media cache", "shader cache",
    "site-packages", "dist-info", "dist",
})

SKIP_PREFIXES: tuple = ("$", "~")
MAX_WORKERS: int = min(16, (os.cpu_count() or 4) * 2)

# ┌─────────────────────────────────────────────────────────────────────────┐
# │  INTERNAL HELPER FUNCTIONS                                              │
# └─────────────────────────────────────────────────────────────────────────┘

def _get_drives() -> list[str]:
    """Detect windows dirive letters"""
    if os.name != 'nt':
        return []
    drives = []
    for letter in string.ascii_uppercase:
        path = f"{letter}:\\"
        try:
            if os.path.exists(path):
                drives.append(path)
        except OSError:
            pass
    return drives


def _should_skip(name: str, skip_dirs_enabled: bool) -> bool:
    """Determines whether a directory should be skipped based on configuration."""
    if not skip_dirs_enabled:
        return False
    lower = name.lower()
    if lower in DEFAULT_SKIP_DIRS:
        return True
    for prefix in SKIP_PREFIXES:
        if lower.startswith(prefix):
            return True
    if lower.startswith("."):
        return True
    return False


def _wildcard_to_regex(query: str, *, anchored: bool) -> str:
    """Translates * and ? wildcards into a regex string."""
    parts = re.split(r"([\*\?])", query)
    regex_parts = []
    for part in parts:
        if part == "*":
            regex_parts.append(".*")
        elif part == "?":
            regex_parts.append(".")
        else:
            regex_parts.append(re.escape(part))
    body = "".join(regex_parts)
    if anchored:
        return "^" + body + "$"
    return body


def _build_regex(query: str, exact_match: bool) -> "re.Pattern":
    """
    Converts a search query into a regex pattern.
    """
    has_wildcards = "*" in query or "?" in query

    if exact_match and not has_wildcards:
        return re.compile("^" + re.escape(query) + "$", re.IGNORECASE)

    if not has_wildcards:
        # Reines Teilstring-Match (überall im Namen erlaubt)
        return re.compile(re.escape(query), re.IGNORECASE)

    # Wildcard-Modus: gesamter Name muss passen
    return re.compile(_wildcard_to_regex(query, anchored=True), re.IGNORECASE)


def _build_exclude_keyword_patterns(keywords: list[str]) -> list["re.Pattern"]:
    """Builds regex patterns for exclude_keywords (supports * and ? wildcards)."""
    patterns: list[re.Pattern] = []
    for keyword in keywords:
        if "*" in keyword or "?" in keyword:
            patterns.append(re.compile(_wildcard_to_regex(keyword, anchored=False), re.IGNORECASE))
        else:
            patterns.append(re.compile(re.escape(keyword), re.IGNORECASE))
    return patterns


def _matches_exclude_keyword(name: str, patterns: list["re.Pattern"]) -> bool:
    return any(pattern.search(name) for pattern in patterns)


def _normalize_path(path: str) -> str:
    return os.path.normpath(path).lower()


def _is_path_under(path: str, parent: str) -> bool:
    path_norm = _normalize_path(path)
    parent_norm = _normalize_path(parent)
    return path_norm == parent_norm or path_norm.startswith(parent_norm + os.sep)


def _is_excluded_content_dir(path: str, ex_content: set[str]) -> bool:
    """True when direct files in this directory should be skipped (exact path match)."""
    path_norm = _normalize_path(path)
    return path_norm in ex_content


def _should_skip_subdirs(path: str, ex_subdirs: set[str]) -> bool:
    """True when subdirectories must not be traversed or listed (/. marker)."""
    return any(_is_path_under(path, excluded) for excluded in ex_subdirs)


def _relevance_score(filepath: str, query: str) -> tuple:
    """Scores a result for sorting. Lower tuple = better (more relevant) match."""
    name = os.path.basename(filepath)
    name_lower = name.lower()

    clean = query.lower().replace("*", "").replace("?", "")
    if not clean:
        return (4, len(name_lower), name_lower)

    base = name_lower.rsplit(".", 1)[0] if "." in name_lower else name_lower

    if name_lower == clean:
        return (0, 0, name_lower)
    if base == clean:
        return (0, 1, name_lower)
    if name_lower.startswith(clean) or base.startswith(clean):
        return (1, len(name_lower), name_lower)
    if name_lower.endswith(clean):
        return (2, len(name_lower), name_lower)
    if clean in name_lower:
        return (3, len(name_lower), name_lower)
    return (4, len(name_lower), name_lower)


def _get_search_roots(skip_dirs_enabled: bool) -> list[tuple[str, bool]]:
    """Gathers top-level system directories. Returns tuples of (path, is_recursive)."""
    roots = []
    if os.name == 'nt':
        for drive in _get_drives():
            # Scan files directly in the drive root (non-recursive)
            roots.append((drive, False))
            try:
                with os.scandir(drive) as it:
                    for entry in it:
                        try:
                            if entry.is_dir(follow_symlinks=False) and not _should_skip(entry.name, skip_dirs_enabled):
                                roots.append((entry.path, True))
                        except OSError:
                            pass
            except (PermissionError, OSError):
                pass
    else:
        # Scan files directly in / (non-recursive)
        roots.append(("/", False))
        try:
            with os.scandir("/") as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False) and not _should_skip(entry.name, skip_dirs_enabled):
                            roots.append((entry.path, True))
                    except OSError:
                        pass
        except (PermissionError, OSError):
            roots = [("/", True)]
            
    return roots


# ┌─────────────────────────────────────────────────────────────────────────┐
# │  CORE SEARCH WORKER (Runs in parallel threads)                           │
# └─────────────────────────────────────────────────────────────────────────┘

def _worker(
    root_path: str,
    is_recursive: bool,
    pattern: "re.Pattern",
    search_type: str,
    results: list[str],
    lock: threading.Lock,
    stop: threading.Event,
    limit: int,
    skip_dirs_enabled: bool,
    max_files_per_dir: Optional[int],
    ex_names: set[str],
    ex_content: set[str],
    ex_subdirs: set[str],
    ex_keyword_patterns: list["re.Pattern"],
) -> None:
    """Iterative BFS worker supporting root-level non-recursive constraints."""
    queue: deque = deque([(root_path, is_recursive)])

    while queue and not stop.is_set():
        current, current_recursive = queue.popleft()
        current_norm = _normalize_path(current)

        subdirs = []
        subfiles = []
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            subdirs.append(entry)
                        else:
                            subfiles.append(entry)
                    except OSError:
                        continue
        except (PermissionError, OSError):
            continue

        # 1. Process subdirectories
        block_subdir_traversal = (not current_recursive) or _should_skip_subdirs(current_norm, ex_subdirs)
        hide_all_recursive = _should_skip_subdirs(current_norm, ex_subdirs)
        hide_direct_content = _is_excluded_content_dir(current_norm, ex_content)
        
        for entry in subdirs:
            if stop.is_set():
                return
            if _should_skip(entry.name, skip_dirs_enabled):
                continue

            name_lower = entry.name.lower()

            if name_lower in ex_names:
                continue

            if hide_all_recursive:
                continue

            keyword_excluded = ex_keyword_patterns and _matches_exclude_keyword(entry.name, ex_keyword_patterns)

            show_as_result = (
                not hide_direct_content
                and not keyword_excluded
                and search_type in ("dir", "any")
                and pattern.search(entry.name)
            )
            if show_as_result:
                with lock:
                    if len(results) < limit:
                        results.append(entry.path)
                        if len(results) >= limit:
                            stop.set()
                            return
            
            if not block_subdir_traversal:
                queue.append((entry.path, True))

        # 2. Process files next
        skip_files_here = hide_direct_content or hide_all_recursive
        files_found_in_dir = 0
        for entry in subfiles:
            if stop.is_set():
                return
            if skip_files_here:
                continue
            
            name_lower = entry.name.lower()
            entry_norm = _normalize_path(entry.path)
            if name_lower in ex_names:
                continue
            if entry_norm in ex_content:
                continue
            if ex_keyword_patterns and _matches_exclude_keyword(entry.name, ex_keyword_patterns):
                continue

            if search_type in ("file", "any") and pattern.search(entry.name):
                if max_files_per_dir is not None and files_found_in_dir >= max_files_per_dir:
                    break
                
                with lock:
                    # Double-check inside lock
                    if len(results) < limit:
                        results.append(entry.path)
                        if len(results) >= limit:
                            stop.set()
                            return
                files_found_in_dir += 1


# ┌─────────────────────────────────────────────────────────────────────────┐
# │  PUBLIC API                                                             │
# └─────────────────────────────────────────────────────────────────────────┘

def fast_search(
    query: str,
    search_type: str = "any",
    max_results: int = 1000,
    timeout: float = 5.0,
    roots: Optional[list[str]] = None,
    all_dirs: bool = False,
    max_files_per_dir: Optional[int] = None,
    exact_match: bool = False,
    exclude_folders: Optional[list[str]] = None,
    exclude_keywords: Optional[list[str]] = None,
) -> list[str]:
    """
    Scans the filesystem at blazing speed.
    """
    # Parameter validation
    if search_type not in ("file", "dir", "any"):
        raise ValueError("search_type must be 'file', 'dir', or 'any'")
    if max_results <= 0:
        raise ValueError("max_results must be strictly positive")
    if timeout <= 0:
        raise ValueError("timeout must be strictly positive")
    if max_files_per_dir is not None and max_files_per_dir <= 0:
        raise ValueError("max_files_per_dir must be strictly positive or None")

    pattern = _build_regex(query, exact_match)
    skip_dirs_enabled = not all_dirs

    # Cleanly parse roots and handles OS-specific drives safely
    processed_roots: list[tuple[str, bool]] = []
    if roots is not None:
        for r in roots:
            # Detect the recursive marker BEFORE normpath strips it
            is_recursive = r.endswith(os.sep + ".") or r.endswith("/.")
            r_norm = os.path.normpath(r)
            base = r_norm

            # Ensure valid drive parsing (e.g., "C:" becomes "C:\")
            drive, tail = os.path.splitdrive(base)
            if drive and not tail:
                base = drive + os.sep

            processed_roots.append((base, is_recursive))
    else:
        processed_roots = _get_search_roots(skip_dirs_enabled)

    # Early exit if no valid roots exist
    if not processed_roots:
        return []

    # Parse exclusions cleanly
    ex_names: set[str] = set()
    ex_content: set[str] = set()
    ex_subdirs: set[str] = set()

    if exclude_folders:
        for p in exclude_folders:
            # Detect the subdirectory-exclusion marker before normpath strips it
            is_subdir_exclusion = p.endswith(os.sep + ".") or p.endswith("/.")
            p_norm = os.path.normpath(p).lower()
            if is_subdir_exclusion:
                ex_subdirs.add(p_norm)
            elif os.sep in p_norm:
                ex_content.add(p_norm)
            else:
                ex_names.add(p_norm)

    ex_keyword_patterns = _build_exclude_keyword_patterns(
        [k.lower() for k in exclude_keywords]
    ) if exclude_keywords else []

    results: list[str] = []
    lock = threading.Lock()
    stop = threading.Event()
    start = time.perf_counter()

    pool = ThreadPoolExecutor(max_workers=MAX_WORKERS)
    
    futures = [
        pool.submit(
            _worker, r_path, r_recursive, pattern, search_type, results, lock, stop, max_results, 
            skip_dirs_enabled, max_files_per_dir, ex_names, ex_content, ex_subdirs, ex_keyword_patterns
        )
        for r_path, r_recursive in processed_roots
    ]

    deadline = start + timeout
    while time.perf_counter() < deadline:
        if all(f.done() for f in futures):
            break
        time.sleep(0.02)

    stop.set()
    
    # Clean up thread pool
    try:
        pool.shutdown(wait=False, cancel_futures=True)
    except TypeError:
        pool.shutdown(wait=False)

    results.sort(key=lambda p: _relevance_score(p, query))
    return results