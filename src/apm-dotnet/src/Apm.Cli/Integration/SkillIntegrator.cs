using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using Apm.Cli.Models;
using Apm.Cli.Primitives;

namespace Apm.Cli.Integration;

/// <summary>Result of skill integration operation.</summary>
public record SkillIntegrationResult(
    bool SkillCreated,
    bool SkillUpdated,
    bool SkillSkipped,
    string? SkillPath,
    int ReferencesCopied,
    int LinksResolved = 0);

/// <summary>Skill name utilities and package type routing.</summary>
public static class SkillNameUtils
{
    /// <summary>
    /// Convert a package name to hyphen-case for Claude Skills spec.
    /// Max 64 characters.
    /// </summary>
    public static string ToHyphenCase(string name)
    {
        // Extract just the repo name if it's owner/repo format
        if (name.Contains('/'))
            name = name.Split('/')[^1];

        // Replace underscores and spaces with hyphens
        var result = name.Replace('_', '-').Replace(' ', '-');

        // Insert hyphens before uppercase letters (camelCase to hyphen-case)
        result = Regex.Replace(result, @"([a-z])([A-Z])", "$1-$2");

        // Convert to lowercase and remove any invalid characters
        result = Regex.Replace(result.ToLowerInvariant(), @"[^a-z0-9-]", "");

        // Remove consecutive hyphens
        result = Regex.Replace(result, @"-+", "-");

        // Remove leading/trailing hyphens, truncate to 64 chars
        result = result.Trim('-');
        return result.Length > 64 ? result[..64] : result;
    }

    /// <summary>
    /// Validate skill name per agentskills.io spec.
    /// Returns (isValid, errorMessage).
    /// </summary>
    public static (bool IsValid, string ErrorMessage) ValidateSkillName(string name)
    {
        if (name.Length < 1)
            return (false, "Skill name cannot be empty");

        if (name.Length > 64)
            return (false, $"Skill name must be 1-64 characters (got {name.Length})");

        if (name.Contains("--"))
            return (false, "Skill name cannot contain consecutive hyphens (--)");

        if (name.StartsWith('-'))
            return (false, "Skill name cannot start with a hyphen");

        if (name.EndsWith('-'))
            return (false, "Skill name cannot end with a hyphen");

        var pattern = new Regex(@"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$");
        if (!pattern.IsMatch(name))
        {
            if (name.Any(char.IsUpper))
                return (false, "Skill name must be lowercase (no uppercase letters)");
            if (name.Contains('_'))
                return (false, "Skill name cannot contain underscores (use hyphens instead)");
            if (name.Contains(' '))
                return (false, "Skill name cannot contain spaces (use hyphens instead)");

            var invalidChars = new HashSet<char>(Regex.Matches(name, @"[^a-z0-9-]").Select(m => m.Value[0]));
            if (invalidChars.Count > 0)
                return (false, $"Skill name contains invalid characters: {string.Join(", ", invalidChars.OrderBy(c => c))}");

            return (false, "Skill name must be lowercase alphanumeric with hyphens only");
        }

        return (true, "");
    }

    /// <summary>Normalize any package name to a valid skill name.</summary>
    public static string NormalizeSkillName(string name) => ToHyphenCase(name);

    /// <summary>Get effective package content type based on explicit type or package structure.</summary>
    public static PackageContentType GetEffectiveType(PackageInfo packageInfo)
    {
        // Priority 1: Explicit type field in apm.yml
        if (packageInfo.Package.Type is not null)
            return packageInfo.Package.Type.Value;

        // Priority 2: Check if package has SKILL.md (via package_type field)
        if (packageInfo.PackageTypeResult is PackageType.ClaudeSkill or PackageType.Hybrid)
            return PackageContentType.Skill;

        // Priority 3: Default to INSTRUCTIONS
        return PackageContentType.Instructions;
    }

    /// <summary>Determine if package should be installed as a native skill.</summary>
    public static bool ShouldInstallSkill(PackageInfo packageInfo)
    {
        var effectiveType = GetEffectiveType(packageInfo);
        return effectiveType is PackageContentType.Skill or PackageContentType.Hybrid;
    }

    /// <summary>Determine if package should compile to AGENTS.md/CLAUDE.md.</summary>
    public static bool ShouldCompileInstructions(PackageInfo packageInfo)
    {
        var effectiveType = GetEffectiveType(packageInfo);
        return effectiveType is PackageContentType.Instructions or PackageContentType.Hybrid;
    }
}

