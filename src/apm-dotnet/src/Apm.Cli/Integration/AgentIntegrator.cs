using Apm.Cli.Models;

namespace Apm.Cli.Integration;

/// <summary>Result of agent integration operation.</summary>
public record AgentIntegrationResult(
    int FilesIntegrated,
    int FilesUpdated,
    int FilesSkipped,
    List<string> TargetPaths,
    bool GitignoreUpdated,
    int LinksResolved = 0);

/// <summary>
/// Handles integration of APM package agents into .github/agents/.
/// Skills are NOT transformed to agents — they are handled by SkillIntegrator.
/// </summary>
public class AgentIntegrator
{
    /// <summary>Check if agent integration should be performed.</summary>
    public bool ShouldIntegrate(string projectRoot) => true;

    /// <summary>Find all .agent.md and .chatmode.md files in a package.</summary>
    public List<string> FindAgentFiles(string packagePath)
    {
        var agentFiles = new List<string>();

        if (Directory.Exists(packagePath))
        {
            agentFiles.AddRange(Directory.EnumerateFiles(packagePath, "*.agent.md", SearchOption.TopDirectoryOnly));
            agentFiles.AddRange(Directory.EnumerateFiles(packagePath, "*.chatmode.md", SearchOption.TopDirectoryOnly));
        }

        var apmAgents = Path.Combine(packagePath, ".apm", "agents");
        if (Directory.Exists(apmAgents))
        {
            agentFiles.AddRange(Directory.EnumerateFiles(apmAgents, "*.agent.md", SearchOption.TopDirectoryOnly));
        }

        var apmChatmodes = Path.Combine(packagePath, ".apm", "chatmodes");
        if (Directory.Exists(apmChatmodes))
        {
            agentFiles.AddRange(Directory.EnumerateFiles(apmChatmodes, "*.chatmode.md", SearchOption.TopDirectoryOnly));
        }

        return agentFiles;
    }

    /// <summary>Generate target filename with -apm suffix (intent-first naming).</summary>
    public string GetTargetFilename(string sourceFile, string packageName)
    {
        var fileName = Path.GetFileName(sourceFile);

        if (fileName.EndsWith(".agent.md", StringComparison.OrdinalIgnoreCase))
        {
            var stem = fileName[..^".agent.md".Length];
            return $"{stem}-apm.agent.md";
        }

        if (fileName.EndsWith(".chatmode.md", StringComparison.OrdinalIgnoreCase))
        {
            var stem = fileName[..^".chatmode.md".Length];
            return $"{stem}-apm.chatmode.md";
        }

        // Fallback
        var fallbackStem = Path.GetFileNameWithoutExtension(fileName);
        var extension = Path.GetExtension(fileName);
        return $"{fallbackStem}-apm{extension}";
    }

    /// <summary>Copy agent file verbatim. Returns number of links resolved (always 0 for now).</summary>
    public int CopyAgent(string source, string target)
    {
        var content = File.ReadAllText(source);
        Directory.CreateDirectory(Path.GetDirectoryName(target)!);
        File.WriteAllText(target, content);
        return 0;
    }

    /// <summary>Integrate all agents from a package into .github/agents/.</summary>
    public AgentIntegrationResult IntegratePackageAgents(PackageInfo packageInfo, string projectRoot)
    {
        var agentFiles = FindAgentFiles(packageInfo.InstallPath);

        if (agentFiles.Count == 0)
        {
            return new AgentIntegrationResult(0, 0, 0, [], false);
        }

        var agentsDir = Path.Combine(projectRoot, ".github", "agents");
        Directory.CreateDirectory(agentsDir);

        var filesIntegrated = 0;
        var targetPaths = new List<string>();
        var totalLinksResolved = 0;

        foreach (var sourceFile in agentFiles)
        {
            var targetFilename = GetTargetFilename(sourceFile, packageInfo.Package.Name);
            var targetPath = Path.Combine(agentsDir, targetFilename);

            var linksResolved = CopyAgent(sourceFile, targetPath);
            totalLinksResolved += linksResolved;
            filesIntegrated++;
            targetPaths.Add(targetPath);
        }

        return new AgentIntegrationResult(filesIntegrated, 0, 0, targetPaths, false, totalLinksResolved);
    }

    /// <summary>Remove all APM-managed agent files for clean regeneration.</summary>
    public Dictionary<string, int> SyncIntegration(ApmPackage apmPackage, string projectRoot)
    {
        var stats = new Dictionary<string, int> { ["files_removed"] = 0, ["errors"] = 0 };

        var agentsDir = Path.Combine(projectRoot, ".github", "agents");
        if (!Directory.Exists(agentsDir))
            return stats;

        foreach (var pattern in new[] { "*-apm.agent.md", "*-apm.chatmode.md" })
        {
            foreach (var file in Directory.EnumerateFiles(agentsDir, pattern))
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
        }

        return stats;
    }

    /// <summary>Update .gitignore with pattern for integrated agents.</summary>
    public bool UpdateGitignoreForIntegratedAgents(string projectRoot)
    {
        var gitignorePath = Path.Combine(projectRoot, ".gitignore");
        string[] patterns =
        [
            ".github/agents/*-apm.agent.md",
            ".github/agents/*-apm.chatmode.md"
        ];

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
            writer.WriteLine("# APM integrated agents");
            foreach (var pattern in patternsToAdd)
                writer.WriteLine(pattern);
            return true;
        }
        catch
        {
            return false;
        }
    }
}
