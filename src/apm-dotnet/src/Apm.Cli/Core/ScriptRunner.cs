using System.Diagnostics;
using System.Text.RegularExpressions;
using YamlDotNet.Serialization;
using YamlDotNet.Serialization.NamingConventions;
using Apm.Cli.Dependencies;
using Apm.Cli.Models;
using Apm.Cli.Utils;

namespace Apm.Cli.Core;

/// <summary>
/// Executes APM scripts with auto-compilation of .prompt.md files.
/// </summary>
public sealed class ScriptRunner
{
    private static readonly Regex PromptFilePattern = new(@"\S+\.prompt\.md", RegexOptions.Compiled);

    private readonly string _compiledDir;
    private readonly IPackageDownloader? _packageDownloader;

    public ScriptRunner(string? compiledDir = null, IPackageDownloader? packageDownloader = null)
    {
        _compiledDir = compiledDir ?? Path.Combine(".apm", "compiled");
        _packageDownloader = packageDownloader;
    }

    /// <summary>
    /// Run a script from apm.yml with parameter substitution.
    /// Priority: 1) explicit scripts, 2) auto-discovered prompts, 3) error.
    /// </summary>
    public bool RunScript(string scriptName, Dictionary<string, string> parameters)
    {
        ConsoleHelpers.Info($"🚀 Running script: {scriptName}");

        var isVirtualPackage = IsVirtualPackageReference(scriptName);

        var config = LoadConfig();
        if (config is null)
        {
            if (isVirtualPackage)
            {
                ConsoleHelpers.Info("Creating minimal apm.yml for zero-config execution...");
                CreateMinimalConfig();
                config = LoadConfig();
            }
            else
            {
                throw new InvalidOperationException("No apm.yml found in current directory");
            }
        }

        // 1. Check explicit scripts first
        if (config!.TryGetValue("scripts", out var scriptsObj) &&
            scriptsObj is Dictionary<object, object> scripts &&
            scripts.TryGetValue(scriptName, out var commandObj) &&
            commandObj is string command)
        {
            return ExecuteScriptCommand(command, parameters);
        }

        // 2. Auto-discover prompt file
        var discoveredPrompt = DiscoverPromptFile(scriptName);
        if (discoveredPrompt is not null)
        {
            ConsoleHelpers.Info($"Auto-discovered: {discoveredPrompt}");
            var runtime = DetectInstalledRuntime();
            var generatedCommand = GenerateRuntimeCommand(runtime, discoveredPrompt);
            return ExecuteScriptCommand(generatedCommand, parameters);
        }

        // 2.5 Try auto-install if it looks like a virtual package reference
        if (isVirtualPackage)
        {
            ConsoleHelpers.Info($"📦 Auto-installing virtual package: {scriptName}");
            if (AutoInstallVirtualPackage(scriptName))
            {
                // Extract the prompt filename from the reference for retry discovery
                var retryName = ExtractPromptFileName(scriptName);
                var retryPrompt = DiscoverPromptFile(retryName ?? scriptName);
                if (retryPrompt is not null)
                {
                    ConsoleHelpers.Success("✨ Package installed and ready to run");
                    var runtime = DetectInstalledRuntime();
                    var generatedCommand = GenerateRuntimeCommand(runtime, retryPrompt);
                    return ExecuteScriptCommand(generatedCommand, parameters);
                }

                throw new InvalidOperationException(
                    $"Package installed successfully but prompt not found.\n" +
                    "The package may not contain the expected prompt file.\n" +
                    "Check apm_modules for installed files.");
            }
        }

        // 3. Not found
        var available = "none";
        if (config.TryGetValue("scripts", out var s) && s is Dictionary<object, object> dict)
            available = string.Join(", ", dict.Keys);

        throw new InvalidOperationException(
            $"Script or prompt '{scriptName}' not found.\n" +
            $"Available scripts in apm.yml: {available}\n" +
            "\nTo find available prompts, check:\n" +
            "  - Local: .apm/prompts/, .github/prompts/, or project root\n" +
            "  - Dependencies: apm_modules/**/.apm/prompts/\n" +
            "\nOr install a prompt package:\n" +
            "  apm install <owner>/<repo>/path/to/prompt.prompt.md");
    }

    /// <summary>
    /// List all available scripts from apm.yml.
    /// </summary>
    public Dictionary<string, string> ListScripts()
    {
        var config = LoadConfig();
        if (config is null)
            return new Dictionary<string, string>();

        if (config.TryGetValue("scripts", out var scriptsObj) &&
            scriptsObj is Dictionary<object, object> scripts)
        {
            return scripts.ToDictionary(
                kvp => kvp.Key.ToString()!,
                kvp => kvp.Value?.ToString() ?? "");
        }

        return new Dictionary<string, string>();
    }