/// <summary>Handles generation of SKILL.md files for Claude Code integration.</summary>
public class SkillIntegrator
{
    /// <summary>Check if skill integration should be performed.</summary>
    public bool ShouldIntegrate(string projectRoot) => true;

    /// <summary>Find all instruction files in a package.</summary>
    public List<string> FindInstructionFiles(string packagePath)
    {
        var dir = Path.Combine(packagePath, ".apm", "instructions");
        return Directory.Exists(dir)
            ? Directory.EnumerateFiles(dir, "*.instructions.md").ToList()
            : [];
    }

    /// <summary>Find all agent files in a package.</summary>
    public List<string> FindAgentFiles(string packagePath)
    {
        var dir = Path.Combine(packagePath, ".apm", "agents");
        return Directory.Exists(dir)
            ? Directory.EnumerateFiles(dir, "*.agent.md").ToList()
            : [];
    }

    /// <summary>Find all prompt files in a package.</summary>
    public List<string> FindPromptFiles(string packagePath)
    {
        var promptFiles = new List<string>();

        if (Directory.Exists(packagePath))
            promptFiles.AddRange(Directory.EnumerateFiles(packagePath, "*.prompt.md", SearchOption.TopDirectoryOnly));

        var apmPrompts = Path.Combine(packagePath, ".apm", "prompts");
        if (Directory.Exists(apmPrompts))
            promptFiles.AddRange(Directory.EnumerateFiles(apmPrompts, "*.prompt.md"));

        return promptFiles;
    }

    /// <summary>Find all context/memory files in a package.</summary>
    public List<string> FindContextFiles(string packagePath)
    {
        var contextFiles = new List<string>();

        var apmContext = Path.Combine(packagePath, ".apm", "context");
        if (Directory.Exists(apmContext))
            contextFiles.AddRange(Directory.EnumerateFiles(apmContext, "*.context.md"));

        var apmMemory = Path.Combine(packagePath, ".apm", "memory");
        if (Directory.Exists(apmMemory))
            contextFiles.AddRange(Directory.EnumerateFiles(apmMemory, "*.memory.md"));

        return contextFiles;
    }

    /// <summary>Parse APM metadata from YAML frontmatter in a SKILL.md file.</summary>
    internal Dictionary<string, string> ParseSkillMetadata(string filePath)
    {
        try
        {
            var (metadata, _) = PrimitiveParser.ParseFrontmatter(File.ReadAllText(filePath));
            if (metadata.TryGetValue("metadata", out var metaObj) && metaObj is Dictionary<object, object> metaDict)
            {
                return new Dictionary<string, string>
                {
                    ["Version"] = metaDict.TryGetValue("apm_version", out var v) ? v?.ToString() ?? "" : "",
                    ["Commit"] = metaDict.TryGetValue("apm_commit", out var c) ? c?.ToString() ?? "" : "",
                    ["Package"] = metaDict.TryGetValue("apm_package", out var p) ? p?.ToString() ?? "" : "",
                    ["ContentHash"] = metaDict.TryGetValue("apm_content_hash", out var h) ? h?.ToString() ?? "" : ""
                };
            }
            return [];
        }
        catch
        {
            return [];
        }
    }

    /// <summary>Calculate a hash of all source files that go into SKILL.md.</summary>
    internal string CalculateSourceHash(string packagePath)
    {
        var allFiles = new List<string>();
        allFiles.AddRange(FindInstructionFiles(packagePath));
        allFiles.AddRange(FindAgentFiles(packagePath));
        allFiles.AddRange(FindContextFiles(packagePath));
        allFiles.Sort(StringComparer.Ordinal);

        using var hasher = SHA256.Create();
        foreach (var filePath in allFiles)
        {
            try
            {
                var content = File.ReadAllText(filePath);
                hasher.TransformBlock(Encoding.UTF8.GetBytes(content), 0,
                    Encoding.UTF8.GetByteCount(content), null, 0);
            }
            catch
            {
                // Skip unreadable files
            }
        }

        hasher.TransformFinalBlock([], 0, 0);
        return Convert.ToHexStringLower(hasher.Hash!);
    }

