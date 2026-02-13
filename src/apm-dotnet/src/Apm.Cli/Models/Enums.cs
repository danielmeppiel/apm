namespace Apm.Cli.Models;

/// <summary>Types of Git references supported.</summary>
public enum GitReferenceType
{
    Branch,
    Tag,
    Commit
}

/// <summary>
/// Types of packages that APM can install.
/// Used internally to classify packages based on their content
/// (presence of apm.yml, SKILL.md, etc.).
/// </summary>
public enum PackageType
{
    /// <summary>Has apm.yml</summary>
    ApmPackage,
    /// <summary>Has SKILL.md, no apm.yml</summary>
    ClaudeSkill,
    /// <summary>Has both apm.yml and SKILL.md</summary>
    Hybrid,
    /// <summary>Neither apm.yml nor SKILL.md</summary>
    Invalid
}

/// <summary>
/// Explicit package content type declared in apm.yml.
/// Controls how the package is processed during install/compile.
/// </summary>
public enum PackageContentType
{
    /// <summary>Compile to AGENTS.md only, no skill created</summary>
    Instructions,
    /// <summary>Install as native skill only, no AGENTS.md compilation</summary>
    Skill,
    /// <summary>Both AGENTS.md instructions AND skill installation (default)</summary>
    Hybrid,
    /// <summary>Commands/prompts only, no instructions or skills</summary>
    Prompts
}

/// <summary>Extension methods for <see cref="PackageContentType"/>.</summary>
public static class PackageContentTypeExtensions
{
    /// <summary>Parse a string value into a PackageContentType enum.</summary>
    /// <exception cref="ArgumentException">If the value is not a valid package content type.</exception>
    public static PackageContentType FromString(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
            throw new ArgumentException("Package type cannot be empty");

        return value.Trim().ToLowerInvariant() switch
        {
            "instructions" => PackageContentType.Instructions,
            "skill" => PackageContentType.Skill,
            "hybrid" => PackageContentType.Hybrid,
            "prompts" => PackageContentType.Prompts,
            _ => throw new ArgumentException(
                $"Invalid package type '{value}'. " +
                $"Valid types are: 'instructions', 'skill', 'hybrid', 'prompts'")
        };
    }

    /// <summary>Convert enum value to its YAML string representation.</summary>
    public static string ToYamlString(this PackageContentType type) => type switch
    {
        PackageContentType.Instructions => "instructions",
        PackageContentType.Skill => "skill",
        PackageContentType.Hybrid => "hybrid",
        PackageContentType.Prompts => "prompts",
        _ => throw new ArgumentOutOfRangeException(nameof(type))
    };
}

/// <summary>Types of validation errors for APM packages.</summary>
public enum ValidationError
{
    MissingApmYml,
    MissingApmDir,
    InvalidYmlFormat,
    MissingRequiredField,
    InvalidVersionFormat,
    InvalidDependencyFormat,
    EmptyApmDir,
    InvalidPrimitiveStructure
}
