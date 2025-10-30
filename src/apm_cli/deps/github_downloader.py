"""GitHub package downloader for APM dependencies."""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import re
import requests

import git
from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

from ..core.token_manager import GitHubTokenManager
from ..models.apm_package import (
    DependencyReference, 
    PackageInfo, 
    ResolvedReference, 
    GitReferenceType,
    validate_apm_package,
    APMPackage
)
from ..utils.github_host import build_https_clone_url, build_ssh_url, sanitize_token_url_in_message, is_github_hostname, default_host


class GitHubPackageDownloader:
    """Downloads and validates APM packages from GitHub repositories."""
    
    def __init__(self):
        """Initialize the GitHub package downloader."""
        self.token_manager = GitHubTokenManager()
        self.git_env = self._setup_git_environment()
    
    def _setup_git_environment(self) -> Dict[str, Any]:
        """Set up Git environment with GitHub authentication using centralized token manager.
        
        Returns:
            Dict containing environment variables for Git operations
        """
        # Use centralized token management
        env = self.token_manager.setup_environment()
        
        # Get the token for modules (APM package access)
        self.github_token = self.token_manager.get_token_for_purpose('modules', env)
        self.has_github_token = self.github_token is not None
        
        # Configure Git security settings
        env['GIT_TERMINAL_PROMPT'] = '0'
        env['GIT_ASKPASS'] = 'echo'  # Prevent interactive credential prompts
        env['GIT_CONFIG_NOSYSTEM'] = '1'
        env['GIT_CONFIG_GLOBAL'] = '/dev/null'
        
        return env
    
    def _sanitize_git_error(self, error_message: str) -> str:
        """Sanitize Git error messages to remove potentially sensitive authentication information.
        
        Args:
            error_message: Raw error message from Git operations
            
        Returns:
            str: Sanitized error message with sensitive data removed
        """
        import re
        
        # Remove any tokens that might appear in URLs for github hosts (format: https://token@host)
        # Sanitize for default host and common enterprise hosts via helper
        sanitized = sanitize_token_url_in_message(error_message, host=default_host())
        
        # Remove any tokens that might appear as standalone values
        sanitized = re.sub(r'(ghp_|gho_|ghu_|ghs_|ghr_)[a-zA-Z0-9_]+', '***', sanitized)
        
        # Remove environment variable values that might contain tokens
        sanitized = re.sub(r'(GITHUB_TOKEN|GITHUB_APM_PAT|GH_TOKEN|GITHUB_COPILOT_PAT)=[^\s]+', r'\1=***', sanitized)
        
        return sanitized

    def _build_repo_url(self, repo_ref: str, use_ssh: bool = False) -> str:
        """Build the appropriate repository URL for cloning.
        
        Uses GitHub Enterprise authentication format for private repositories:
        - x-access-token format for authenticated HTTPS (GitHub Enterprise standard)
        - SSH URLs for SSH key-based authentication
        - Standard HTTPS URLs as fallback
        
        Args:
            repo_ref: Repository reference in format "owner/repo"
            use_ssh: Whether to use SSH URL for git operations
            
        Returns:
            str: Repository URL suitable for git clone operations
        """
        # Determine host to use. If repo_ref is namespaced with a host (like host/owner/repo),
        # the DependencyReference.parse will have normalized repo_ref to owner/repo and stored host separately.
        # For this method, callers should pass repo_ref as owner/repo and optionally set self.github_host.
        host = getattr(self, 'github_host', None) or default_host()

        if use_ssh:
            return build_ssh_url(host, repo_ref)
        elif self.github_token:
            return build_https_clone_url(host, repo_ref, token=self.github_token)
        else:
            return build_https_clone_url(host, repo_ref, token=None)
    
    def _clone_with_fallback(self, repo_url_base: str, target_path: Path, **clone_kwargs) -> Repo:
        """Attempt to clone a repository with fallback authentication methods.
        
        Uses GitHub Enterprise authentication patterns:
        1. x-access-token format for private repos (GitHub Enterprise standard)
        2. SSH for SSH key-based authentication
        3. Standard HTTPS for public repos (fallback)
        
        Args:
            repo_url_base: Base repository reference (owner/repo)
            target_path: Target path for cloning
            **clone_kwargs: Additional arguments for Repo.clone_from
            
        Returns:
            Repo: Successfully cloned repository
            
        Raises:
            RuntimeError: If all authentication methods fail
        """
        last_error = None
        
        # Method 1: Try x-access-token format if token is available (GitHub Enterprise)
        if self.github_token:
            try:
                auth_url = self._build_repo_url(repo_url_base, use_ssh=False)
                return Repo.clone_from(auth_url, target_path, env=self.git_env, **clone_kwargs)
            except GitCommandError as e:
                last_error = e
                # Continue to next method
        
        # Method 2: Try SSH if it might work (for SSH key-based authentication)
        try:
            ssh_url = self._build_repo_url(repo_url_base, use_ssh=True)
            return Repo.clone_from(ssh_url, target_path, env=self.git_env, **clone_kwargs)
        except GitCommandError as e:
            last_error = e
            # Continue to next method
        
        # Method 3: Try standard HTTPS as fallback for public repos
        try:
            public_url = f"https://github.com/{repo_url_base}"
            return Repo.clone_from(public_url, target_path, env=self.git_env, **clone_kwargs)
        except GitCommandError as e:
            last_error = e
        
        # All methods failed
        error_msg = f"Failed to clone repository {repo_url_base} using all available methods. "
        if not self.has_github_token:
            error_msg += "For private repositories, set GITHUB_APM_PAT or GITHUB_TOKEN environment variable, " \
                        "or ensure SSH keys are configured."
        else:
            error_msg += "Please check repository access permissions and authentication setup."
        
        if last_error:
            sanitized_error = self._sanitize_git_error(str(last_error))
            error_msg += f" Last error: {sanitized_error}"
        
        raise RuntimeError(error_msg)
    
    def resolve_git_reference(self, repo_ref: str) -> ResolvedReference:
        """Resolve a Git reference (branch/tag/commit) to a specific commit SHA.
        
        Args:
            repo_ref: Repository reference string (e.g., "user/repo#branch")
            
        Returns:
            ResolvedReference: Resolved reference with commit SHA
            
        Raises:
            ValueError: If the reference format is invalid
            RuntimeError: If Git operations fail
        """
        # Parse the repository reference
        try:
            dep_ref = DependencyReference.parse(repo_ref)
        except ValueError as e:
            raise ValueError(f"Invalid repository reference '{repo_ref}': {e}")
        
        # Default to main branch if no reference specified
        ref = dep_ref.reference or "main"
        
        # Pre-analyze the reference type to determine the best approach
        is_likely_commit = re.match(r'^[a-f0-9]{7,40}$', ref.lower()) is not None
        
        # Create a temporary directory for Git operations
        temp_dir = None
        try:
            import tempfile
            temp_dir = Path(tempfile.mkdtemp())
            
            if is_likely_commit:
                # For commit SHAs, clone full repository first, then checkout the commit
                try:
                    # Ensure host is set for enterprise repos
                    if getattr(dep_ref, 'host', None):
                        self.github_host = dep_ref.host
                    repo = self._clone_with_fallback(dep_ref.repo_url, temp_dir)
                    commit = repo.commit(ref)
                    ref_type = GitReferenceType.COMMIT
                    resolved_commit = commit.hexsha
                    ref_name = ref
                except Exception as e:
                    sanitized_error = self._sanitize_git_error(str(e))
                    raise ValueError(f"Could not resolve commit '{ref}' in repository {dep_ref.repo_url}: {sanitized_error}")
            else:
                # For branches and tags, try shallow clone first
                try:
                    # Try to clone with specific branch/tag first
                    if getattr(dep_ref, 'host', None):
                        self.github_host = dep_ref.host
                    repo = self._clone_with_fallback(
                        dep_ref.repo_url,
                        temp_dir,
                        depth=1,
                        branch=ref
                    )
                    ref_type = GitReferenceType.BRANCH  # Could be branch or tag
                    resolved_commit = repo.head.commit.hexsha
                    ref_name = ref

                except GitCommandError:
                    # If branch/tag clone fails, try full clone and resolve reference
                    try:
                        if getattr(dep_ref, 'host', None):
                            self.github_host = dep_ref.host
                        repo = self._clone_with_fallback(dep_ref.repo_url, temp_dir)

                        # Try to resolve the reference
                        try:
                            # Try as branch first
                            try:
                                branch = repo.refs[f"origin/{ref}"]
                                ref_type = GitReferenceType.BRANCH
                                resolved_commit = branch.commit.hexsha
                                ref_name = ref
                            except IndexError:
                                # Try as tag
                                try:
                                    tag = repo.tags[ref]
                                    ref_type = GitReferenceType.TAG
                                    resolved_commit = tag.commit.hexsha
                                    ref_name = ref
                                except IndexError:
                                    raise ValueError(f"Reference '{ref}' not found in repository {dep_ref.repo_url}")

                        except Exception as e:
                            sanitized_error = self._sanitize_git_error(str(e))
                            raise ValueError(f"Could not resolve reference '{ref}' in repository {dep_ref.repo_url}: {sanitized_error}")

                    except GitCommandError as e:
                        # Check if this might be a private repository access issue
                        if "Authentication failed" in str(e) or "remote: Repository not found" in str(e):
                            error_msg = f"Failed to clone repository {dep_ref.repo_url}. "
                            if not self.has_github_token:
                                error_msg += "This might be a private repository that requires authentication. " \
                                           "Please set GITHUB_APM_PAT or GITHUB_TOKEN environment variable."
                            else:
                                error_msg += "Authentication failed. Please check your GitHub token permissions."
                            raise RuntimeError(error_msg)
                        else:
                            sanitized_error = self._sanitize_git_error(str(e))
                            raise RuntimeError(f"Failed to clone repository {dep_ref.repo_url}: {sanitized_error}")
                    
        finally:
            # Clean up temporary directory
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
        
        return ResolvedReference(
            original_ref=repo_ref,
            ref_type=ref_type,
            resolved_commit=resolved_commit,
            ref_name=ref_name
        )
    
    def download_raw_file(self, dep_ref: DependencyReference, file_path: str, ref: str = "main") -> bytes:
        """Download a single file from GitHub repository via raw.githubusercontent.com.
        
        Args:
            dep_ref: Parsed dependency reference
            file_path: Path to file within the repository (e.g., "prompts/code-review.prompt.md")
            ref: Git reference (branch, tag, or commit SHA). Defaults to "main"
            
        Returns:
            bytes: File content
            
        Raises:
            RuntimeError: If download fails or file not found
        """
        host = dep_ref.host or default_host()
        
        # Build raw file URL
        # Format: https://raw.githubusercontent.com/owner/repo/ref/path/to/file
        if host == "github.com":
            base_url = "https://raw.githubusercontent.com"
        else:
            # For GitHub Enterprise, use the API endpoint
            base_url = f"https://{host}/raw"
        
        file_url = f"{base_url}/{dep_ref.repo_url}/{ref}/{file_path}"
        
        # Set up authentication headers
        headers = {}
        if self.github_token:
            headers['Authorization'] = f'token {self.github_token}'
        
        # Try to download with the specified ref
        try:
            response = requests.get(file_url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.content
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                # Try fallback branches if the specified ref fails
                if ref not in ["main", "master"]:
                    # If original ref failed, don't try fallbacks - it might be a specific version
                    raise RuntimeError(f"File not found: {file_path} at ref '{ref}' in {dep_ref.repo_url}")
                
                # Try the other default branch
                fallback_ref = "master" if ref == "main" else "main"
                fallback_url = f"{base_url}/{dep_ref.repo_url}/{fallback_ref}/{file_path}"
                
                try:
                    response = requests.get(fallback_url, headers=headers, timeout=30)
                    response.raise_for_status()
                    return response.content
                except requests.exceptions.HTTPError:
                    raise RuntimeError(
                        f"File not found: {file_path} in {dep_ref.repo_url} "
                        f"(tried refs: {ref}, {fallback_ref})"
                    )
            elif e.response.status_code == 401 or e.response.status_code == 403:
                error_msg = f"Authentication failed for {dep_ref.repo_url}. "
                if not self.github_token:
                    error_msg += "This might be a private repository. Please set GITHUB_APM_PAT or GITHUB_TOKEN."
                else:
                    error_msg += "Please check your GitHub token permissions."
                raise RuntimeError(error_msg)
            else:
                raise RuntimeError(f"Failed to download {file_path}: HTTP {e.response.status_code}")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Network error downloading {file_path}: {e}")
    
    def download_virtual_file_package(self, dep_ref: DependencyReference, target_path: Path) -> PackageInfo:
        """Download a single file as a virtual APM package.
        
        Creates a minimal APM package structure with the file placed in the appropriate
        .apm/ subdirectory based on its extension.
        
        Args:
            dep_ref: Dependency reference with virtual_path set
            target_path: Local path where virtual package should be created
            
        Returns:
            PackageInfo: Information about the created virtual package
            
        Raises:
            ValueError: If the dependency is not a valid virtual file package
            RuntimeError: If download fails
        """
        if not dep_ref.is_virtual or not dep_ref.virtual_path:
            raise ValueError("Dependency must be a virtual file package")
        
        if not dep_ref.is_virtual_file():
            raise ValueError(f"Path '{dep_ref.virtual_path}' is not a valid individual file. "
                           f"Must end with one of: {', '.join(DependencyReference.VIRTUAL_FILE_EXTENSIONS)}")
        
        # Determine the ref to use
        ref = dep_ref.reference or "main"
        
        # Download the file content
        try:
            file_content = self.download_raw_file(dep_ref, dep_ref.virtual_path, ref)
        except RuntimeError as e:
            raise RuntimeError(f"Failed to download virtual package: {e}")
        
        # Create target directory structure
        target_path.mkdir(parents=True, exist_ok=True)
        
        # Determine the subdirectory based on file extension
        subdirs = {
            '.prompt.md': 'prompts',
            '.instructions.md': 'instructions',
            '.chatmode.md': 'chatmodes',
            '.agent.md': 'agents'
        }
        
        subdir = None
        filename = dep_ref.virtual_path.split('/')[-1]
        for ext, dir_name in subdirs.items():
            if dep_ref.virtual_path.endswith(ext):
                subdir = dir_name
                break
        
        if not subdir:
            raise ValueError(f"Unknown file extension for {dep_ref.virtual_path}")
        
        # Create .apm structure
        apm_dir = target_path / ".apm" / subdir
        apm_dir.mkdir(parents=True, exist_ok=True)
        
        # Write the file
        file_path = apm_dir / filename
        file_path.write_bytes(file_content)
        
        # Generate minimal apm.yml
        package_name = dep_ref.get_virtual_package_name()
        
        # Try to extract description from file frontmatter
        description = f"Virtual package containing {filename}"
        try:
            content_str = file_content.decode('utf-8')
            # Simple frontmatter parsing (YAML between --- markers)
            if content_str.startswith('---\n'):
                end_idx = content_str.find('\n---\n', 4)
                if end_idx > 0:
                    frontmatter = content_str[4:end_idx]
                    # Look for description field
                    for line in frontmatter.split('\n'):
                        if line.startswith('description:'):
                            description = line.split(':', 1)[1].strip().strip('"\'')
                            break
        except Exception:
            # If frontmatter parsing fails, use default description
            pass
        
        apm_yml_content = f"""name: {package_name}
version: 1.0.0
description: {description}
author: {dep_ref.repo_url.split('/')[0]}
"""
        
        apm_yml_path = target_path / "apm.yml"
        apm_yml_path.write_text(apm_yml_content, encoding='utf-8')
        
        # Create APMPackage object
        package = APMPackage(
            name=package_name,
            version="1.0.0",
            description=description,
            author=dep_ref.repo_url.split('/')[0],
            source=dep_ref.to_github_url(),
            package_path=target_path
        )
        
        # Return PackageInfo
        return PackageInfo(
            package=package,
            install_path=target_path,
            installed_at=datetime.now().isoformat()
        )
    
    def download_collection_package(self, dep_ref: DependencyReference, target_path: Path) -> PackageInfo:
        """Download a collection as a virtual APM package.
        
        Downloads the collection manifest, then fetches all referenced files and
        organizes them into the appropriate .apm/ subdirectories.
        
        Args:
            dep_ref: Dependency reference with virtual_path pointing to collection
            target_path: Local path where virtual package should be created
            
        Returns:
            PackageInfo: Information about the created virtual package
            
        Raises:
            ValueError: If the dependency is not a valid collection package
            RuntimeError: If download fails
        """
        if not dep_ref.is_virtual or not dep_ref.virtual_path:
            raise ValueError("Dependency must be a virtual collection package")
        
        if not dep_ref.is_virtual_collection():
            raise ValueError(f"Path '{dep_ref.virtual_path}' is not a valid collection path")
        
        # Determine the ref to use
        ref = dep_ref.reference or "main"
        
        # Extract collection name from path (e.g., "collections/project-planning" -> "project-planning")
        collection_name = dep_ref.virtual_path.split('/')[-1]
        
        # Build collection manifest path - try .yml first, then .yaml as fallback
        collection_manifest_path = f"{dep_ref.virtual_path}.collection.yml"
        
        # Download the collection manifest
        try:
            manifest_content = self.download_raw_file(dep_ref, collection_manifest_path, ref)
        except RuntimeError as e:
            # Try .yaml extension as fallback
            if ".collection.yml" in str(e):
                collection_manifest_path = f"{dep_ref.virtual_path}.collection.yaml"
                try:
                    manifest_content = self.download_raw_file(dep_ref, collection_manifest_path, ref)
                except RuntimeError:
                    raise RuntimeError(f"Collection manifest not found: {dep_ref.virtual_path}.collection.yml (also tried .yaml)")
            else:
                raise RuntimeError(f"Failed to download collection manifest: {e}")
        
        # Parse the collection manifest
        from .collection_parser import parse_collection_yml
        
        try:
            manifest = parse_collection_yml(manifest_content)
        except (ValueError, Exception) as e:
            raise RuntimeError(f"Invalid collection manifest '{collection_name}': {e}")
        
        # Create target directory structure
        target_path.mkdir(parents=True, exist_ok=True)
        
        # Download all items from the collection
        downloaded_count = 0
        failed_items = []
        
        for item in manifest.items:
            try:
                # Download the file
                item_content = self.download_raw_file(dep_ref, item.path, ref)
                
                # Determine subdirectory based on item kind
                subdir = item.subdirectory
                
                # Create the subdirectory
                apm_subdir = target_path / ".apm" / subdir
                apm_subdir.mkdir(parents=True, exist_ok=True)
                
                # Write the file
                filename = item.path.split('/')[-1]
                file_path = apm_subdir / filename
                file_path.write_bytes(item_content)
                
                downloaded_count += 1
                
            except RuntimeError as e:
                # Log the failure but continue with other items
                failed_items.append(f"{item.path} ({e})")
                continue
        
        # Check if we downloaded at least some items
        if downloaded_count == 0:
            error_msg = f"Failed to download any items from collection '{collection_name}'"
            if failed_items:
                error_msg += f". Failures:\n  - " + "\n  - ".join(failed_items)
            raise RuntimeError(error_msg)
        
        # Generate apm.yml with collection metadata
        package_name = dep_ref.get_virtual_package_name()
        
        apm_yml_content = f"""name: {package_name}
version: 1.0.0
description: {manifest.description}
author: {dep_ref.repo_url.split('/')[0]}
"""
        
        # Add tags if present
        if manifest.tags:
            apm_yml_content += f"\ntags:\n"
            for tag in manifest.tags:
                apm_yml_content += f"  - {tag}\n"
        
        apm_yml_path = target_path / "apm.yml"
        apm_yml_path.write_text(apm_yml_content, encoding='utf-8')
        
        # Create APMPackage object
        package = APMPackage(
            name=package_name,
            version="1.0.0",
            description=manifest.description,
            author=dep_ref.repo_url.split('/')[0],
            source=dep_ref.to_github_url(),
            package_path=target_path
        )
        
        # Log warnings for failed items if any
        if failed_items:
            import warnings
            warnings.warn(
                f"Collection '{collection_name}' installed with {downloaded_count}/{manifest.item_count} items. "
                f"Failed items: {len(failed_items)}"
            )
        
        # Return PackageInfo
        return PackageInfo(
            package=package,
            install_path=target_path,
            installed_at=datetime.now().isoformat()
        )
    
    def download_package(self, repo_ref: str, target_path: Path) -> PackageInfo:
        """Download a GitHub repository and validate it as an APM package.
        
        For virtual packages (individual files or collections), creates a minimal
        package structure instead of cloning the full repository.
        
        Args:
            repo_ref: Repository reference string (e.g., "user/repo#branch" or "user/repo/path/file.prompt.md")
            target_path: Local path where package should be downloaded
            
        Returns:
            PackageInfo: Information about the downloaded package
            
        Raises:
            ValueError: If the repository reference is invalid
            RuntimeError: If download or validation fails
        """
        # Parse the repository reference
        try:
            dep_ref = DependencyReference.parse(repo_ref)
        except ValueError as e:
            raise ValueError(f"Invalid repository reference '{repo_ref}': {e}")
        
        # Handle virtual packages differently
        if dep_ref.is_virtual:
            if dep_ref.is_virtual_file():
                # Individual file virtual package
                return self.download_virtual_file_package(dep_ref, target_path)
            elif dep_ref.is_virtual_collection():
                # Collection virtual package
                return self.download_collection_package(dep_ref, target_path)
            else:
                raise ValueError(f"Unknown virtual package type for {dep_ref.virtual_path}")
        
        # Regular package download (existing logic)
        # Resolve the Git reference to get specific commit
        resolved_ref = self.resolve_git_reference(repo_ref)
        
        # Create target directory if it doesn't exist
        target_path.mkdir(parents=True, exist_ok=True)
        
        # If directory already exists and has content, remove it
        if target_path.exists() and any(target_path.iterdir()):
            shutil.rmtree(target_path)
            target_path.mkdir(parents=True, exist_ok=True)
        
        try:
            # Clone the repository using fallback authentication methods
            # Use shallow clone for performance if we have a specific commit
            if resolved_ref.ref_type == GitReferenceType.COMMIT:
                # For commits, we need to clone and checkout the specific commit
                repo = self._clone_with_fallback(dep_ref.repo_url, target_path)
                repo.git.checkout(resolved_ref.resolved_commit)
            else:
                # For branches and tags, we can use shallow clone
                repo = self._clone_with_fallback(
                    dep_ref.repo_url,
                    target_path,
                    depth=1,
                    branch=resolved_ref.ref_name
                )
            
            # Remove .git directory to save space and prevent treating as a Git repository
            git_dir = target_path / ".git"
            if git_dir.exists():
                shutil.rmtree(git_dir, ignore_errors=True)
                
        except GitCommandError as e:
            # Check if this might be a private repository access issue
            if "Authentication failed" in str(e) or "remote: Repository not found" in str(e):
                error_msg = f"Failed to clone repository {dep_ref.repo_url}. "
                if not self.has_github_token:
                    error_msg += "This might be a private repository that requires authentication. " \
                               "Please set GITHUB_APM_PAT or GITHUB_TOKEN environment variable."
                else:
                    error_msg += "Authentication failed. Please check your GitHub token permissions."
                raise RuntimeError(error_msg)
            else:
                sanitized_error = self._sanitize_git_error(str(e))
                raise RuntimeError(f"Failed to clone repository {dep_ref.repo_url}: {sanitized_error}")
        except RuntimeError:
            # Re-raise RuntimeError from _clone_with_fallback
            raise
        
        # Validate the downloaded package
        validation_result = validate_apm_package(target_path)
        if not validation_result.is_valid:
            # Clean up on validation failure
            if target_path.exists():
                shutil.rmtree(target_path, ignore_errors=True)
            
            error_msg = f"Invalid APM package {dep_ref.repo_url}:\n"
            for error in validation_result.errors:
                error_msg += f"  - {error}\n"
            raise RuntimeError(error_msg.strip())
        
        # Load the APM package metadata
        if not validation_result.package:
            raise RuntimeError(f"Package validation succeeded but no package metadata found for {dep_ref.repo_url}")
        
        package = validation_result.package
        package.source = dep_ref.to_github_url()
        package.resolved_commit = resolved_ref.resolved_commit
        
        # Create and return PackageInfo
        return PackageInfo(
            package=package,
            install_path=target_path,
            resolved_reference=resolved_ref,
            installed_at=datetime.now().isoformat()
        )
    
    def _get_clone_progress_callback(self):
        """Get a progress callback for Git clone operations.
        
        Returns:
            Callable that can be used as progress callback for GitPython
        """
        def progress_callback(op_code, cur_count, max_count=None, message=''):
            """Progress callback for Git operations."""
            if max_count:
                percentage = int((cur_count / max_count) * 100)
                print(f"\r🚀 Cloning: {percentage}% ({cur_count}/{max_count}) {message}", end='', flush=True)
            else:
                print(f"\r🚀 Cloning: {message} ({cur_count})", end='', flush=True)
        
        return progress_callback