    /// <summary>Determine if an existing SKILL.md should be updated.</summary>
    internal (bool ShouldUpdate, bool WasModified) ShouldUpdateSkill(
        Dictionary<string, string> existingMetadata, PackageInfo packageInfo, string packagePath)
    {
        if (existingMetadata.Count == 0)
            return (true, false);

        var newVersion = packageInfo.Package.Version;
        var newCommit = packageInfo.ResolvedReference?.ResolvedCommit ?? "unknown";

        var existingVersion = existingMetadata.GetValueOrDefault("Version", "");
        var existingCommit = existingMetadata.GetValueOrDefault("Commit", "");

        var wasModified = false;
        var storedHash = existingMetadata.GetValueOrDefault("ContentHash", "");
        if (!string.IsNullOrEmpty(storedHash))
        {
            var currentHash = CalculateSourceHash(packagePath);
            wasModified = currentHash != storedHash && !string.IsNullOrEmpty(currentHash);
        }

        var shouldUpdate = existingVersion != newVersion || existingCommit != newCommit;
        return (shouldUpdate, wasModified);
    }

    /// <summary>Extract keywords from file names for discovery hints.</summary>
    internal HashSet<string> ExtractKeywords(List<string> files)
    {
        var keywords = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var f in files)
        {
            var stem = Path.GetFileNameWithoutExtension(f).Split('.')[0];
            var words = stem.Replace('-', ' ').Replace('_', ' ').Split(' ', StringSplitOptions.RemoveEmptyEntries);
            foreach (var w in words)
            {
                if (w.Length > 3)
                    keywords.Add(w.ToLowerInvariant());
            }
        }
        return keywords;
    }

    /// <summary>Generate description optimized for Claude skill discovery.</summary>
    internal string GenerateDiscoveryDescription(PackageInfo packageInfo, Dictionary<string, List<string>> primitives)
    {
        var baseDesc = packageInfo.Package.Description ?? $"Expertise from {packageInfo.Package.Name}";

        var allFiles = primitives.Values.SelectMany(f => f).ToList();
        var keywords = ExtractKeywords(allFiles);

        var hint = "";
        if (keywords.Count > 0)
        {
            var triggers = string.Join(", ", keywords.OrderBy(k => k).Take(5));
            hint = $" Use when working with {triggers}.";
        }

        var result = baseDesc + hint;
        return result.Length > 1024 ? result[..1024] : result;
    }

    /// <summary>Generate concise SKILL.md body content.</summary>
    internal string GenerateSkillContent(PackageInfo packageInfo, Dictionary<string, List<string>> primitives, string skillDir)
    {
        var pkg = packageInfo.Package;
        var sections = new List<string>
        {
            $"# {pkg.Name}",
            "",
            pkg.Description ?? $"Expertise from {pkg.Source ?? pkg.Name}.",
            "",
            "## What's Included",
            "",
            "| Directory | Contents |",
            "|-----------|----------|"
        };

        var typeLabels = new Dictionary<string, string>
        {
            ["instructions"] = "Guidelines & standards",
            ["agents"] = "Specialist personas",
            ["prompts"] = "Executable workflows",
            ["context"] = "Reference documents"
        };

        foreach (var (ptype, label) in typeLabels)
        {
            if (primitives.TryGetValue(ptype, out var files) && files.Count > 0)
            {
                sections.Add($"| [{ptype}/]({ptype}/) | {files.Count} {label.ToLowerInvariant()} |");
            }
        }

        sections.Add("");
        sections.Add("Read files in each directory for detailed guidance.");

        return string.Join("\n", sections);
    }

    /// <summary>Copy all primitives to typed subdirectories in skill directory.</summary>
    internal int CopyPrimitivesToSkill(Dictionary<string, List<string>> primitives, string skillDir)
    {
        var totalCopied = 0;

        foreach (var (ptype, files) in primitives)
        {
            if (files.Count == 0) continue;

            var subdir = Path.Combine(skillDir, ptype);
            Directory.CreateDirectory(subdir);

            foreach (var srcFile in files)
            {
                var targetPath = Path.Combine(subdir, Path.GetFileName(srcFile));
                try
                {
                    File.Copy(srcFile, targetPath, overwrite: true);
                    totalCopied++;
                }
                catch
                {
                    // Skip files that can't be copied
                }
            }
        }

        return totalCopied;
    }

    /// <summary>Generate the SKILL.md file with proper frontmatter.</summary>
    internal int GenerateSkillFile(PackageInfo packageInfo, Dictionary<string, List<string>> primitives, string skillDir)
    {
        var skillPath = Path.Combine(skillDir, "SKILL.md");
        var packagePath = packageInfo.InstallPath;

        var repoUrl = packageInfo.Package.Source ?? packageInfo.Package.Name;
        var skillName = SkillNameUtils.ToHyphenCase(repoUrl);
        var skillDescription = GenerateDiscoveryDescription(packageInfo, primitives);
        var contentHash = CalculateSourceHash(packagePath);

        var filesCopied = CopyPrimitivesToSkill(primitives, skillDir);
        var bodyContent = GenerateSkillContent(packageInfo, primitives, skillDir);

        // Build frontmatter
        var commit = packageInfo.ResolvedReference?.ResolvedCommit ?? "unknown";
        var installedAt = packageInfo.InstalledAt ?? DateTime.Now.ToString("o");

        var sb = new StringBuilder();
        sb.AppendLine("---");
        sb.AppendLine($"name: {skillName}");
        sb.AppendLine($"description: {skillDescription}");
        sb.AppendLine("metadata:");
        sb.AppendLine($"  apm_package: {packageInfo.GetCanonicalDependencyString()}");
        sb.AppendLine($"  apm_version: {packageInfo.Package.Version}");
        sb.AppendLine($"  apm_commit: {commit}");
        sb.AppendLine($"  apm_installed_at: {installedAt}");
        sb.AppendLine($"  apm_content_hash: {contentHash}");
        sb.AppendLine("---");
        sb.AppendLine();
        sb.Append(bodyContent);

        File.WriteAllText(skillPath, sb.ToString());
        return filesCopied;
    }

    /// <summary>Copy a native Skill (with existing SKILL.md) to .github/skills/ and optionally .claude/skills/.</summary>
    internal SkillIntegrationResult IntegrateNativeSkill(PackageInfo packageInfo, string projectRoot, string sourceSkillMd)
    {
        var packagePath = packageInfo.InstallPath;
        var rawSkillName = Path.GetFileName(packagePath);

        var (isValid, _) = SkillNameUtils.ValidateSkillName(rawSkillName);
        var skillName = isValid ? rawSkillName : SkillNameUtils.NormalizeSkillName(rawSkillName);

        // Primary target: .github/skills/
        var githubSkillDir = Path.Combine(projectRoot, ".github", "skills", skillName);
        var githubSkillMd = Path.Combine(githubSkillDir, "SKILL.md");

        var skillCreated = !Directory.Exists(githubSkillDir);

        // Copy to .github/skills/
        if (Directory.Exists(githubSkillDir))
            Directory.Delete(githubSkillDir, recursive: true);

        Directory.CreateDirectory(Path.GetDirectoryName(githubSkillDir)!);
        CopyDirectory(packagePath, githubSkillDir);

        var filesCopied = Directory.EnumerateFiles(githubSkillDir, "*", SearchOption.AllDirectories).Count();

        // T7: Copy to .claude/skills/ if .claude/ exists
        var claudeDir = Path.Combine(projectRoot, ".claude");
        if (Directory.Exists(claudeDir))
        {
            var claudeSkillDir = Path.Combine(claudeDir, "skills", skillName);
            if (Directory.Exists(claudeSkillDir))
                Directory.Delete(claudeSkillDir, recursive: true);

            Directory.CreateDirectory(Path.GetDirectoryName(claudeSkillDir)!);
            CopyDirectory(packagePath, claudeSkillDir);
        }

        return new SkillIntegrationResult(
            SkillCreated: skillCreated,
            SkillUpdated: !skillCreated,
            SkillSkipped: false,
            SkillPath: githubSkillMd,
            ReferencesCopied: filesCopied,
            LinksResolved: 0);
    }

    /// <summary>Generate SKILL.md for a package in .github/skills/ directory.</summary>
    public SkillIntegrationResult IntegratePackageSkill(PackageInfo packageInfo, string projectRoot)
    {
        // Check if package type allows skill installation (T4 routing)
        if (!SkillNameUtils.ShouldInstallSkill(packageInfo))
        {
            return new SkillIntegrationResult(false, false, true, null, 0, 0);
        }

        // Skip virtual FILE and COLLECTION packages
        if (packageInfo.DependencyRef is { IsVirtual: true })
        {
            if (!packageInfo.DependencyRef.IsVirtualSubdirectory())
            {
                return new SkillIntegrationResult(false, false, true, null, 0, 0);
            }
        }

        var packagePath = packageInfo.InstallPath;

        // Check if this is a native Skill (already has SKILL.md at root)
        var sourceSkillMd = Path.Combine(packagePath, "SKILL.md");
        if (File.Exists(sourceSkillMd))
        {
            return IntegrateNativeSkill(packageInfo, projectRoot, sourceSkillMd);
        }

        // Discover all primitives for APM packages without SKILL.md
        var primitives = new Dictionary<string, List<string>>
        {
            ["instructions"] = FindInstructionFiles(packagePath),
            ["agents"] = FindAgentFiles(packagePath),
            ["prompts"] = FindPromptFiles(packagePath),
            ["context"] = FindContextFiles(packagePath)
        };

        // Filter out empty lists
        primitives = primitives.Where(kv => kv.Value.Count > 0)
            .ToDictionary(kv => kv.Key, kv => kv.Value);

        if (primitives.Count == 0)
        {
            return new SkillIntegrationResult(false, false, true, null, 0, 0);
        }

        // Determine target path
        var skillName = Path.GetFileName(packagePath);
        var skillDir = Path.Combine(projectRoot, ".github", "skills", skillName);
        Directory.CreateDirectory(skillDir);

        var skillPath = Path.Combine(skillDir, "SKILL.md");

        bool skillCreated = false, skillUpdated = false, skillSkipped = false;
        var filesCopied = 0;

        if (File.Exists(skillPath))
        {
            var existingMetadata = ParseSkillMetadata(skillPath);
            var (shouldUpdate, _) = ShouldUpdateSkill(existingMetadata, packageInfo, packagePath);

            if (shouldUpdate)
            {
                filesCopied = GenerateSkillFile(packageInfo, primitives, skillDir);
                skillUpdated = true;
                SyncToClaudeSkills(packageInfo, primitives, skillName, projectRoot);
            }
            else
            {
                skillSkipped = true;
            }
        }
        else
        {
            filesCopied = GenerateSkillFile(packageInfo, primitives, skillDir);
            skillCreated = true;
            SyncToClaudeSkills(packageInfo, primitives, skillName, projectRoot);
        }

        return new SkillIntegrationResult(
            SkillCreated: skillCreated,
            SkillUpdated: skillUpdated,
            SkillSkipped: skillSkipped,
            SkillPath: (skillCreated || skillUpdated) ? skillPath : null,
            ReferencesCopied: filesCopied,
            LinksResolved: 0);
    }

    /// <summary>Copy generated skill to .claude/skills/ if .claude/ directory exists (T7).</summary>
    internal string? SyncToClaudeSkills(
        PackageInfo packageInfo, Dictionary<string, List<string>> primitives, string skillName, string projectRoot)
    {
        var claudeDir = Path.Combine(projectRoot, ".claude");
        if (!Directory.Exists(claudeDir))
            return null;

        var claudeSkillDir = Path.Combine(claudeDir, "skills", skillName);
        Directory.CreateDirectory(claudeSkillDir);

        GenerateSkillFile(packageInfo, primitives, claudeSkillDir);
        return claudeSkillDir;
    }

    /// <summary>Copy skill directory to .github/skills/ and optionally .claude/skills/.</summary>
    public static (string? GithubPath, string? ClaudePath) CopySkillToTarget(
        PackageInfo packageInfo, string sourcePath, string targetBase)
    {
        if (!SkillNameUtils.ShouldInstallSkill(packageInfo))
            return (null, null);

        var sourceSkillMd = Path.Combine(sourcePath, "SKILL.md");
        if (!File.Exists(sourceSkillMd))
            return (null, null);

        var rawSkillName = Path.GetFileName(sourcePath);
        var (isValid, _) = SkillNameUtils.ValidateSkillName(rawSkillName);
        var skillName = isValid ? rawSkillName : SkillNameUtils.NormalizeSkillName(rawSkillName);

        // Primary: .github/skills/
        var githubSkillDir = Path.Combine(targetBase, ".github", "skills", skillName);
        Directory.CreateDirectory(Path.GetDirectoryName(githubSkillDir)!);

        if (Directory.Exists(githubSkillDir))
            Directory.Delete(githubSkillDir, recursive: true);

        CopyDirectory(sourcePath, githubSkillDir);

        // Secondary: .claude/skills/ (T7)
        string? claudeSkillDir = null;
        var claudeDir = Path.Combine(targetBase, ".claude");
        if (Directory.Exists(claudeDir))
        {
            claudeSkillDir = Path.Combine(claudeDir, "skills", skillName);
            Directory.CreateDirectory(Path.GetDirectoryName(claudeSkillDir)!);

            if (Directory.Exists(claudeSkillDir))
                Directory.Delete(claudeSkillDir, recursive: true);

            CopyDirectory(sourcePath, claudeSkillDir);
        }

        return (githubSkillDir, claudeSkillDir);
    }

    /// <summary>Sync .github/skills/ and .claude/skills/ with currently installed packages.</summary>
    public Dictionary<string, int> SyncIntegration(ApmPackage apmPackage, string projectRoot)
    {
        var stats = new Dictionary<string, int> { ["files_removed"] = 0, ["errors"] = 0 };

        // Build set of expected skill directory names
        var installedSkillNames = new HashSet<string>();
        foreach (var dep in apmPackage.GetApmDependencies())
        {
            var rawName = dep.RepoUrl.Split('/')[^1];
            if (dep.IsVirtual && !string.IsNullOrEmpty(dep.VirtualPath))
                rawName = dep.VirtualPath.Split('/')[^1];

            var (isValid, _) = SkillNameUtils.ValidateSkillName(rawName);
            var skillName = isValid ? rawName : SkillNameUtils.NormalizeSkillName(rawName);
            installedSkillNames.Add(skillName);
        }

        // Clean .github/skills/
        var githubSkillsDir = Path.Combine(projectRoot, ".github", "skills");
        if (Directory.Exists(githubSkillsDir))
        {
            var result = CleanOrphanedSkills(githubSkillsDir, installedSkillNames);
            stats["files_removed"] += result["files_removed"];
            stats["errors"] += result["errors"];
        }

        // Clean .claude/skills/ (T7)
        var claudeSkillsDir = Path.Combine(projectRoot, ".claude", "skills");
        if (Directory.Exists(claudeSkillsDir))
        {
            var result = CleanOrphanedSkills(claudeSkillsDir, installedSkillNames);
            stats["files_removed"] += result["files_removed"];
            stats["errors"] += result["errors"];
        }

        return stats;
    }

    /// <summary>Clean orphaned skills from a skills directory.</summary>
    internal Dictionary<string, int> CleanOrphanedSkills(string skillsDir, HashSet<string> installedSkillNames)
    {
        var filesRemoved = 0;
        var errors = 0;

        foreach (var subDir in Directory.EnumerateDirectories(skillsDir))
        {
            var dirName = Path.GetFileName(subDir);
            if (!installedSkillNames.Contains(dirName))
            {
                try
                {
                    Directory.Delete(subDir, recursive: true);
                    filesRemoved++;
                }
                catch
                {
                    errors++;
                }
            }
        }

        return new Dictionary<string, int> { ["files_removed"] = filesRemoved, ["errors"] = errors };
    }

    /// <summary>Update .gitignore with pattern for generated Claude skills.</summary>
    public bool UpdateGitignoreForSkills(string projectRoot)
    {
        var gitignorePath = Path.Combine(projectRoot, ".gitignore");
        string[] patterns = [".github/skills/*-apm/", "# APM-generated skills"];

        var currentContent = new List<string>();
        if (File.Exists(gitignorePath))
        {
            try
            {
                currentContent = File.ReadAllLines(gitignorePath).ToList();
            }
            catch
            {
                return false;
            }
        }

        var patternsToAdd = patterns
            .Where(p => !currentContent.Any(line => line.Contains(p)))
            .ToList();

        if (patternsToAdd.Count == 0)
            return false;

        try
        {
            using var writer = File.AppendText(gitignorePath);
            if (currentContent.Count > 0 && !string.IsNullOrWhiteSpace(currentContent[^1]))
                writer.WriteLine();
            writer.WriteLine();
            writer.WriteLine("# APM generated Claude Skills");
            foreach (var pattern in patternsToAdd)
                writer.WriteLine(pattern);
            return true;
        }
        catch
        {
            return false;
        }
    }

    /// <summary>Recursively copy a directory.</summary>
    private static void CopyDirectory(string source, string destination)
    {
        Directory.CreateDirectory(destination);

        foreach (var file in Directory.EnumerateFiles(source))
        {
            File.Copy(file, Path.Combine(destination, Path.GetFileName(file)), overwrite: true);
        }

        foreach (var dir in Directory.EnumerateDirectories(source))
        {
            CopyDirectory(dir, Path.Combine(destination, Path.GetFileName(dir)));
        }
    }
}
