namespace Apm.Cli.Tests.Adapters;

/// <summary>
/// Collection that prevents parallel execution for tests that modify the current working directory.
/// </summary>
[CollectionDefinition("CwdTests", DisableParallelization = true)]
public class CwdTestsCollection;
