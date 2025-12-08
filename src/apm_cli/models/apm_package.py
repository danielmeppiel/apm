"""APM Package data models and validation logic."""

import re
import urllib.parse
from ..utils.github_host import is_supported_git_host, is_azure_devops_hostname, default_host
import yaml
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any, Union


class GitReferenceType(Enum):
    """Types of Git references supported."""
    BRANCH = "branch"
    TAG = "tag" 
    COMMIT = "commit"


class ValidationError(Enum):
    """Types of validation errors for APM packages."""
    MISSING_APM_YML = "missing_apm_yml"
    MISSING_APM_DIR = "missing_apm_dir"
    INVALID_YML_FORMAT = "invalid_yml_format"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    INVALID_VERSION_FORMAT = "invalid_version_format"
    INVALID_DEPENDENCY_FORMAT = "invalid_dependency_format"
    EMPTY_APM_DIR = "empty_apm_dir"
    INVALID_PRIMITIVE_STRUCTURE = "invalid_primitive_structure"


class InvalidVirtualPackageExtensionError(ValueError):
    """Raised when a virtual package file has an invalid extension."""
    pass


@dataclass
class ResolvedReference:
    """Represents a resolved Git reference."""
    original_ref: str
    ref_type: GitReferenceType
    resolved_commit: str
    ref_name: str  # The actual branch/tag/commit name
    
    def __str__(self) -> str:
        """String representation of resolved reference."""
        if self.ref_type == GitReferenceType.COMMIT:
            return f"{self.resolved_commit[:8]}"
        return f"{self.ref_name} ({self.resolved_commit[:8]})"


