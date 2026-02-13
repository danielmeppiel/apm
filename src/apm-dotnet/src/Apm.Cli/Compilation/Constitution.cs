namespace Apm.Cli.Compilation;

/// <summary>Utilities for reading constitution file.</summary>
public static class Constitution
{
    /// <summary>Return path to constitution.md if present, else a path that does not exist.</summary>
    public static string FindConstitution(string baseDir)
        => Path.Combine(baseDir, CompilationConstants.ConstitutionRelativePath);

    /// <summary>Read full constitution content if file exists.</summary>
    public static string? ReadConstitution(string baseDir)
    {
        var path = FindConstitution(baseDir);
        if (!File.Exists(path))
            return null;

        try
        {
            return File.ReadAllText(path);
        }
        catch (IOException)
        {
            return null;
        }
    }
}
