namespace Apm.Cli.Compilation;

/// <summary>High-level constitution injection workflow used by compile command.</summary>
public class ConstitutionInjector : IConstitutionInjector
{
    private readonly string _baseDir;

    public ConstitutionInjector(string baseDir)
    {
        _baseDir = Path.GetFullPath(baseDir);
    }

    /// <summary>
    /// Return final AGENTS.md content after optional injection.
    /// </summary>
    public (string Content, string Status, string Hash) Inject(
        string compiledContent,
        bool withConstitution,
        string outputPath)
    {
        var existingContent = "";
        if (File.Exists(outputPath))
        {
            try { existingContent = File.ReadAllText(outputPath); }
            catch (IOException) { /* ignore */ }
        }

        var (headerPart, bodyPart) = SplitHeader(compiledContent);

        if (!withConstitution)
        {
            // Preserve existing block if present but enforce ordering
            var existingBlock = ConstitutionBlock.FindExistingBlock(existingContent);
            if (existingBlock is not null)
            {
                var final = headerPart + existingBlock.Raw.TrimEnd() + "\n\n" + bodyPart.TrimStart('\n');
                return (final, "SKIPPED", "");
            }
            return (compiledContent, "SKIPPED", "");
        }

        var constitutionText = Constitution.ReadConstitution(_baseDir);
        if (constitutionText is null)
        {
            var existingBlock = ConstitutionBlock.FindExistingBlock(existingContent);
            if (existingBlock is not null)
            {
                var final = headerPart + existingBlock.Raw.TrimEnd() + "\n\n" + bodyPart.TrimStart('\n');
                return (final, "MISSING", "");
            }
            return (compiledContent, "MISSING", "");
        }

        var newBlock = ConstitutionBlock.RenderBlock(constitutionText);
        var existingBlockFound = ConstitutionBlock.FindExistingBlock(existingContent);

        string status;
        string blockToUse;

        if (existingBlockFound is not null)
        {
            if (existingBlockFound.Raw.TrimEnd() == newBlock.TrimEnd())
            {
                status = "UNCHANGED";
                blockToUse = existingBlockFound.Raw.TrimEnd();
            }
            else
            {
                status = "UPDATED";
                blockToUse = newBlock.TrimEnd();
            }
        }
        else
        {
            status = "CREATED";
            blockToUse = newBlock.TrimEnd();
        }

        // Extract hash value from the new block
        var hashValue = "";
        var lines = newBlock.Split('\n');
        if (lines.Length > 1 && lines[1].StartsWith("hash:"))
        {
            var parts = lines[1].Split(' ', StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length >= 2)
                hashValue = parts[1];
        }

        var finalContent = headerPart + blockToUse + "\n\n" + bodyPart.TrimStart('\n');
        if (!finalContent.EndsWith('\n'))
            finalContent += "\n";

        return (finalContent, status, hashValue);
    }

    private static (string Header, string Body) SplitHeader(string content)
    {
        const string marker = "\n\n";
        var idx = content.IndexOf(marker, StringComparison.Ordinal);
        if (idx >= 0)
            return (content[..(idx + marker.Length)], content[(idx + marker.Length)..]);
        return (content, "");
    }
}