@dataclass 
class DependencyReference:
    """Represents a reference to an APM dependency."""
    repo_url: str  # e.g., "user/repo" for GitHub or "org/project/repo" for Azure DevOps
    host: Optional[str] = None  # Optional host (github.com, dev.azure.com, or enterprise host)
    reference: Optional[str] = None  # e.g., "main", "v1.0.0", "abc123"
    alias: Optional[str] = None  # Optional alias for the dependency
    virtual_path: Optional[str] = None  # Path for virtual packages (e.g., "prompts/file.prompt.md")
    is_virtual: bool = False  # True if this is a virtual package (individual file or collection)
    
    # Azure DevOps specific fields (ADO uses org/project/repo structure)
    ado_organization: Optional[str] = None  # e.g., "dmeppiel-org"
    ado_project: Optional[str] = None       # e.g., "market-js-app"
    ado_repo: Optional[str] = None          # e.g., "compliance-rules"
    
    # Supported file extensions for virtual packages
    VIRTUAL_FILE_EXTENSIONS = ('.prompt.md', '.instructions.md', '.chatmode.md', '.agent.md')
    
    def is_azure_devops(self) -> bool:
        """Check if this reference points to Azure DevOps."""
        from ..utils.github_host import is_azure_devops_hostname
        return self.host is not None and is_azure_devops_hostname(self.host)
    
    def is_virtual_file(self) -> bool:
        """Check if this is a virtual file package (individual file)."""
        if not self.is_virtual or not self.virtual_path:
            return False
        return any(self.virtual_path.endswith(ext) for ext in self.VIRTUAL_FILE_EXTENSIONS)
    
    def is_virtual_collection(self) -> bool:
        """Check if this is a virtual collection package."""
        if not self.is_virtual or not self.virtual_path:
            return False
        # Collections have /collections/ in their path or start with collections/
        return '/collections/' in self.virtual_path or self.virtual_path.startswith('collections/')
    
    def get_virtual_package_name(self) -> str:
        """Generate a package name for this virtual package.
        
        For virtual packages, we create a sanitized name from the path:
        - github/awesome-copilot/prompts/code-review.prompt.md → awesome-copilot-code-review
        - github/awesome-copilot/collections/project-planning → awesome-copilot-project-planning
        """
        if not self.is_virtual or not self.virtual_path:
            return self.repo_url.split('/')[-1]  # Return repo name as fallback
        
        # Extract repo name and file/collection name
        repo_parts = self.repo_url.split('/')
        repo_name = repo_parts[-1] if repo_parts else "package"
        
        # Get the basename without extension
        path_parts = self.virtual_path.split('/')
        if self.is_virtual_collection():
            # For collections: use the collection name
            # collections/project-planning → project-planning
            collection_name = path_parts[-1]
            return f"{repo_name}-{collection_name}"
        else:
            # For individual files: use the filename without extension
            # prompts/code-review.prompt.md → code-review
            filename = path_parts[-1]
            for ext in self.VIRTUAL_FILE_EXTENSIONS:
                if filename.endswith(ext):
                    filename = filename[:-len(ext)]
                    break
            return f"{repo_name}-{filename}"
    
    def get_unique_key(self) -> str:
        """Get a unique key for this dependency for deduplication.
        
        For regular packages: repo_url
        For virtual packages: repo_url + virtual_path to ensure uniqueness
        
        Returns:
            str: Unique key for this dependency
        """
        if self.is_virtual and self.virtual_path:
            return f"{self.repo_url}/{self.virtual_path}"
        return self.repo_url
    
    def get_canonical_dependency_string(self) -> str:
        """Get the canonical dependency string as stored in apm.yml.
        
        This is the unique identifier for a package in the dependency list.
        It includes:
        - repo_url (always)
        - virtual_path (for virtual packages)
        - Does NOT include: reference (#) or alias (@) as these don't affect identity
        
        Returns:
            str: Canonical dependency string (e.g., "owner/repo" or "owner/repo/collections/name")
        """
        return self.get_unique_key()
    
    def get_install_path(self, apm_modules_dir: Path) -> Path:
        """Get the canonical filesystem path where this package should be installed.
        
        This is the single source of truth for where a package lives in apm_modules/.
        
        For regular packages:
            - GitHub: apm_modules/owner/repo/
            - ADO: apm_modules/org/project/repo/
        
        For virtual packages:
            - GitHub: apm_modules/owner/<virtual-package-name>/
            - ADO: apm_modules/org/project/<virtual-package-name>/
        
        Args:
            apm_modules_dir: Path to the apm_modules directory
            
        Returns:
            Path: Absolute path to the package installation directory
        """
        repo_parts = self.repo_url.split("/")
        
        if self.is_virtual:
            # Virtual package: use sanitized package name
            package_name = self.get_virtual_package_name()
            if self.is_azure_devops() and len(repo_parts) >= 3:
                # ADO: org/project/virtual-pkg-name
                return apm_modules_dir / repo_parts[0] / repo_parts[1] / package_name
            elif len(repo_parts) >= 2:
                # GitHub: owner/virtual-pkg-name
                return apm_modules_dir / repo_parts[0] / package_name
        else:
            # Regular package: use full repo path
            if self.is_azure_devops() and len(repo_parts) >= 3:
                # ADO: org/project/repo
                return apm_modules_dir / repo_parts[0] / repo_parts[1] / repo_parts[2]
            elif len(repo_parts) >= 2:
                # GitHub: owner/repo
                return apm_modules_dir / repo_parts[0] / repo_parts[1]
        
        # Fallback: join all parts
        return apm_modules_dir.joinpath(*repo_parts)
    
    @classmethod
    def parse(cls, dependency_str: str) -> "DependencyReference":
        """Parse a dependency string into a DependencyReference.
        
        Supports formats:
        - user/repo
        - user/repo#branch
        - user/repo#v1.0.0
        - user/repo#commit_sha
        - github.com/user/repo#ref
        - user/repo@alias
        - user/repo#ref@alias
        - user/repo/path/to/file.prompt.md (virtual file package)
        - user/repo/collections/name (virtual collection package)
        
        Args:
            dependency_str: The dependency string to parse
            
        Returns:
            DependencyReference: Parsed dependency reference
            
        Raises:
            ValueError: If the dependency string format is invalid
        """
        if not dependency_str.strip():
            raise ValueError("Empty dependency string")
        
        # Check for control characters (newlines, tabs, etc.)
        if any(ord(c) < 32 for c in dependency_str):
            raise ValueError("Dependency string contains invalid control characters")
        
        # SECURITY: Reject protocol-relative URLs (//example.com)
        if dependency_str.startswith('//'):
            raise ValueError("Unsupported Git host. Protocol-relative URLs are not allowed")
        
        # Early detection of virtual packages (3+ path segments)
        # Extract the core path before processing reference (#) and alias (@)
        work_str = dependency_str
        
        # Temporarily remove reference and alias for path segment counting
        temp_str = work_str
        if '@' in temp_str and not temp_str.startswith('git@'):
            temp_str = temp_str.rsplit('@', 1)[0]
        if '#' in temp_str:
            temp_str = temp_str.rsplit('#', 1)[0]
        
        # Check if this looks like a virtual package (3+ path segments)
        # Skip SSH URLs (git@host:owner/repo format)
        is_virtual_package = False
        virtual_path = None
        validated_host = None  # Track if we validated a GitHub hostname
        
        if not temp_str.startswith(('git@', 'https://', 'http://')):
            # SECURITY: Use proper URL parsing instead of substring checks to validate hostnames
            # This prevents bypasses like "evil.com/github.com/repo" or "github.com.evil.com/repo"
            check_str = temp_str
            
            # Try to parse as potential URL with host prefix
            if '/' in check_str:
                first_segment = check_str.split('/')[0]
                
                # If first segment contains a dot, it might be a hostname - VALIDATE IT
                if '.' in first_segment:
                    # Construct a full URL and parse it properly
                    test_url = f"https://{check_str}"
                    try:
                        parsed = urllib.parse.urlparse(test_url)
                        hostname = parsed.hostname
                        
                        # SECURITY CRITICAL: If there's a dot in first segment, it MUST be a valid Git hostname
                        # Otherwise reject it - prevents evil-github.com, github.com.evil.com attacks
                        if hostname and is_supported_git_host(hostname):
                            # Valid Git hosting hostname - extract path after it
                            validated_host = hostname
                            path_parts = parsed.path.lstrip('/').split('/')
                            if len(path_parts) >= 2:
                                # Remove the hostname from check_str by taking everything after first segment
                                check_str = '/'.join(check_str.split('/')[1:])
                        else:
                            # First segment has a dot but is NOT a valid Git host - REJECT
                            raise ValueError(
                                f"Unsupported Git host. Invalid hostname: {hostname or first_segment}"
                            )
                    except (ValueError, AttributeError) as e:
                        # If we can't parse or validate, and first segment has dot, it's suspicious - REJECT
                        if isinstance(e, ValueError) and "Unsupported Git host" in str(e):
                            raise  # Re-raise our security error
                        raise ValueError(
                            f"Unsupported Git host. Could not validate hostname: {first_segment}"
                        )
                elif check_str.startswith('gh/'):
                    # Handle 'gh/' shorthand - only if it's exactly at the start
                    check_str = '/'.join(check_str.split('/')[1:])
            
            # Count segments (owner/repo/path/to/file = 5 segments)
            path_segments = check_str.split('/')
            
            # Filter out empty segments (from double slashes like "user//repo")
            path_segments = [seg for seg in path_segments if seg]
            
            # For Azure DevOps, the base package format is org/project/repo (3 segments)
            # Virtual packages would have 4+ segments: org/project/repo/path/to/file
            # For GitHub, base is owner/repo (2 segments), virtual is 3+ segments
            is_ado = validated_host is not None and is_azure_devops_hostname(validated_host)
            
            # Handle _git in ADO URLs: org/project/_git/repo -> org/project/repo
            if is_ado and '_git' in path_segments:
                git_idx = path_segments.index('_git')
                # Remove _git from the path segments
                path_segments = path_segments[:git_idx] + path_segments[git_idx+1:]
            
            min_base_segments = 3 if is_ado else 2
            min_virtual_segments = min_base_segments + 1
            
            if len(path_segments) >= min_virtual_segments:
                # This is a virtual package!
                # For GitHub: owner/repo/path/to/file.prompt.md
                # For ADO: org/project/repo/path/to/file.prompt.md
                is_virtual_package = True
                
                # Extract virtual path (base repo is derived later)
                virtual_path = '/'.join(path_segments[min_base_segments:])
                
                # Validate virtual package format
                if '/collections/' in check_str or virtual_path.startswith('collections/'):
                    # Collection virtual package
                    pass  # Collections are validated by fetching the .collection.yml
                else:
                    # Individual file virtual package - must end with valid extension
                    valid_extension = any(virtual_path.endswith(ext) for ext in cls.VIRTUAL_FILE_EXTENSIONS)
                    if not valid_extension:
                        raise InvalidVirtualPackageExtensionError(
                            f"Invalid virtual package path '{virtual_path}'. "
                            f"Individual files must end with one of: {', '.join(cls.VIRTUAL_FILE_EXTENSIONS)}"
                        )
        
        # Handle SSH URLs first (before @ processing) to avoid conflict with alias separator
        original_str = dependency_str
        ssh_repo_part = None
        host = None
        # Match patterns like git@host:owner/repo.git
        ssh_match = re.match(r'^git@([^:]+):(.+)$', dependency_str)
        if ssh_match:
            host = ssh_match.group(1)
            ssh_repo_part = ssh_match.group(2)
            if ssh_repo_part.endswith('.git'):
                ssh_repo_part = ssh_repo_part[:-4]

            # Handle reference and alias in SSH URL
            reference = None
            alias = None

            if "@" in ssh_repo_part:
                ssh_repo_part, alias = ssh_repo_part.rsplit("@", 1)
                alias = alias.strip()

            if "#" in ssh_repo_part:
                repo_part, reference = ssh_repo_part.rsplit("#", 1)
                reference = reference.strip()
            else:
                repo_part = ssh_repo_part

            repo_url = repo_part.strip()
        else:
            # Handle alias (@alias) for non-SSH URLs
            alias = None
            if "@" in dependency_str:
                dependency_str, alias = dependency_str.rsplit("@", 1)
                alias = alias.strip()
            
            # Handle reference (#ref)
            reference = None
            if "#" in dependency_str:
                repo_part, reference = dependency_str.rsplit("#", 1)
                reference = reference.strip()
            else:
                repo_part = dependency_str
            
            # SECURITY: Use urllib.parse for all URL validation to avoid substring vulnerabilities
            
            repo_url = repo_part.strip()
            
            # For virtual packages, extract just the owner/repo part (or org/project/repo for ADO)
            if is_virtual_package and not repo_url.startswith(("https://", "http://")):
                # Virtual packages have format: owner/repo/path/to/file or host/owner/repo/path/to/file
                # For ADO: dev.azure.com/org/project/repo/path/to/file (4+ with host) or org/project/repo/path (3+ without host)
                parts = repo_url.split("/")
                
                # Handle _git in path: org/project/_git/repo -> org/project/repo
                if '_git' in parts:
                    git_idx = parts.index('_git')
                    parts = parts[:git_idx] + parts[git_idx+1:]
                
                # Check if starts with host
                if len(parts) >= 3 and is_supported_git_host(parts[0]):
                    host = parts[0]
                    # For ADO: dev.azure.com/org/project/repo/path -> extract org/project/repo
                    # For GitHub: github.com/owner/repo/path -> extract owner/repo
                    if is_azure_devops_hostname(parts[0]):
                        if len(parts) < 5:  # host + org + project + repo + at least one path segment
                            raise ValueError("Invalid Azure DevOps virtual package format: must be dev.azure.com/org/project/repo/path")
                        repo_url = "/".join(parts[1:4])  # org/project/repo
                    else:
                        repo_url = "/".join(parts[1:3])  # owner/repo
                elif len(parts) >= 2:
                    # No host prefix
                    if not host:
                        host = default_host()
                    # Use validated_host to check if this is ADO
                    if validated_host and is_azure_devops_hostname(validated_host):
                        if len(parts) < 4:  # org + project + repo + at least one path segment
                            raise ValueError("Invalid Azure DevOps virtual package format: expected at least org/project/repo/path")
                        repo_url = "/".join(parts[:3])  # org/project/repo
                    else:
                        repo_url = "/".join(parts[:2])  # owner/repo
            
            # Normalize to URL format for secure parsing - always use urllib.parse, never substring checks
            if repo_url.startswith(("https://", "http://")):
                # Already a full URL - parse directly
                parsed_url = urllib.parse.urlparse(repo_url)
                host = parsed_url.hostname or ""
            else:
                # Safely construct a URL from various input formats. Support GitHub, GitHub Enterprise,
                # Azure DevOps, and other Git hosting platforms.
                parts = repo_url.split("/")
                
                # Handle _git in path for ADO URLs
                if '_git' in parts:
                    git_idx = parts.index('_git')
                    parts = parts[:git_idx] + parts[git_idx+1:]
                
                # host/user/repo  OR user/repo (no host)
                if len(parts) >= 3 and is_supported_git_host(parts[0]):
                    # Format with host prefix: github.com/user/repo OR dev.azure.com/org/project/repo
                    host = parts[0]
                    if is_azure_devops_hostname(host) and len(parts) >= 4:
                        # ADO format: dev.azure.com/org/project/repo
                        user_repo = "/".join(parts[1:4])
                    else:
                        # GitHub format: github.com/user/repo
                        user_repo = "/".join(parts[1:3])
                elif len(parts) >= 2 and "." not in parts[0]:
                    # Format without host: user/repo or org/project/repo (for ADO)
                    if not host:
                        host = default_host()
                    # Check if default host is ADO
                    if is_azure_devops_hostname(host) and len(parts) >= 3:
                        user_repo = "/".join(parts[:3])  # org/project/repo
                    else:
                        user_repo = "/".join(parts[:2])  # user/repo
                else:
                    raise ValueError(f"Use 'user/repo' or 'github.com/user/repo' or 'dev.azure.com/org/project/repo' format")

                # Validate format before URL construction (security critical)
                if not user_repo or "/" not in user_repo:
                    raise ValueError(f"Invalid repository format: {repo_url}. Expected 'user/repo' or 'org/project/repo'")

                uparts = user_repo.split("/")
                is_ado_host = host and is_azure_devops_hostname(host)
                expected_parts = 3 if is_ado_host else 2
                
                if len(uparts) < expected_parts:
                    if is_ado_host:
                        raise ValueError(f"Invalid Azure DevOps repository format: {repo_url}. Expected 'org/project/repo'")
                    else:
                        raise ValueError(f"Invalid repository format: {repo_url}. Expected 'user/repo'")
                
                # Security: validate characters to prevent injection
                for part in uparts:
                    if not re.match(r'^[a-zA-Z0-9._-]+$', part.rstrip('.git')):
                        raise ValueError(f"Invalid repository path component: {part}")

                # Safely construct URL using detected host
                github_url = urllib.parse.urljoin(f"https://{host}/", user_repo)
                parsed_url = urllib.parse.urlparse(github_url)

            # SECURITY: Validate that this is actually a supported Git host URL.
            # Accept github.com, GitHub Enterprise, Azure DevOps, etc. Use parsed_url.hostname
            hostname = parsed_url.hostname or ""
            if not is_supported_git_host(hostname):
                raise ValueError(f"Unsupported Git host, got hostname: {parsed_url.netloc}")
            
            # Extract and validate the path
            path = parsed_url.path.strip("/")
            if not path:
                raise ValueError("Repository path cannot be empty")
            
            # Remove .git suffix if present
            if path.endswith(".git"):
                path = path[:-4]
            
            # Handle _git in parsed path for ADO URLs
            path_parts = path.split("/")
            if '_git' in path_parts:
                git_idx = path_parts.index('_git')
                path_parts = path_parts[:git_idx] + path_parts[git_idx+1:]
            
            # Validate path format based on host type
            is_ado_host = is_azure_devops_hostname(hostname)
            expected_parts = 3 if is_ado_host else 2
            
            if len(path_parts) != expected_parts:
                if is_ado_host:
                    raise ValueError(f"Invalid Azure DevOps repository path: expected 'org/project/repo', got '{path}'")
                else:
                    raise ValueError(f"Invalid repository path: expected 'user/repo', got '{path}'")
            
            # Validate all path parts contain only allowed characters
            for i, part in enumerate(path_parts):
                if not part:
                    raise ValueError(f"Invalid repository format: path component {i+1} cannot be empty")
                if not re.match(r'^[a-zA-Z0-9._-]+$', part):
                    raise ValueError(f"Invalid repository path component: {part}")
            
            repo_url = "/".join(path_parts)
            
            # If host not set via SSH or parsed parts, default to default_host()
            if not host:
                host = default_host()

        
        # Validate repo format based on host type
        is_ado_final = host and is_azure_devops_hostname(host)
        if is_ado_final:
            # ADO format: org/project/repo (3 segments)
            if not re.match(r'^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$', repo_url):
                raise ValueError(f"Invalid Azure DevOps repository format: {repo_url}. Expected 'org/project/repo'")
            # Extract ADO-specific fields
            ado_parts = repo_url.split('/')
            ado_organization = ado_parts[0]
            ado_project = ado_parts[1]
            ado_repo = ado_parts[2]
        else:
            # GitHub format: user/repo (2 segments)
            if not re.match(r'^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$', repo_url):
                raise ValueError(f"Invalid repository format: {repo_url}. Expected 'user/repo'")
            ado_organization = None
            ado_project = None
            ado_repo = None
        
        # Validate alias characters if present
        if alias and not re.match(r'^[a-zA-Z0-9._-]+$', alias):
            raise ValueError(f"Invalid alias: {alias}. Aliases can only contain letters, numbers, dots, underscores, and hyphens")

        return cls(
            repo_url=repo_url,
            host=host,
            reference=reference,
            alias=alias,
            virtual_path=virtual_path,
            is_virtual=is_virtual_package,
            ado_organization=ado_organization,
            ado_project=ado_project,
            ado_repo=ado_repo
        )

    def to_github_url(self) -> str:
        """Convert to full repository URL.
        
        For Azure DevOps, generates: https://dev.azure.com/org/project/_git/repo
        For GitHub, generates: https://github.com/owner/repo
        """
        host = self.host or default_host()
        
        if self.is_azure_devops():
            # ADO format: https://dev.azure.com/org/project/_git/repo
            return f"https://{host}/{self.ado_organization}/{self.ado_project}/_git/{self.ado_repo}"
        else:
            # GitHub format: https://github.com/owner/repo
            return f"https://{host}/{self.repo_url}"
    
    def to_clone_url(self) -> str:
        """Convert to a clone-friendly URL (same as to_github_url for most purposes)."""
        return self.to_github_url()

    def get_display_name(self) -> str:
        """Get display name for this dependency (alias or repo name)."""
        if self.alias:
            return self.alias
        if self.is_virtual:
            return self.get_virtual_package_name()
        return self.repo_url  # Full repo URL for disambiguation

    def __str__(self) -> str:
        """String representation of the dependency reference."""
        if self.host:
            result = f"{self.host}/{self.repo_url}"
        else:
            result = self.repo_url
        if self.virtual_path:
            result += f"/{self.virtual_path}"
        if self.reference:
            result += f"#{self.reference}"
        if self.alias:
            result += f"@{self.alias}"
        return result


