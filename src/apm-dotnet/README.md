# APM CLI — .NET Port

A .NET 10 NativeAOT implementation of the APM CLI — the dependency manager for AI agents.

## Install

### .NET Global Tool

```bash
dotnet tool install -g apm-cli
```

### PowerShell (cross-platform, pwsh 7+)

```powershell
irm https://raw.githubusercontent.com/danielmeppiel/apm/main/src/apm-dotnet/install.ps1 | iex
```

### dnx

```bash
dnx run apm-cli
```

### Build from Source

```bash
git clone https://github.com/danielmeppiel/apm.git
cd apm/src/apm-dotnet
dotnet build
dotnet test
dotnet run --project src/Apm.Cli
```

## Build & Pack

```bash
dotnet build          # Debug build
dotnet test           # Run tests
dotnet pack           # Create NuGet package
```

### NativeAOT Publish

```bash
dotnet publish src/Apm.Cli -c Release -r linux-x64 /p:NativeAot=true
```

Supported RIDs: `win-x64`, `linux-x64`, `linux-arm64`, `osx-x64`, `osx-arm64`.
