using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;

namespace Apm.Cli.Compilation;

/// <summary>Rendering and parsing of injected constitution block in AGENTS.md.</summary>
public static partial class ConstitutionBlock
{
    private const string HashPrefix = "hash:";

    /// <summary>Compute stable truncated SHA256 hash of full constitution content.</summary>
    public static string ComputeConstitutionHash(string content)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(content));
        return Convert.ToHexStringLower(bytes)[..12];
    }

    /// <summary>Render full constitution block with markers and hash line.</summary>
    public static string RenderBlock(string constitutionContent)
    {
        var h = ComputeConstitutionHash(constitutionContent);
        var headerMeta = $"{HashPrefix} {h} path: {CompilationConstants.ConstitutionRelativePath}";
        var body = constitutionContent.TrimEnd() + "\n";

        return
            $"{CompilationConstants.ConstitutionMarkerBegin}\n" +
            $"{headerMeta}\n" +
            body +
            $"{CompilationConstants.ConstitutionMarkerEnd}\n" +
            "\n"; // blank line after block
    }

    /// <summary>Locate existing constitution block and extract its hash if present.</summary>
    public static ExistingBlock? FindExistingBlock(string content)
    {
        var match = BlockRegex().Match(content);
        if (!match.Success)
            return null;

        var blockText = match.Value;
        var hashMatch = HashLineRegex().Match(blockText);
        var hash = hashMatch.Success ? hashMatch.Groups[1].Value : null;

        return new ExistingBlock(blockText, hash, match.Index, match.Index + match.Length);
    }

    /// <summary>Insert or update constitution block in existing AGENTS.md content.</summary>
    /// <returns>Tuple of (updatedText, status) where status is CREATED, UPDATED, or UNCHANGED.</returns>
    public static (string Content, string Status) InjectOrUpdate(
        string existingAgents,
        string newBlock,
        bool placeTop = true)
    {
        var existing = FindExistingBlock(existingAgents);
        if (existing is not null)
        {
            if (existing.Raw == newBlock.TrimEnd())
                return (existingAgents, "UNCHANGED");

            // Replace existing block span with new block
            var updated = existingAgents[..existing.StartIndex] + newBlock.TrimEnd() + existingAgents[existing.EndIndex..];

            // If markers were not at top and we want top placement, move them
            if (placeTop && !updated.StartsWith(newBlock))
            {
                var bodyWithoutBlock = updated.Replace(newBlock.TrimEnd(), "").TrimStart('\n');
                updated = newBlock + bodyWithoutBlock;
            }

            return (updated, "UPDATED");
        }

        // No existing block
        if (placeTop)
            return (newBlock + existingAgents.TrimStart('\n'), "CREATED");

        var separator = existingAgents.EndsWith('\n') ? "" : "\n";
        return (existingAgents + separator + newBlock, "CREATED");
    }

    [GeneratedRegex(@"(<!-- SPEC-KIT CONSTITUTION: BEGIN -->)(.*?)(<!-- SPEC-KIT CONSTITUTION: END -->)", RegexOptions.Singleline)]
    private static partial Regex BlockRegex();

    [GeneratedRegex(@"hash:\s*([0-9a-fA-F]{6,64})")]
    private static partial Regex HashLineRegex();
}

/// <summary>Represents an existing constitution block found in content.</summary>
public sealed record ExistingBlock(string Raw, string? Hash, int StartIndex, int EndIndex);
