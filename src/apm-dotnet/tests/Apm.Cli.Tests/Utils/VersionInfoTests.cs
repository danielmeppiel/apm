using Apm.Cli.Utils;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Utils;

public class VersionInfoTests
{
    [Fact]
    public void GetVersion_ReturnsNonEmptyString()
    {
        var version = VersionInfo.GetVersion();
        version.Should().NotBeNullOrEmpty();
    }

    [Fact]
    public void GetVersion_DoesNotContainPlusHash()
    {
        var version = VersionInfo.GetVersion();
        version.Should().NotContain("+");
    }
}
