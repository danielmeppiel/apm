using Apm.Cli.Primitives;

namespace Apm.Cli.Compilation;

/// <summary>
/// Builds template sections for AGENTS.md compilation.
/// Stub interface — full implementation in a future wave.
/// </summary>
public interface ITemplateBuilder
{
    /// <summary>Build conditional sections grouped by applyTo patterns.</summary>
    string BuildConditionalSections(List<Instruction> instructions);

    /// <summary>Generate the full AGENTS.md template from data.</summary>
    string GenerateAgentsMdTemplate(TemplateData data);

    /// <summary>Find a chatmode by name in the collection.</summary>
    Chatmode? FindChatmodeByName(List<Chatmode> chatmodes, string name);
}
