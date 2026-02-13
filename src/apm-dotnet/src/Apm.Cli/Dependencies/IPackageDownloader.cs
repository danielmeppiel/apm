using Apm.Cli.Models;

namespace Apm.Cli.Dependencies;

/// <summary>
/// Abstraction for downloading APM packages.
/// </summary>
public interface IPackageDownloader
{
    /// <summary>Download a package (virtual or full repo) to the target path.</summary>
    PackageInfo DownloadPackage(string repoRef, string targetPath);
}
