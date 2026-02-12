namespace Apm.Cli.Compilation;

/// <summary>
/// Resolves and validates markdown links in compiled output.
/// Stub interface — full implementation in a future wave.
/// </summary>
public interface ILinkResolver
{
    /// <summary>Resolve markdown links relative to a base directory.</summary>
    string ResolveMarkdownLinks(string content, string baseDir);

    /// <summary>Validate that link targets exist relative to a base directory.</summary>
    List<string> ValidateLinkTargets(string content, string baseDir);
}
