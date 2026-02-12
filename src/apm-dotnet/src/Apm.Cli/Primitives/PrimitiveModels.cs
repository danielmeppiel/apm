namespace Apm.Cli.Primitives;

/// <summary>Represents a chatmode primitive.</summary>
public class Chatmode
{
    public string Name { get; set; } = "";
    public string FilePath { get; set; } = "";
    public string Description { get; set; } = "";
    /// <summary>Glob pattern for file targeting (optional for chatmodes).</summary>
    public string? ApplyTo { get; set; }
    public string Content { get; set; } = "";
    public string? Author { get; set; }
    public string? Version { get; set; }
    /// <summary>Source of primitive: "local" or "dependency:{package_name}".</summary>
    public string? Source { get; set; }

    public List<string> Validate()
    {
        var errors = new List<string>();
        if (string.IsNullOrEmpty(Description))
            errors.Add("Missing 'description' in frontmatter");
        if (string.IsNullOrWhiteSpace(Content))
            errors.Add("Empty content");
        return errors;
    }
}

/// <summary>Represents an instruction primitive.</summary>
public class Instruction
{
    public string Name { get; set; } = "";
    public string FilePath { get; set; } = "";
    public string Description { get; set; } = "";
    /// <summary>Glob pattern for file targeting (required for instructions).</summary>
    public string ApplyTo { get; set; } = "";
    public string Content { get; set; } = "";
    public string? Author { get; set; }
    public string? Version { get; set; }
    /// <summary>Source of primitive: "local" or "dependency:{package_name}".</summary>
    public string? Source { get; set; }

    public List<string> Validate()
    {
        var errors = new List<string>();
        if (string.IsNullOrEmpty(Description))
            errors.Add("Missing 'description' in frontmatter");
        if (string.IsNullOrEmpty(ApplyTo))
            errors.Add("Missing 'applyTo' in frontmatter (required for instructions)");
        if (string.IsNullOrWhiteSpace(Content))
            errors.Add("Empty content");
        return errors;
    }
}

/// <summary>Represents a context primitive.</summary>
public class Context
{
    public string Name { get; set; } = "";
    public string FilePath { get; set; } = "";
    public string Content { get; set; } = "";
    public string? Description { get; set; }
    public string? Author { get; set; }
    public string? Version { get; set; }
    /// <summary>Source of primitive: "local" or "dependency:{package_name}".</summary>
    public string? Source { get; set; }

    public List<string> Validate()
    {
        var errors = new List<string>();
        if (string.IsNullOrWhiteSpace(Content))
            errors.Add("Empty content");
        return errors;
    }
}

/// <summary>
/// Represents a SKILL.md primitive (package meta-guide).
/// SKILL.md is an optional file at the package root that describes how to use the package.
/// For Claude: SKILL.md is used natively for contextual activation.
/// For VSCode: SKILL.md is transformed to .agent.md for dropdown selection.
/// </summary>
public class Skill
{
    public string Name { get; set; } = "";
    public string FilePath { get; set; } = "";
    public string Description { get; set; } = "";
    public string Content { get; set; } = "";
    /// <summary>Source of primitive: "local" or "dependency:{package_name}".</summary>
    public string? Source { get; set; }

    public List<string> Validate()
    {
        var errors = new List<string>();
        if (string.IsNullOrEmpty(Name))
            errors.Add("Missing 'name' in frontmatter");
        if (string.IsNullOrEmpty(Description))
            errors.Add("Missing 'description' in frontmatter");
        if (string.IsNullOrWhiteSpace(Content))
            errors.Add("Empty content");
        return errors;
    }
}

/// <summary>Represents a conflict between primitives from different sources.</summary>
public class PrimitiveConflict
{
    public string PrimitiveName { get; set; } = "";
    /// <summary>'chatmode', 'instruction', 'context', or 'skill'.</summary>
    public string PrimitiveType { get; set; } = "";
    /// <summary>Source that won the conflict.</summary>
    public string WinningSource { get; set; } = "";
    /// <summary>Sources that lost the conflict.</summary>
    public List<string> LosingSources { get; set; } = [];
    public string FilePath { get; set; } = "";

    public override string ToString()
    {
        var losingList = string.Join(", ", LosingSources);
        return $"{PrimitiveType} '{PrimitiveName}': {WinningSource} overrides {losingList}";
    }
}

