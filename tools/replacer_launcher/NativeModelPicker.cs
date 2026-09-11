using System.Text;
using System.Text.Json;

namespace RE4RCharacterReplacer;

internal static class NativeModelPicker
{
    private static readonly HashSet<string> SupportedExtensions = new(StringComparer.OrdinalIgnoreCase) { ".pmx", ".pmd", ".fbx", ".blend" };

    internal static int Run(string[] args)
    {
        var outputPath = Option(args, "--output");
        if (string.IsNullOrWhiteSpace(outputPath)) return 2;
        try
        {
            WriteResult(outputPath, PickModel(Option(args, "--initial"), owner: null));
            return 0;
        }
        catch (Exception ex)
        {
            try { WriteResult(outputPath, new { ok = false, error = ex.Message }); } catch { }
            return 1;
        }
    }

    internal static void HandleBrokerRequest(string requestPath, string resultPath, IWin32Window owner)
    {
        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(requestPath));
            var initial = document.RootElement.TryGetProperty("initial", out var value) ? value.GetString() : null;
            WriteResult(resultPath, PickModel(initial, owner));
        }
        catch (Exception ex)
        {
            WriteResult(resultPath, new Dictionary<string, object?> { ["ok"] = false, ["error"] = ex.Message });
        }
    }

    private static Dictionary<string, object?> PickModel(string? requestedDirectory, IWin32Window? owner)
    {
        var testPath = Environment.GetEnvironmentVariable("REPLACER_PICK_MODEL_TEST_PATH");
        if (!string.IsNullOrWhiteSpace(testPath)) return CompleteSelection(testPath, saveDirectory: false);

        var language = LauncherLanguage.Detect(AppContext.BaseDirectory);
        var chinese = LauncherLanguage.IsChinese(language);

        using var dialog = new OpenFileDialog {
            Title = chinese ? "选择人物模型" : "Select a character model",
            Filter = chinese
                ? "支持的人物模型 (*.pmx;*.pmd;*.fbx;*.blend)|*.pmx;*.pmd;*.fbx;*.blend|MikuMikuDance 模型 (*.pmx;*.pmd)|*.pmx;*.pmd|FBX 模型 (*.fbx)|*.fbx|Blender 文件 (*.blend)|*.blend"
                : "Supported character models (*.pmx;*.pmd;*.fbx;*.blend)|*.pmx;*.pmd;*.fbx;*.blend|MikuMikuDance models (*.pmx;*.pmd)|*.pmx;*.pmd|FBX models (*.fbx)|*.fbx|Blender files (*.blend)|*.blend",
            CheckFileExists = true,
            Multiselect = false,
            RestoreDirectory = true,
            AddExtension = true,
        };
        var initial = ChooseInitialDirectory(requestedDirectory);
        if (initial is not null) dialog.InitialDirectory = initial;
        var dialogResult = owner is null ? dialog.ShowDialog() : dialog.ShowDialog(owner);
        if (dialogResult != DialogResult.OK)
            return new Dictionary<string, object?> { ["ok"] = true, ["cancelled"] = true };
        return CompleteSelection(dialog.FileName);
    }

    private static Dictionary<string, object?> CompleteSelection(string selectedPath, bool saveDirectory = true)
    {
        var fullPath = Path.GetFullPath(selectedPath);
        var chinese = LauncherLanguage.IsChinese(LauncherLanguage.Detect(AppContext.BaseDirectory));
        if (!File.Exists(fullPath)) throw new FileNotFoundException(chinese ? "选择的模型文件不存在。" : "The selected model file does not exist.", fullPath);
        if (!SupportedExtensions.Contains(Path.GetExtension(fullPath)))
            throw new InvalidDataException(chinese ? "请选择 PMX、PMD、FBX 或 BLEND 模型文件。" : "Select a PMX, PMD, FBX, or BLEND model file.");
        var directory = Path.GetDirectoryName(fullPath)!;
        if (saveDirectory)
        {
            try { SaveLastDirectory(directory); }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or JsonException) { }
        }
        return new Dictionary<string, object?> {
            ["ok"] = true, ["cancelled"] = false, ["path"] = fullPath,
            ["name"] = Path.GetFileName(fullPath), ["directory"] = directory,
        };
    }

    private static string? ChooseInitialDirectory(string? requested)
    {
        var candidates = new List<string?> { requested };
        var config = LauncherLanguage.ReadConfig(AppContext.BaseDirectory);
        if (config.TryGetValue("modelDirectory", out var saved)) candidates.Add(saved);
        candidates.Add(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments));
        candidates.Add(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory));
        candidates.Add(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile));
        return candidates.FirstOrDefault(path => !string.IsNullOrWhiteSpace(path) && Directory.Exists(path));
    }

    private static void SaveLastDirectory(string directory)
    {
        LauncherLanguage.UpdateConfig(AppContext.BaseDirectory, config => config["modelDirectory"] = directory);
    }

    private static string? Option(string[] args, string name)
    {
        for (var index = 0; index < args.Length - 1; index++)
            if (string.Equals(args[index], name, StringComparison.OrdinalIgnoreCase)) return args[index + 1];
        return null;
    }

    private static void WriteResult(string path, object result) => WriteJsonAtomic(path, result);

    private static void WriteJsonAtomic(string path, object value)
    {
        var fullPath = Path.GetFullPath(path);
        Directory.CreateDirectory(Path.GetDirectoryName(fullPath)!);
        var temporary = fullPath + "." + Environment.ProcessId + ".tmp";
        File.WriteAllText(temporary, JsonSerializer.Serialize(value), new UTF8Encoding(false));
        File.Move(temporary, fullPath, true);
    }
}
