using Apm.Cli.Utils;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Utils;

public class ConsoleHelpersTests
{
    [Fact]
    public void StatusSymbols_ContainsExpectedKeys()
    {
        ConsoleHelpers.StatusSymbols.Should().ContainKey("success");
        ConsoleHelpers.StatusSymbols.Should().ContainKey("error");
        ConsoleHelpers.StatusSymbols.Should().ContainKey("warning");
        ConsoleHelpers.StatusSymbols.Should().ContainKey("info");
        ConsoleHelpers.StatusSymbols.Should().ContainKey("running");
        ConsoleHelpers.StatusSymbols.Should().ContainKey("check");
    }

    [Fact]
    public void GetSymbol_KnownKey_ReturnsEmoji()
    {
        ConsoleHelpers.GetSymbol("success").Should().Be("✨");
        ConsoleHelpers.GetSymbol("error").Should().Be("❌");
        ConsoleHelpers.GetSymbol("check").Should().Be("✅");
    }

    [Fact]
    public void GetSymbol_UnknownKey_ReturnsEmptyString()
    {
        ConsoleHelpers.GetSymbol("nonexistent").Should().BeEmpty();
    }

    [Fact]
    public void StatusSymbols_IsReadOnly()
    {
        ConsoleHelpers.StatusSymbols.Should().BeAssignableTo<IReadOnlyDictionary<string, string>>();
    }
}