    private bool ExecuteScriptCommand(string command, Dictionary<string, string> parameters)
    {
        // Auto-compile any .prompt.md files in the command
        var (compiledCommand, compiledFiles, runtimeContent) = AutoCompilePrompts(command, parameters);

        if (compiledFiles.Count > 0)
            ConsoleHelpers.Info($"Compiled {compiledFiles.Count} prompt file(s)");

        var runtime = DetectRuntime(compiledCommand);

        try
        {
            // Set up token environment
            var env = TokenManager.SetupRuntimeEnvironment();

            var startTime = Stopwatch.GetTimestamp();

            int exitCode;
            if (runtimeContent is not null)
                exitCode = ExecuteRuntimeCommand(compiledCommand, runtimeContent, env);
            else
                exitCode = ExecuteShellCommand(compiledCommand, env);

            var elapsed = Stopwatch.GetElapsedTime(startTime);
            ConsoleHelpers.Success($"✨ Script completed in {elapsed.TotalSeconds:F1}s ({runtime})");

            return exitCode == 0;
        }
        catch (Exception e)
        {
            ConsoleHelpers.Error($"❌ Script execution failed: {e.Message}");
            throw new InvalidOperationException($"Script execution failed: {e.Message}", e);
        }
    }

    private (string CompiledCommand, List<string> CompiledFiles, string? RuntimeContent)
        AutoCompilePrompts(string command, Dictionary<string, string> parameters)
    {
        var promptFiles = PromptFilePattern.Matches(command)
            .Select(m => m.Value).ToList();
        var compiledFiles = new List<string>();
        string? runtimeContent = null;
        var compiledCommand = command;

        foreach (var promptFile in promptFiles)
        {
            var compiledPath = CompilePromptFile(promptFile, parameters);
            compiledFiles.Add(promptFile);

            var compiledContent = File.ReadAllText(compiledPath).Trim();

            var isRuntimeCmd = new[] { "copilot", "codex", "llm" }
                .Any(r => command.Contains(r)) && command.Contains(promptFile);

            compiledCommand = TransformRuntimeCommand(compiledCommand, promptFile, compiledContent, compiledPath);

            if (isRuntimeCmd)
                runtimeContent = compiledContent;
        }

        return (compiledCommand, compiledFiles, runtimeContent);
    }

    internal string TransformRuntimeCommand(string command, string promptFile, string compiledContent, string compiledPath)
    {
        string[] runtimeCommands = ["codex", "copilot", "llm"];

        foreach (var runtimeCmd in runtimeCommands)
        {
            var runtimePattern = $" {runtimeCmd} ";
            if (command.Contains(runtimePattern) && command.Contains(promptFile))
            {
                var parts = command.Split(runtimePattern, 2);
                var potentialEnvPart = parts[0];
                var runtimePart = runtimeCmd + " " + parts[1];

                if (potentialEnvPart.Contains('=') && !potentialEnvPart.StartsWith(runtimeCmd))
                {
                    var escaped = Regex.Escape(promptFile);
                    var match = Regex.Match(runtimePart, $@"{runtimeCmd}\s+(.*?)({escaped})(.*?)$");
                    if (match.Success)
                    {
                        var argsBefore = match.Groups[1].Value.Trim();
                        var argsAfter = match.Groups[3].Value.Trim();

                        string result;
                        if (runtimeCmd == "codex")
                            result = string.IsNullOrEmpty(argsBefore)
                                ? $"{potentialEnvPart} codex exec"
                                : $"{potentialEnvPart} codex exec {argsBefore}";
                        else
                        {
                            result = $"{potentialEnvPart} {runtimeCmd}";
                            if (!string.IsNullOrEmpty(argsBefore))
                            {
                                var cleaned = argsBefore.Replace("-p", "").Trim();
                                if (!string.IsNullOrEmpty(cleaned))
                                    result += $" {cleaned}";
                            }
                        }

                        if (!string.IsNullOrEmpty(argsAfter))
                            result += $" {argsAfter}";
                        return result;
                    }
                }
            }
        }

        // Handle individual runtime patterns without env vars
        var escapedFile = Regex.Escape(promptFile);

        if (Regex.IsMatch(command, $@"codex\s+.*{escapedFile}"))
        {
            var match = Regex.Match(command, $@"codex\s+(.*?)({escapedFile})(.*?)$");
            if (match.Success)
            {
                var before = match.Groups[1].Value.Trim();
                var after = match.Groups[3].Value.Trim();
                var result = "codex exec";
                if (!string.IsNullOrEmpty(before)) result += $" {before}";
                if (!string.IsNullOrEmpty(after)) result += $" {after}";
                return result;
            }
        }
        else if (Regex.IsMatch(command, $@"copilot\s+.*{escapedFile}"))
        {
            var match = Regex.Match(command, $@"copilot\s+(.*?)({escapedFile})(.*?)$");
            if (match.Success)
            {
                var before = match.Groups[1].Value.Trim().Replace("-p", "").Trim();
                var after = match.Groups[3].Value.Trim();
                var result = "copilot";
                if (!string.IsNullOrEmpty(before)) result += $" {before}";
                if (!string.IsNullOrEmpty(after)) result += $" {after}";
                return result;
            }
        }
        else if (Regex.IsMatch(command, $@"llm\s+.*{escapedFile}"))
        {
            var match = Regex.Match(command, $@"llm\s+(.*?)({escapedFile})(.*?)$");
            if (match.Success)
            {
                var before = match.Groups[1].Value.Trim();
                var after = match.Groups[3].Value.Trim();
                var result = "llm";
                if (!string.IsNullOrEmpty(before)) result += $" {before}";
                if (!string.IsNullOrEmpty(after)) result += $" {after}";
                return result;
            }
        }
        else if (command.Trim() == promptFile)
        {
            return "codex exec";
        }

        // Fallback: replace file path with compiled path
        return command.Replace(promptFile, compiledPath);
    }

