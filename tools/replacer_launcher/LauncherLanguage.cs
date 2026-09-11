using System.Globalization;
using System.Text;
using System.Text.Json;

namespace RE4RCharacterReplacer;

internal static class LauncherLanguage
{
    internal static string Detect(string root)
    {
        var environment = Environment.GetEnvironmentVariable("REPLACER_LANGUAGE");
        if (!string.IsNullOrWhiteSpace(environment)) return Normalize(environment);
        var config = ReadConfig(root);
        if (config.TryGetValue("language", out var saved) && !string.IsNullOrWhiteSpace(saved)) return Normalize(saved);
        return Normalize(CultureInfo.CurrentUICulture.Name);
    }

    internal static string Normalize(string? value) =>
        value?.StartsWith("zh", StringComparison.OrdinalIgnoreCase) == true ? "zh-CN" : "en";

    internal static bool IsChinese(string language) => Normalize(language) == "zh-CN";

    internal static Dictionary<string, string> ReadConfig(string root)
    {
        var path = Path.Combine(root, "replacer-paths.json");
        try
        {
            return File.Exists(path)
                ? JsonSerializer.Deserialize<Dictionary<string, string>>(File.ReadAllText(path)) ?? new()
                : new();
        }
        catch (Exception ex) when (ex is IOException or JsonException) { return new(); }
    }

    internal static void UpdateConfig(string root, Action<Dictionary<string, string>> update)
    {
        var config = ReadConfig(root);
        update(config);
        var path = Path.Combine(root, "replacer-paths.json");
        var temporary = path + "." + Environment.ProcessId + ".tmp";
        File.WriteAllText(temporary, JsonSerializer.Serialize(config, new JsonSerializerOptions { WriteIndented = true }), new UTF8Encoding(false));
        File.Move(temporary, path, true);
    }
}
