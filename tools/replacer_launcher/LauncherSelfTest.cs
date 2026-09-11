using System.Diagnostics;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;

namespace RE4RCharacterReplacer;

internal static class LauncherSelfTest
{
    internal static async Task<int> RunAsync()
    {
        var root = AppContext.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar);
        var reportPath = Environment.GetEnvironmentVariable("REPLACER_SELF_TEST_REPORT")
            ?? Path.Combine(root, "self-test-report.json");
        var report = new Dictionary<string, object?> { ["root"] = root, ["passed"] = false };
        TcpListener? blocker = null;
        Process? server = null;
        string? testModel = null;
        var statePath = Path.Combine(root, "self-test-server.json");
        try
        {
            var blender = Environment.GetEnvironmentVariable("REPLACER_BLENDER");
            if (string.IsNullOrWhiteSpace(blender) || !File.Exists(blender))
                throw new InvalidOperationException("REPLACER_BLENDER must point to blender.exe for --self-test.");
            var required = new[] {
                Path.Combine(root, "replacer_app", "server.py"),
                Path.Combine(root, "replacer_app", "web", "index.html"),
                Path.Combine(root, "vendor", "blender_mmd_tools", "mmd_tools", "__init__.py"),
                Path.Combine(root, "tools", "replacer_pak", "ReplacerPak.exe"),
            };
            var missing = required.Where(path => !File.Exists(path)).ToArray();
            if (missing.Length > 0) throw new FileNotFoundException("Package files missing: " + string.Join(", ", missing));

            var basePort = 18765;
            for (; basePort < 18865; basePort++)
            {
                try
                {
                    blocker = new TcpListener(IPAddress.Loopback, basePort);
                    blocker.Server.ExclusiveAddressUse = true;
                    blocker.Start();
                    break;
                }
                catch (SocketException) { blocker?.Stop(); blocker = null; }
            }
            if (blocker is null) throw new InvalidOperationException("Could not reserve a collision-test port.");

            File.Delete(statePath);
            // Keep the fixture under the package root. On some Windows setups TEMP uses
            // an 8.3 alias (HUNTER~1) while Python resolves the same file to its long
            // path, making a correct native-picker round trip look unequal.
            var testDirectory = Path.Combine(root, "work", "launcher-self-test");
            Directory.CreateDirectory(testDirectory);
            testModel = Path.Combine(testDirectory, $"re4r-picker-{Guid.NewGuid():N}.fbx");
            File.WriteAllText(testModel, "RE4R native picker integration test", new UTF8Encoding(false));
            var info = CreateBlenderInfo(blender, root, Path.Combine(root, "replacer_app", "server.py"));
            info.Environment["REPLACER_PORT"] = basePort.ToString();
            info.Environment["REPLACER_SERVER_STATE"] = statePath;
            info.Environment["REPLACER_PICK_MODEL_TEST_PATH"] = testModel;
            server = Process.Start(info) ?? throw new InvalidOperationException("Could not start Blender server process.");
            var state = await WaitForStateAsync(statePath, server.Id, TimeSpan.FromSeconds(45));
            var selectedPort = state.GetProperty("port").GetInt32();
            var url = state.GetProperty("url").GetString() ?? throw new InvalidDataException("Server URL missing.");
            report["basePortBlocked"] = basePort;
            report["selectedPort"] = selectedPort;
            report["adaptivePort"] = selectedPort == basePort + 1;

            using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(10) };
            var rootResponse = await client.GetAsync(url);
            var html = await rootResponse.Content.ReadAsStringAsync();
            var healthResponse = await client.GetAsync(url + "api/health");
            var browseResponse = await client.GetAsync(url + "api/model-directory");
            using var browseDocument = JsonDocument.Parse(await browseResponse.Content.ReadAsStringAsync());
            var browsePath = browseDocument.RootElement.TryGetProperty("path", out var pathElement) ? pathElement.GetString() : null;
            using var pickContent = new StringContent("{}", Encoding.UTF8, "application/json");
            var pickResponse = await client.PostAsync(url + "api/pick-model", pickContent);
            using var pickDocument = JsonDocument.Parse(await pickResponse.Content.ReadAsStringAsync());
            var pickedPath = pickDocument.RootElement.TryGetProperty("path", out var pickedElement) ? pickedElement.GetString() : null;
            var missingResponse = await client.GetAsync(url + "missing/");
            report["rootStatus"] = (int)rootResponse.StatusCode;
            report["correctPage"] = rootResponse.IsSuccessStatusCode && html.Contains("<title>RE4 · 人物替换</title>") && !html.Contains("Directory listing for");
            report["healthStatus"] = (int)healthResponse.StatusCode;
            report["modelBrowserStatus"] = (int)browseResponse.StatusCode;
            report["modelBrowserPath"] = browsePath;
            report["modelBrowserPathExists"] = browsePath is not null && Directory.Exists(browsePath);
            report["nativePickerStatus"] = (int)pickResponse.StatusCode;
            report["nativePickerRoundTrip"] = pickResponse.IsSuccessStatusCode && string.Equals(pickedPath, testModel, StringComparison.OrdinalIgnoreCase);
            report["missingStatus"] = (int)missingResponse.StatusCode;
            report["passed"] = selectedPort == basePort + 1 && rootResponse.IsSuccessStatusCode
                && (bool)report["correctPage"]! && healthResponse.IsSuccessStatusCode
                && browseResponse.IsSuccessStatusCode && browsePath is not null && Directory.Exists(browsePath)
                && pickResponse.IsSuccessStatusCode && string.Equals(pickedPath, testModel, StringComparison.OrdinalIgnoreCase)
                && missingResponse.StatusCode == HttpStatusCode.NotFound;
        }
        catch (Exception ex)
        {
            report["error"] = ex.ToString();
        }
        finally
        {
            try { if (server is { HasExited: false }) server.Kill(entireProcessTree: true); } catch { }
            server?.Dispose();
            blocker?.Stop();
            try { File.Delete(statePath); } catch { }
            try { if (testModel is not null) File.Delete(testModel); } catch { }
            Directory.CreateDirectory(Path.GetDirectoryName(reportPath)!);
            File.WriteAllText(reportPath, JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true }), new UTF8Encoding(false));
        }
        return report.TryGetValue("passed", out var passed) && passed is true ? 0 : 1;
    }

    private static ProcessStartInfo CreateBlenderInfo(string blender, string root, string script)
    {
        var info = new ProcessStartInfo {
            FileName = blender, WorkingDirectory = root, UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardOutput = true, RedirectStandardError = true,
        };
        foreach (var argument in new[] { "--background", "--python-exit-code", "1", "--python", script }) info.ArgumentList.Add(argument);
        info.Environment["REPLACER_BLENDER"] = blender;
        info.Environment["REPLACER_MMD_TOOLS"] = Path.Combine(root, "vendor", "blender_mmd_tools");
        info.Environment["REPLACER_OPEN_BROWSER"] = "0";
        info.Environment.Remove("REPLACER_MODEL_DIR");
        return info;
    }

    private static async Task<JsonElement> WaitForStateAsync(string statePath, int pid, TimeSpan timeout)
    {
        var until = DateTime.UtcNow + timeout;
        while (DateTime.UtcNow < until)
        {
            try
            {
                if (File.Exists(statePath))
                {
                    using var document = JsonDocument.Parse(File.ReadAllText(statePath));
                    if (document.RootElement.GetProperty("pid").GetInt32() == pid) return document.RootElement.Clone();
                }
            }
            catch (Exception ex) when (ex is IOException or JsonException or InvalidOperationException) { }
            await Task.Delay(150);
        }
        throw new TimeoutException("Timed out waiting for server state.");
    }
}