    internal static string DetectRuntime(string command)
    {
        var lower = command.ToLowerInvariant().Trim();
        if (lower.Contains("copilot")) return "copilot";
        if (lower.Contains("codex")) return "codex";
        if (lower.Contains("llm")) return "llm";
        return "unknown";
    }

    private int ExecuteRuntimeCommand(string command, string content, Dictionary<string, string> env)
    {
        // Parse command into args, extracting env vars
        var parts = command.Trim().Split(' ', StringSplitOptions.RemoveEmptyEntries);
        var envVars = new Dictionary<string, string>(env);
        var actualArgs = new List<string>();

        foreach (var part in parts)
        {
            if (part.Contains('=') && actualArgs.Count == 0 &&
                Regex.IsMatch(part.Split('=')[0], @"^[a-zA-Z_][a-zA-Z0-9_]*$"))
            {
                var eqIdx = part.IndexOf('=');
                envVars[part[..eqIdx]] = part[(eqIdx + 1)..];
            }
            else
            {
                actualArgs.Add(part);
            }
        }

        var runtime = DetectRuntime(string.Join(' ', actualArgs));

        if (runtime == "copilot")
            actualArgs.AddRange(["-p", content]);
        else
            actualArgs.Add(content);

        return RunProcess(actualArgs, envVars);
    }