@dataclass
class APMPackage:
    """Represents an APM package with metadata."""
    name: str
    version: str
    description: Optional[str] = None
    author: Optional[str] = None
    license: Optional[str] = None
    source: Optional[str] = None  # Source location (for dependencies)
    resolved_commit: Optional[str] = None  # Resolved commit SHA (for dependencies)
    dependencies: Optional[Dict[str, List[Union[DependencyReference, str]]]] = None  # Mixed types for APM/MCP
    scripts: Optional[Dict[str, str]] = None
    package_path: Optional[Path] = None  # Local path to package
    target: Optional[str] = None  # Target agent: vscode, claude, or all (applies to compile and install)
    
    @classmethod
    def from_apm_yml(cls, apm_yml_path: Path) -> "APMPackage":
        """Load APM package from apm.yml file.
        
        Args:
            apm_yml_path: Path to the apm.yml file
            
        Returns:
            APMPackage: Loaded package instance
            
        Raises:
            ValueError: If the file is invalid or missing required fields
            FileNotFoundError: If the file doesn't exist
        """
        if not apm_yml_path.exists():
            raise FileNotFoundError(f"apm.yml not found: {apm_yml_path}")
        
        try:
            with open(apm_yml_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML format in {apm_yml_path}: {e}")
        
        if not isinstance(data, dict):
            raise ValueError(f"apm.yml must contain a YAML object, got {type(data)}")
        
        # Required fields
        if 'name' not in data:
            raise ValueError("Missing required field 'name' in apm.yml")
        if 'version' not in data:
            raise ValueError("Missing required field 'version' in apm.yml")
        
        # Parse dependencies
        dependencies = None
        if 'dependencies' in data and isinstance(data['dependencies'], dict):
            dependencies = {}
            for dep_type, dep_list in data['dependencies'].items():
                if isinstance(dep_list, list):
                    if dep_type == 'apm':
                        # APM dependencies need to be parsed as DependencyReference objects
                        parsed_deps = []
                        for dep_str in dep_list:
                            if isinstance(dep_str, str):
                                try:
                                    parsed_deps.append(DependencyReference.parse(dep_str))
                                except ValueError as e:
                                    raise ValueError(f"Invalid APM dependency '{dep_str}': {e}")
                        dependencies[dep_type] = parsed_deps
                    else:
                        # Other dependencies (like MCP) remain as strings
                        dependencies[dep_type] = [str(dep) for dep in dep_list if isinstance(dep, str)]
        
        return cls(
            name=data['name'],
            version=data['version'],
            description=data.get('description'),
            author=data.get('author'),
            license=data.get('license'),
            dependencies=dependencies,
            scripts=data.get('scripts'),
            package_path=apm_yml_path.parent,
            target=data.get('target'),
        )
    
    def get_apm_dependencies(self) -> List[DependencyReference]:
        """Get list of APM dependencies."""
        if not self.dependencies or 'apm' not in self.dependencies:
            return []
        # Filter to only return DependencyReference objects
        return [dep for dep in self.dependencies['apm'] if isinstance(dep, DependencyReference)]
    
    def get_mcp_dependencies(self) -> List[str]:
        """Get list of MCP dependencies (as strings for compatibility)."""
        if not self.dependencies or 'mcp' not in self.dependencies:
            return []
        # MCP deps are stored as strings, not DependencyReference objects
        return [str(dep) if isinstance(dep, DependencyReference) else dep 
                for dep in self.dependencies.get('mcp', [])]
    
    def has_apm_dependencies(self) -> bool:
        """Check if this package has APM dependencies."""
        return bool(self.get_apm_dependencies())


@dataclass
class ValidationResult:
    """Result of APM package validation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    package: Optional[APMPackage] = None
    
    def __init__(self):
        self.is_valid = True
        self.errors = []
        self.warnings = []
        self.package = None
    
    def add_error(self, error: str) -> None:
        """Add a validation error."""
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str) -> None:
        """Add a validation warning."""
        self.warnings.append(warning)
    
    def has_issues(self) -> bool:
        """Check if there are any errors or warnings."""
        return bool(self.errors or self.warnings)
    
    def summary(self) -> str:
        """Get a summary of validation results."""
        if self.is_valid and not self.warnings:
            return "✅ Package is valid"
        elif self.is_valid and self.warnings:
            return f"⚠️ Package is valid with {len(self.warnings)} warning(s)"
        else:
            return f"❌ Package is invalid with {len(self.errors)} error(s)"


@dataclass
class PackageInfo:
    """Information about a downloaded/installed package."""
    package: APMPackage
    install_path: Path
    resolved_reference: Optional[ResolvedReference] = None
    installed_at: Optional[str] = None  # ISO timestamp
    dependency_ref: Optional["DependencyReference"] = None  # Original dependency reference for canonical string
    
    def get_canonical_dependency_string(self) -> str:
        """Get the canonical dependency string for this package.
        
        Used for orphan detection - this is the unique identifier as stored in apm.yml.
        For virtual packages, includes the full path (e.g., owner/repo/collections/name).
        For regular packages, just the repo URL (e.g., owner/repo).
        
        Returns:
            str: Canonical dependency string, or package source/name as fallback
        """
        if self.dependency_ref:
            return self.dependency_ref.get_canonical_dependency_string()
        # Fallback to package source or name
        return self.package.source or self.package.name or "unknown"
    
    def get_primitives_path(self) -> Path:
        """Get path to the .apm directory for this package."""
        return self.install_path / ".apm"
    
    def has_primitives(self) -> bool:
        """Check if the package has any primitives."""
        apm_dir = self.get_primitives_path()
        if not apm_dir.exists():
            return False
        
        # Check for any primitive files in subdirectories
        for primitive_type in ['instructions', 'chatmodes', 'contexts', 'prompts']:
            primitive_dir = apm_dir / primitive_type
            if primitive_dir.exists() and any(primitive_dir.iterdir()):
                return True
        return False


def validate_apm_package(package_path: Path) -> ValidationResult:
    """Validate that a directory contains a valid APM package.
    
    Args:
        package_path: Path to the directory to validate
        
    Returns:
        ValidationResult: Validation results with any errors/warnings
    """
    result = ValidationResult()
    
    # Check if directory exists
    if not package_path.exists():
        result.add_error(f"Package directory does not exist: {package_path}")
        return result
    
    if not package_path.is_dir():
        result.add_error(f"Package path is not a directory: {package_path}")
        return result
    
    # Check for apm.yml
    apm_yml_path = package_path / "apm.yml"
    if not apm_yml_path.exists():
        result.add_error("Missing required file: apm.yml")
        return result
    
    # Try to parse apm.yml
    try:
        package = APMPackage.from_apm_yml(apm_yml_path)
        result.package = package
    except (ValueError, FileNotFoundError) as e:
        result.add_error(f"Invalid apm.yml: {e}")
        return result
    
    # Check for .apm directory
    apm_dir = package_path / ".apm"
    if not apm_dir.exists():
        result.add_error("Missing required directory: .apm/")
        return result
    
    if not apm_dir.is_dir():
        result.add_error(".apm must be a directory")
        return result
    
    # Check if .apm directory has any content
    primitive_types = ['instructions', 'chatmodes', 'contexts', 'prompts']
    has_primitives = False
    
    for primitive_type in primitive_types:
        primitive_dir = apm_dir / primitive_type
        if primitive_dir.exists() and primitive_dir.is_dir():
            # Check if directory has any markdown files
            md_files = list(primitive_dir.glob("*.md"))
            if md_files:
                has_primitives = True
                # Validate each primitive file has basic structure
                for md_file in md_files:
                    try:
                        content = md_file.read_text(encoding='utf-8')
                        if not content.strip():
                            result.add_warning(f"Empty primitive file: {md_file.relative_to(package_path)}")
                    except Exception as e:
                        result.add_warning(f"Could not read primitive file {md_file.relative_to(package_path)}: {e}")
    
    if not has_primitives:
        result.add_warning("No primitive files found in .apm/ directory")
    
    # Version format validation (basic semver check)
    if package and package.version is not None:
        # Defensive cast in case YAML parsed a numeric like 1 or 1.0 
        version_str = str(package.version).strip()
        if not re.match(r'^\d+\.\d+\.\d+', version_str):
            result.add_warning(f"Version '{version_str}' doesn't follow semantic versioning (x.y.z)")
    
    return result


def parse_git_reference(ref_string: str) -> tuple[GitReferenceType, str]:
    """Parse a git reference string to determine its type.
    
    Args:
        ref_string: Git reference (branch, tag, or commit)
        
    Returns:
        tuple: (GitReferenceType, cleaned_reference)
    """
    if not ref_string:
        return GitReferenceType.BRANCH, "main"  # Default to main branch
    
    ref = ref_string.strip()
    
    # Check if it looks like a commit SHA (40 hex chars or 7+ hex chars)
    if re.match(r'^[a-f0-9]{7,40}$', ref.lower()):
        return GitReferenceType.COMMIT, ref
    
    # Check if it looks like a semantic version tag
    if re.match(r'^v?\d+\.\d+\.\d+', ref):
        return GitReferenceType.TAG, ref
    
    # Otherwise assume it's a branch
    return GitReferenceType.BRANCH, ref