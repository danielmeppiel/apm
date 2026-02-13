using System.Text.RegularExpressions;
using Apm.Cli.Models;

namespace Apm.Cli.Integration;

/// <summary>Result of prompt integration operation.</summary>
public record PromptIntegrationResult(
    int FilesIntegrated,
    int FilesUpdated,
    int FilesSkipped,
    List<string> TargetPaths,
    bool GitignoreUpdated,
    int LinksResolved = 0);

/// <summary>Handles integration of APM package prompts into .github/prompts/.</summary>
public class PromptIntegrator
{
    private static readonly Regex LinkPattern = new(@"\]\(([^)]+)\)", RegexOptions.Compiled);

    /// <summary>Check if prompt integration should be performed.</summary>
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

    /// <summary>Copy prompt file verbatim. Returns number of links resolved (always 0 for now).</summary>
    public int CopyPrompt(string source, string target)
    {
        var content = File.ReadAllText(source);
        Directory.CreateDirectory(Path.GetDirectoryName(target)!);
        File.WriteAllText(target, content);
        return 0;
    }

    /// <summary>Generate target filename with -apm suffix (intent-first naming).</summary>
    public string GetTargetFilename(string sourceFile, string packageName)
    {
        var fileName = Path.GetFileName(sourceFile);
        // Remove .prompt.md, then add -apm.prompt.md
        var stem = fileName.EndsWith(".prompt.md", StringComparison.OrdinalIgnoreCase)
            ? fileName[..^".prompt.md".Length]
            : Path.GetFileNameWithoutExtension(fileName);
        return $"{stem}-apm.prompt.md";
    }

    /// <summary>Integrate all prompts from a package into .github/prompts/.</summary>
    public PromptIntegrationResult IntegratePackagePrompts(PackageInfo packageInfo, string projectRoot)
    {
        var promptFiles = FindPromptFiles(packageInfo.InstallPath);

        if (promptFiles.Count == 0)
        {
            return new PromptIntegrationResult(0, 0, 0, [], false);
        }

        var promptsDir = Path.Combine(projectRoot, ".github", "prompts");
        Directory.CreateDirectory(promptsDir);

        var filesIntegrated = 0;
        var targetPaths = new List<string>();
        var totalLinksResolved = 0;

        foreach (var sourceFile in promptFiles)
        {
            var targetFilename = GetTargetFilename(sourceFile, packageInfo.Package.Name);
            var targetPath = Path.Combine(promptsDir, targetFilename);

            var linksResolved = CopyPrompt(sourceFile, targetPath);
            totalLinksResolved += linksResolved;
            filesIntegrated++;
            targetPaths.Add(targetPath);
        }

        return new PromptIntegrationResult(filesIntegrated, 0, 0, targetPaths, false, totalLinksResolved);
    }

    /// <summary>Remove all APM-managed prompt files for clean regeneration.</summary>
    public Dictionary<string, int> SyncIntegration(ApmPackage apmPackage, string projectRoot)
    {
        var stats = new Dictionary<string, int> { ["files_removed"] = 0, ["errors"] = 0 };

        var promptsDir = Path.Combine(projectRoot, ".github", "prompts");
        if (!Directory.Exists(promptsDir))
            return stats;

        foreach (var file in Directory.EnumerateFiles(promptsDir, "*-apm.prompt.md"))
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

    /// <summary>Update .gitignore with pattern for integrated prompts.</summary>
    public bool UpdateGitignoreForIntegratedPrompts(string projectRoot)
    {
        var gitignorePath = Path.Combine(projectRoot, ".gitignore");
        const string pattern = ".github/prompts/*-apm.prompt.md";

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

        if (currentContent.Any(line => line.Contains(pattern)))
            return false;

        try
        {
            using var writer = File.AppendText(gitignorePath);
            if (currentContent.Count > 0 && !string.IsNullOrWhiteSpace(currentContent[^1]))
                writer.WriteLine();
            writer.WriteLine();
            writer.WriteLine("# APM integrated prompts");
            writer.WriteLine(pattern);
            return true;
        }
        catch
        {
            return false;
        }
    }
}