/// <summary>Collection of discovered primitives with conflict detection.</summary>
public class PrimitiveCollection
{
    public List<Chatmode> Chatmodes { get; } = [];
    public List<Instruction> Instructions { get; } = [];
    public List<Context> Contexts { get; } = [];
    public List<Skill> Skills { get; } = [];
    public List<PrimitiveConflict> Conflicts { get; } = [];

    /// <summary>
    /// Add a primitive to the appropriate collection.
    /// If a primitive with the same name already exists, the new primitive
    /// will only be added if it has higher priority (conflicts are tracked).
    /// </summary>
    public void AddPrimitive(object primitive)
    {
        switch (primitive)
        {
            case Chatmode c:
                AddWithConflictDetection(c, Chatmodes, "chatmode", p => p.Name, p => p.Source);
                break;
            case Instruction i:
                AddWithConflictDetection(i, Instructions, "instruction", p => p.Name, p => p.Source);
                break;
            case Context ctx:
                AddWithConflictDetection(ctx, Contexts, "context", p => p.Name, p => p.Source);
                break;
            case Skill s:
                AddWithConflictDetection(s, Skills, "skill", p => p.Name, p => p.Source);
                break;
            default:
                throw new ArgumentException($"Unknown primitive type: {primitive.GetType().Name}");
        }
    }

    /// <summary>Get all primitives as a single list.</summary>
    public List<object> AllPrimitives()
    {
        var all = new List<object>();
        all.AddRange(Chatmodes);
        all.AddRange(Instructions);
        all.AddRange(Contexts);
        all.AddRange(Skills);
        return all;
    }

    /// <summary>Get total count of all primitives.</summary>
    public int Count() => Chatmodes.Count + Instructions.Count + Contexts.Count + Skills.Count;

    /// <summary>Check if any conflicts were detected during discovery.</summary>
    public bool HasConflicts() => Conflicts.Count > 0;

    /// <summary>Get conflicts for a specific primitive type.</summary>
    public List<PrimitiveConflict> GetConflictsByType(string primitiveType)
        => Conflicts.Where(c => c.PrimitiveType == primitiveType).ToList();

    /// <summary>Get all primitives from a specific source.</summary>
    public List<object> GetPrimitivesBySource(string source)
        => AllPrimitives().Where(p => GetSource(p) == source).ToList();

    private void AddWithConflictDetection<T>(
        T newPrimitive,
        List<T> collection,
        string primitiveType,
        Func<T, string> getName,
        Func<T, string?> getSource) where T : class
    {
        var newName = getName(newPrimitive);
        var existingIndex = collection.FindIndex(existing => getName(existing) == newName);

        if (existingIndex < 0)
        {
            collection.Add(newPrimitive);
            return;
        }

        var existing = collection[existingIndex];
        if (ShouldReplacePrimitive(getSource(existing), getSource(newPrimitive)))
        {
            Conflicts.Add(new PrimitiveConflict
            {
                PrimitiveName = newName,
                PrimitiveType = primitiveType,
                WinningSource = getSource(newPrimitive) ?? "unknown",
                LosingSources = [getSource(existing) ?? "unknown"],
                FilePath = GetFilePath(newPrimitive)
            });
            collection[existingIndex] = newPrimitive;
        }
        else
        {
            Conflicts.Add(new PrimitiveConflict
            {
                PrimitiveName = newName,
                PrimitiveType = primitiveType,
                WinningSource = getSource(existing) ?? "unknown",
                LosingSources = [getSource(newPrimitive) ?? "unknown"],
                FilePath = GetFilePath(existing)
            });
        }
    }

    private static bool ShouldReplacePrimitive(string? existingSource, string? newSource)
    {
        existingSource ??= "unknown";
        newSource ??= "unknown";

        // Local always wins
        if (existingSource == "local") return false;
        if (newSource == "local") return true;

        // Both are dependencies - keep first (existing)
        return false;
    }

    private static string GetSource(object primitive) => primitive switch
    {
        Chatmode c => c.Source ?? "unknown",
        Instruction i => i.Source ?? "unknown",
        Context ctx => ctx.Source ?? "unknown",
        Skill s => s.Source ?? "unknown",
        _ => "unknown"
    };

    private static string GetFilePath(object primitive) => primitive switch
    {
        Chatmode c => c.FilePath,
        Instruction i => i.FilePath,
        Context ctx => ctx.FilePath,
        Skill s => s.FilePath,
        _ => ""
    };
}
