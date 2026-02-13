using Apm.Cli.Models;
using Apm.Cli.Primitives;

namespace Apm.Cli.Integration;

/// <summary>Result of command integration operation.</summary>
public record CommandIntegrationResult(
    int FilesIntegrated,
    int FilesUpdated,
    int FilesSkipped,
    List<string> TargetPaths,
    bool GitignoreUpdated,
    int LinksResolved = 0);

/// <summary>
/// Handles integration of APM package prompts into .claude/commands/.
/// Transforms .prompt.md files into Claude Code custom slash commands.
/// </summary>
public class CommandIntegrator
{
    /// <summary>Check if command integration should be performed.</summary>
    public bool ShouldIntegrate(string projectRoot) => true;

    /// <summary>Find all .prompt.md files in a package.</summary>
    public List<string> FindPromptFiles(string packagePath)
    {
        var promptFiles = new List<string>();

        if (Directory.Exists(packagePath))
        {
            promptFiles.AddRange(Directory.EnumerateFiles(packagePath, "*.prompt.md", SearchOption.TopDirectoryOnly));
        }

        var apmPrompts = Path.Combine(packagePath, ".apm", "prompts");
        if (Directory.Exists(apmPrompts))
        {
            promptFiles.AddRange(Directory.EnumerateFiles(apmPrompts, "*.prompt.md", SearchOption.TopDirectoryOnly));
        }

        return promptFiles;
    }

    /// <summary>
    /// Transform a .prompt.md file into Claude command format.
    /// Returns (commandName, metadata, body, warnings).
    /// </summary>
    public (string CommandName, Dictionary<string, string> Metadata, string Body, List<string> Warnings)
        TransformPromptToCommand(string source)
    {
        var warnings = new List<string>();
        var content = File.ReadAllText(source);
        var (rawMetadata, body) = PrimitiveParser.ParseFrontmatter(content);

        // Extract command name from filename
        var fileName = Path.GetFileName(source);
        var commandName = fileName.EndsWith(".prompt.md", StringComparison.OrdinalIgnoreCase)
            ? fileName[..^".prompt.md".Length]
            : Path.GetFileNameWithoutExtension(fileName);

        // Map APM frontmatter to Claude frontmatter
        var claudeMetadata = new Dictionary<string, string>();

        if (rawMetadata.TryGetValue("description", out var desc) && desc is not null)
            claudeMetadata["description"] = desc.ToString()!;

        if (rawMetadata.TryGetValue("allowed-tools", out var tools) && tools is not null)
            claudeMetadata["allowed-tools"] = tools.ToString()!;
        else if (rawMetadata.TryGetValue("allowedTools", out var tools2) && tools2 is not null)
            claudeMetadata["allowed-tools"] = tools2.ToString()!;

        if (rawMetadata.TryGetValue("model", out var model) && model is not null)
            claudeMetadata["model"] = model.ToString()!;

        if (rawMetadata.TryGetValue("argument-hint", out var hint) && hint is not null)
            claudeMetadata["argument-hint"] = hint.ToString()!;
        else if (rawMetadata.TryGetValue("argumentHint", out var hint2) && hint2 is not null)
            claudeMetadata["argument-hint"] = hint2.ToString()!;

        return (commandName, claudeMetadata, body, warnings);
    }

    /// <summary>Integrate a prompt file as a Claude command.</summary>
    public int IntegrateCommand(string source, string target, PackageInfo packageInfo, string originalPath)
    {
        var (_, metadata, body, _) = TransformPromptToCommand(source);

        Directory.CreateDirectory(Path.GetDirectoryName(target)!);

        // Write the command file with frontmatter
        using var writer = new StreamWriter(target);
        if (metadata.Count > 0)
        {
            writer.WriteLine("---");
            foreach (var (key, value) in metadata)
                writer.WriteLine($"{key}: {value}");
            writer.WriteLine("---");
            writer.WriteLine();
        }
        writer.Write(body);

        return 0;
    }

    /// <summary>Integrate all prompt files from a package as Claude commands.</summary>
    public CommandIntegrationResult IntegratePackageCommands(PackageInfo packageInfo, string projectRoot)
    {
        var commandsDir = Path.Combine(projectRoot, ".claude", "commands");
        var promptFiles = FindPromptFiles(packageInfo.InstallPath);

        if (promptFiles.Count == 0)
        {
            return new CommandIntegrationResult(0, 0, 0, [], false, 0);
        }

        var filesIntegrated = 0;
        var targetPaths = new List<string>();
        var totalLinksResolved = 0;

        foreach (var promptFile in promptFiles)
        {
            var fileName = Path.GetFileName(promptFile);
            var baseName = fileName.EndsWith(".prompt.md", StringComparison.OrdinalIgnoreCase)
                ? fileName[..^".prompt.md".Length]
                : Path.GetFileNameWithoutExtension(fileName);

            var commandName = $"{baseName}-apm";
            var targetPath = Path.Combine(commandsDir, $"{commandName}.md");

            var linksResolved = IntegrateCommand(promptFile, targetPath, packageInfo, promptFile);
            filesIntegrated++;
            totalLinksResolved += linksResolved;
            targetPaths.Add(targetPath);
        }

        var gitignoreUpdated = UpdateGitignore(projectRoot);

        return new CommandIntegrationResult(filesIntegrated, 0, 0, targetPaths, gitignoreUpdated, totalLinksResolved);
    }

    /// <summary>Remove all APM-managed command files for clean regeneration.</summary>
    public Dictionary<string, int> SyncIntegration(ApmPackage apmPackage, string projectRoot)
    {
        var stats = new Dictionary<string, int> { ["files_removed"] = 0, ["errors"] = 0 };

        var commandsDir = Path.Combine(projectRoot, ".claude", "commands");
        if (!Directory.Exists(commandsDir))
            return stats;

        foreach (var file in Directory.EnumerateFiles(commandsDir, "*-apm.md"))
        {
            try
            {
                File.Delete(file);
                stats["files_removed"]++;
            }
            catch
            {
                stats["errors"]++;
            }
        }

        return stats;
    }

    /// <summary>Remove all APM-managed command files for a specific package.</summary>
    public int RemovePackageCommands(string packageName, string projectRoot)
    {
        var commandsDir = Path.Combine(projectRoot, ".claude", "commands");
        if (!Directory.Exists(commandsDir))
            return 0;

        var filesRemoved = 0;
        foreach (var file in Directory.EnumerateFiles(commandsDir, "*-apm.md"))
        {
            try
            {
                File.Delete(file);
                filesRemoved++;
            }
            catch
            {
                // Skip files that can't be deleted
            }
        }

        return filesRemoved;
    }

    private bool UpdateGitignore(string projectRoot)
    {
        var gitignorePath = Path.Combine(projectRoot, ".gitignore");
        const string pattern = ".claude/commands/*-apm.md";

        var existingContent = File.Exists(gitignorePath) ? File.ReadAllText(gitignorePath) : "";

        if (existingContent.Contains(pattern))
            return false;

        var newContent = existingContent.TrimEnd() + "\n\n# APM-generated Claude commands\n" + pattern + "\n";
        File.WriteAllText(gitignorePath, newContent);
        return true;
    }
}
