using Apm.Cli.Models;

namespace Apm.Cli.Dependencies;

/// <summary>Validates APM package structure and content.</summary>
public class PackageValidator
{
    private static readonly string[] PrimitiveTypes = ["instructions", "chatmodes", "contexts", "prompts"];

    private static readonly Dictionary<string, string> SuffixMap = new()
    {
        ["instructions"] = ".instructions",
        ["chatmodes"] = ".chatmode",
        ["contexts"] = ".context",
        ["prompts"] = ".prompt"
    };

    /// <summary>Validate that a directory contains a valid APM package.</summary>
    public ValidationResult ValidatePackage(string packagePath)
        => ValidatePackageStructure(packagePath);

    /// <summary>
    /// Validate APM package directory structure.
    /// Checks for required files (apm.yml) and directories (.apm/ with primitives).
    /// </summary>
    public ValidationResult ValidatePackageStructure(string packagePath)
    {
        var result = new ValidationResult();

        if (!Directory.Exists(packagePath))
        {
            result.AddError($"Package directory does not exist: {packagePath}");
            return result;
        }

        // Check for apm.yml
        var apmYml = Path.Combine(packagePath, "apm.yml");
        if (!File.Exists(apmYml))
        {
            result.AddError("Missing required file: apm.yml");
            return result;
        }

        // Try to parse apm.yml
        try
        {
            var package = ApmPackage.FromApmYml(apmYml);
            result.Package = package;
        }
        catch (Exception e) when (e is ArgumentException or FileNotFoundException)
        {
            result.AddError($"Invalid apm.yml: {e.Message}");
            return result;
        }

        // Check for .apm directory
        var apmDir = Path.Combine(packagePath, ".apm");
        if (!Directory.Exists(apmDir))
        {
            result.AddError("Missing required directory: .apm/");
            return result;
        }

        // Check for primitive content
        var hasPrimitives = false;
        foreach (var primitiveType in PrimitiveTypes)
        {
            var primitiveDir = Path.Combine(apmDir, primitiveType);
            if (!Directory.Exists(primitiveDir)) continue;

            var mdFiles = Directory.GetFiles(primitiveDir, "*.md");
            if (mdFiles.Length > 0)
            {
                hasPrimitives = true;
                foreach (var mdFile in mdFiles)
                    ValidatePrimitiveFile(mdFile, result);
            }
        }

        if (!hasPrimitives)
            result.AddWarning("No primitive files found in .apm/ directory");

        return result;
    }

    /// <summary>Validate the structure of primitives in .apm directory.</summary>
    public List<string> ValidatePrimitiveStructure(string apmDir)
    {
        var issues = new List<string>();

        if (!Directory.Exists(apmDir))
        {
            issues.Add("Missing .apm directory");
            return issues;
        }

        var foundPrimitives = false;
        foreach (var primitiveType in PrimitiveTypes)
        {
            var primitiveDir = Path.Combine(apmDir, primitiveType);
            if (!Directory.Exists(primitiveDir)) continue;

            if (!new DirectoryInfo(primitiveDir).Attributes.HasFlag(FileAttributes.Directory))
            {
                issues.Add($"{primitiveType} should be a directory");
                continue;
            }

            var mdFiles = Directory.GetFiles(primitiveDir, "*.md");
            if (mdFiles.Length > 0)
            {
                foundPrimitives = true;
                foreach (var mdFile in mdFiles)
                {
                    if (!IsValidPrimitiveName(Path.GetFileName(mdFile), primitiveType))
                        issues.Add($"Invalid primitive file name: {Path.GetFileName(mdFile)}");
                }
            }
        }

        if (!foundPrimitives)
            issues.Add("No primitive files found in .apm directory");

        return issues;
    }

    /// <summary>Get a summary of package information for display.</summary>
    public string? GetPackageInfoSummary(string packagePath)
    {
        var validationResult = ValidatePackage(packagePath);
        if (!validationResult.IsValid || validationResult.Package == null)
            return null;

        var package = validationResult.Package;
        var summary = $"{package.Name} v{package.Version}";

        if (!string.IsNullOrEmpty(package.Description))
            summary += $" - {package.Description}";

        var apmDir = Path.Combine(packagePath, ".apm");
        if (Directory.Exists(apmDir))
        {
            var primitiveCount = 0;
            foreach (var primitiveType in PrimitiveTypes)
            {
                var primitiveDir = Path.Combine(apmDir, primitiveType);
                if (Directory.Exists(primitiveDir))
                    primitiveCount += Directory.GetFiles(primitiveDir, "*.md").Length;
            }

            if (primitiveCount > 0)
                summary += $" ({primitiveCount} primitives)";
        }

        return summary;
    }

    private static void ValidatePrimitiveFile(string filePath, ValidationResult result)
    {
        try
        {
            var content = File.ReadAllText(filePath);
            if (string.IsNullOrWhiteSpace(content))
                result.AddWarning($"Empty primitive file: {Path.GetFileName(filePath)}");
        }
        catch (Exception e)
        {
            result.AddWarning($"Could not read primitive file {Path.GetFileName(filePath)}: {e.Message}");
        }
    }

    private static bool IsValidPrimitiveName(string filename, string primitiveType)
    {
        if (!filename.EndsWith(".md"))
            return false;

        if (filename.Contains(' '))
            return false;

        var nameWithoutExt = filename[..^3]; // Remove .md
        if (SuffixMap.TryGetValue(primitiveType, out var expectedSuffix))
        {
            if (!nameWithoutExt.EndsWith(expectedSuffix))
                return false;
        }

        return true;
    }
}
