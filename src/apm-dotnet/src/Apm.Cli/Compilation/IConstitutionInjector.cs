namespace Apm.Cli.Compilation;

/// <summary>
/// Injects constitution content into compiled output.
/// Stub interface — full implementation in a future wave.
/// </summary>
public interface IConstitutionInjector
{
    /// <summary>
    /// Inject constitution into compiled content.
    /// </summary>
    /// <returns>Tuple of (content, status, hash).</returns>
    (string Content, string Status, string Hash) Inject(
        string content,
        bool withConstitution,
        string outputPath);
}