    private static int ExecuteShellCommand(string command, Dictionary<string, string> env)
    {
        var isWindows = OperatingSystem.IsWindows();
        var fileName = isWindows ? "cmd.exe" : "/bin/sh";
        var args = isWindows ? $"/c {command}" : $"-c \"{command.Replace("\"", "\\\"")}\"";

        var psi = new ProcessStartInfo(fileName, args)
        {
            UseShellExecute = false,
        };

        foreach (var (key, value) in env)
            psi.Environment[key] = value;

        using var process = Process.Start(psi)
            ?? throw new InvalidOperationException("Failed to start process");
        process.WaitForExit();
        return process.ExitCode;
    }

    private static int RunProcess(List<string> args, Dictionary<string, string> env)
    {
        var psi = new ProcessStartInfo(args[0])
        {
            UseShellExecute = false,
        };

        for (var i = 1; i < args.Count; i++)
            psi.ArgumentList.Add(args[i]);

        foreach (var (key, value) in env)
            psi.Environment[key] = value;

        using var process = Process.Start(psi)
            ?? throw new InvalidOperationException("Failed to start process");
        process.WaitForExit();
        return process.ExitCode;
    }

    private string? DiscoverPromptFile(string name)
    {
        var searchName = name.EndsWith(".prompt.md") ? name : $"{name}.prompt.md";

        // 1. Check local paths
        string[] localPaths =
        [
            searchName,
            Path.Combine(".apm", "prompts", searchName),
            Path.Combine(".github", "prompts", searchName),
        ];

        foreach (var path in localPaths)
        {
            if (File.Exists(path))
                return path;
        }

        // 2. Search in dependencies
        var apmModules = "apm_modules";
        if (!Directory.Exists(apmModules))
            return null;

        var matches = Directory.GetFiles(apmModules, searchName, SearchOption.AllDirectories);
        return matches.Length switch
        {
            0 => null,
            1 => matches[0],
            _ => throw new InvalidOperationException(
                $"Multiple prompts found for '{name}':\n" +
                string.Join("\n", matches.Select(m => $"  - {m}")) +
                "\n\nPlease specify using qualified path."),
        };
    }

    private static string DetectInstalledRuntime()
    {
        // Check PATH for available runtimes
        if (FindInPath("copilot") is not null)
            return "copilot";
        if (FindInPath("codex") is not null)
            return "codex";

        throw new InvalidOperationException(
            "No compatible runtime found.\n" +
            "Install GitHub Copilot CLI with:\n" +
            "  apm runtime setup copilot\n" +
            "Or install Codex CLI with:\n" +
            "  apm runtime setup codex");
    }

    private static string? FindInPath(string executable)
    {
        var pathVar = Environment.GetEnvironmentVariable("PATH") ?? "";
        var separator = OperatingSystem.IsWindows() ? ';' : ':';
        var extensions = OperatingSystem.IsWindows()
            ? new[] { ".exe", ".cmd", ".bat", "" }
            : new[] { "" };

        foreach (var dir in pathVar.Split(separator, StringSplitOptions.RemoveEmptyEntries))
        {
            foreach (var ext in extensions)
            {
                var fullPath = Path.Combine(dir, executable + ext);
                if (File.Exists(fullPath))
                    return fullPath;
            }
        }

        return null;
    }

    private static string GenerateRuntimeCommand(string runtime, string promptFile)
    {
        return runtime switch
        {
            "copilot" => $"copilot --log-level all --log-dir copilot-logs --allow-all-tools -p {promptFile}",
            "codex" => $"codex -s workspace-write --skip-git-repo-check {promptFile}",
            _ => throw new ArgumentException($"Unsupported runtime: {runtime}"),
        };
    }

    private string CompilePromptFile(string promptFile, Dictionary<string, string> parameters)
    {
        var promptPath = ResolvePromptFile(promptFile);
        Directory.CreateDirectory(_compiledDir);

        var content = File.ReadAllText(promptPath);

        // Parse frontmatter and extract main content
        string mainContent;
        if (content.StartsWith("---"))
        {
            var parts = content.Split("---", 3);
            mainContent = parts.Length >= 3 ? parts[2].Trim() : content;
        }
        else
        {
            mainContent = content;
        }

        // Substitute parameters
        var compiled = SubstituteParameters(mainContent, parameters);

        var outputName = Path.GetFileNameWithoutExtension(
            Path.GetFileNameWithoutExtension(promptFile)) + ".txt";
        var outputPath = Path.Combine(_compiledDir, outputName);

        File.WriteAllText(outputPath, compiled);
        return outputPath;
    }

    private static string ResolvePromptFile(string promptFile)
    {
        if (File.Exists(promptFile))
            return promptFile;

        string[] commonDirs = [Path.Combine(".github", "prompts"), Path.Combine(".apm", "prompts")];
        foreach (var dir in commonDirs)
        {
            var path = Path.Combine(dir, promptFile);
            if (File.Exists(path))
                return path;
        }

        var apmModules = "apm_modules";
        if (Directory.Exists(apmModules))
        {
            var matches = Directory.GetFiles(apmModules, Path.GetFileName(promptFile), SearchOption.AllDirectories);
            if (matches.Length > 0)
                return matches[0];
        }

        throw new FileNotFoundException(
            $"Prompt file '{promptFile}' not found.\n" +
            "Tip: Run 'apm install' to ensure dependencies are installed.");
    }

    internal static string SubstituteParameters(string content, Dictionary<string, string> parameters)
    {
        var result = content;
        foreach (var (key, value) in parameters)
        {
            var placeholder = $"${{input:{key}}}";
            result = result.Replace(placeholder, value);
        }
        return result;
    }

    /// <summary>
    /// Check if a name looks like a virtual package reference.
    /// Virtual packages have format: owner/repo/path/to/file.prompt.md
    /// </summary>
    internal static bool IsVirtualPackageReference(string name)
    {
        if (!name.Contains('/'))
            return false;

        try
        {
            var depRef = DependencyReference.Parse(name);
            return depRef.IsVirtual;
        }
        catch (InvalidVirtualPackageExtensionException)
        {
            // Invalid extension - only reject if it already has a file extension
            var lastSegment = name.Split('/').Last();
            if (lastSegment.Contains('.'))
                return false;
        }
        catch
        {
            // Other parsing errors - fall through to retry
        }

        // Retry with .prompt.md if no file extension or collection path
        var hasExtension = name.Split('/').Last().Contains('.');
        var isCollectionPath = name.Contains("/collections/");

        if (!hasExtension || isCollectionPath)
        {
            try
            {
                var depRef = DependencyReference.Parse($"{name}.prompt.md");
                return depRef.IsVirtual;
            }
            catch { /* not a virtual package */ }
        }

        return false;
    }

    /// <summary>
    /// Auto-install a virtual package from a remote repository.
    /// </summary>
    internal bool AutoInstallVirtualPackage(string packageRef)
    {
        try
        {
            var downloader = _packageDownloader ?? new GitHubPackageDownloader();

            // Normalize the reference - add .prompt.md if missing
            var normalizedRef = packageRef.EndsWith(".prompt.md")
                ? packageRef
                : $"{packageRef}.prompt.md";

            var depRef = DependencyReference.Parse(normalizedRef);
            if (!depRef.IsVirtual)
                return false;

            // Get the install path
            var targetPath = depRef.GetInstallPath("apm_modules");

            // Check if already installed
            if (Directory.Exists(targetPath))
            {
                ConsoleHelpers.Info($"Package already installed at {targetPath}");
                return true;
            }

            ConsoleHelpers.Info($"📥 Downloading from {depRef.ToGitHubUrl()}");
            var packageInfo = downloader.DownloadPackage(normalizedRef, targetPath);
            ConsoleHelpers.Success($"✅ Installed {packageInfo.Package.Name} v{packageInfo.Package.Version}");

            AddDependencyToConfig(normalizedRef);
            return true;
        }
        catch (Exception e)
        {
            ConsoleHelpers.Error($"❌ Auto-install failed: {e.Message}");
            return false;
        }
    }

    /// <summary>
    /// Add a dependency to the apm.yml dependencies list.
    /// </summary>
    internal static void AddDependencyToConfig(string dependencyString)
    {
        const string configPath = "apm.yml";
        if (!File.Exists(configPath))
            return;

        var yaml = File.ReadAllText(configPath);
        var deserializer = new DeserializerBuilder()
            .WithNamingConvention(UnderscoredNamingConvention.Instance)
            .Build();
        var config = deserializer.Deserialize<Dictionary<object, object>>(yaml)
                     ?? new Dictionary<object, object>();

        // Ensure dependencies.apm section exists
        if (!config.TryGetValue("dependencies", out var depsObj) ||
            depsObj is not Dictionary<object, object> deps)
        {
            deps = new Dictionary<object, object>();
            config["dependencies"] = deps;
        }

        if (!deps.TryGetValue("apm", out var apmListObj) ||
            apmListObj is not List<object> apmList)
        {
            apmList = new List<object>();
            deps["apm"] = apmList;
        }

        // Add if not already present
        if (apmList.Any(item => item?.ToString() == dependencyString))
            return;

        apmList.Add(dependencyString);

        var serializer = new SerializerBuilder()
            .WithNamingConvention(UnderscoredNamingConvention.Instance)
            .Build();
        File.WriteAllText(configPath, serializer.Serialize(config));

        ConsoleHelpers.Info($"Added {dependencyString} to apm.yml dependencies");
    }

    /// <summary>
    /// Extract the prompt filename from a virtual package reference for discovery retry.
    /// </summary>
    internal static string? ExtractPromptFileName(string packageRef)
    {
        var normalizedRef = packageRef.EndsWith(".prompt.md")
            ? packageRef
            : $"{packageRef}.prompt.md";

        try
        {
            var depRef = DependencyReference.Parse(normalizedRef);
            if (depRef.IsVirtual && !string.IsNullOrEmpty(depRef.VirtualPath))
                return depRef.VirtualPath.Split('/').Last();
        }
        catch { /* fall through */ }

        // Fallback: just use last path segment
        var lastSegment = packageRef.Split('/').Last();
        return lastSegment.EndsWith(".prompt.md") ? lastSegment : $"{lastSegment}.prompt.md";
    }

    private static void CreateMinimalConfig()
    {
        var dirName = new DirectoryInfo(Directory.GetCurrentDirectory()).Name;
        var content = $"name: {dirName}\nversion: 1.0.0\ndescription: Auto-generated for zero-config virtual package execution\n";
        File.WriteAllText("apm.yml", content);
    }

    private Dictionary<object, object>? LoadConfig()
    {
        const string configPath = "apm.yml";
        if (!File.Exists(configPath))
            return null;

        var yaml = File.ReadAllText(configPath);
        var deserializer = new DeserializerBuilder()
            .WithNamingConvention(UnderscoredNamingConvention.Instance)
            .Build();

        return deserializer.Deserialize<Dictionary<object, object>>(yaml);
    }
}
