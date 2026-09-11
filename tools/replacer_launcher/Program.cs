using System.Diagnostics;
using System.Drawing;
using System.Text;
using System.Text.Json;

namespace RE4RCharacterReplacer;

internal static class Program
{
    [STAThread]
    private static int Main(string[] args)
    {
        if (args.Contains("--self-test", StringComparer.OrdinalIgnoreCase))
            return LauncherSelfTest.RunAsync().GetAwaiter().GetResult();
        ApplicationConfiguration.Initialize();
        if (args.Contains("--pick-model", StringComparer.OrdinalIgnoreCase))
            return NativeModelPicker.Run(args);
        if (args.Contains("--lifecycle-self-test", StringComparer.OrdinalIgnoreCase))
        {
            using var lifecycleForm = new LauncherForm(lifecycleTest: true);
            Application.Run(lifecycleForm);
            return lifecycleForm.LifecycleTestPassed ? 0 : 1;
        }
        if (args.Contains("--ui-smoke-test", StringComparer.OrdinalIgnoreCase))
        {
            using var smokeForm = new LauncherForm();
            _ = smokeForm.Handle;
            return 0;
        }
        Application.Run(new LauncherForm());
        return 0;
    }
}

internal sealed class LauncherForm : Form
{
    private const int PreferredPort = 8765;
    private readonly string root = AppContext.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar);
    private readonly TextBox blenderPath = new();
    private readonly TextBox gamePath = new();
    private readonly Button startButton = new();
    private readonly Button stopButton = new();
    private readonly Button openButton = new();
    private readonly Button languageButton = new();
    private readonly Label subtitleLabel = new();
    private readonly Label blenderLabel = new();
    private readonly Label blenderHintLabel = new();
    private readonly Label gameLabel = new();
    private readonly Label gameHintLabel = new();
    private readonly Button blenderBrowseButton = new();
    private readonly Button gameBrowseButton = new();
    private readonly Label statusLabel = new();
    private readonly TextBox logBox = new();
    private readonly NotifyIcon trayIcon = new();
    private readonly System.Windows.Forms.Timer pickerTimer = new() { Interval = 150 };
    private Process? serverProcess;
    private Uri? serverUri;
    private bool closing;
    private bool allowExit;
    private bool pickerBusy;
    private readonly bool lifecycleTest;
    private string language;
    private ToolStripMenuItem? openMenuItem;
    private ToolStripMenuItem? showMenuItem;
    private ToolStripMenuItem? exitMenuItem;

    internal bool LifecycleTestPassed { get; private set; }

    private string ConfigPath => Path.Combine(root, "replacer-paths.json");
    private string StatePath => Path.Combine(root, "replacer-server.json");
    private string PickerDirectory => Path.Combine(root, "replacer_app", "data", "native-picker");
    private string BuildDirectory {
        get {
            var localData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            return Path.Combine(string.IsNullOrWhiteSpace(localData) ? Path.GetTempPath() : localData, "RE4R-Replacer", "jobs");
        }
    }

    public LauncherForm(bool lifecycleTest = false)
    {
        this.lifecycleTest = lifecycleTest;
        language = LauncherLanguage.Detect(root);
        Text = "RE4R Character Replacer";
        Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
        StartPosition = FormStartPosition.CenterScreen;
        MinimumSize = new Size(760, 570);
        Size = new Size(860, 650);
        BackColor = Color.FromArgb(19, 20, 22);
        ForeColor = Color.FromArgb(235, 235, 235);
        Font = new Font("Segoe UI", 10F);
        BuildInterface();
        ConfigureTray();
        ApplyLanguage();
        ConfigurePickerBroker();
        LoadPaths();
        FormClosing += LauncherFormClosing;
        if (lifecycleTest)
        {
            Opacity = 0;
            ShowInTaskbar = false;
            Shown += RunLifecycleSelfTest;
        }
    }

    private void ConfigurePickerBroker()
    {
        Directory.CreateDirectory(PickerDirectory);
        foreach (var pattern in new[] { "*.request.json", "*.result.json", "*.ack" })
            foreach (var path in Directory.EnumerateFiles(PickerDirectory, pattern))
                try { File.Delete(path); } catch (IOException) { }
        pickerTimer.Tick += ProcessPickerRequests;
        pickerTimer.Start();
    }

    private void ProcessPickerRequests(object? sender, EventArgs e)
    {
        if (pickerBusy) return;
        string? requestPath;
        try { requestPath = Directory.EnumerateFiles(PickerDirectory, "*.request.json").OrderBy(File.GetCreationTimeUtc).FirstOrDefault(); }
        catch (IOException) { return; }
        if (requestPath is null) return;

        pickerBusy = true;
        var requestName = Path.GetFileName(requestPath);
        var requestId = requestName[..^".request.json".Length];
        var resultPath = Path.Combine(PickerDirectory, requestId + ".result.json");
        var acknowledgementPath = Path.Combine(PickerDirectory, requestId + ".ack");
        var wasVisible = Visible;
        var previousTopMost = TopMost;
        try
        {
            File.WriteAllText(acknowledgementPath, "ready", new UTF8Encoding(false));
            if (!lifecycleTest && !wasVisible) ShowLauncher();
            TopMost = true;
            Activate();
            BringToFront();
            NativeModelPicker.HandleBrokerRequest(requestPath, resultPath, this);
        }
        catch (Exception ex)
        {
            AppendLog(L("模型文件窗口失败：", "Model file window failed: ") + ex.Message);
            try { File.WriteAllText(resultPath, JsonSerializer.Serialize(new { ok = false, error = ex.Message }), new UTF8Encoding(false)); } catch { }
        }
        finally
        {
            try { File.Delete(requestPath); } catch (IOException) { }
            TopMost = previousTopMost;
            if (!lifecycleTest && !wasVisible && serverProcess is { HasExited: false }) HideToTray(showNotice: false);
            pickerBusy = false;
        }
    }

    private void BuildInterface()
    {
        var page = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(26), ColumnCount = 1, RowCount = 8 };
        for (var index = 0; index < 7; index++) page.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        page.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        var titleRow = new TableLayoutPanel { Dock = DockStyle.Fill, AutoSize = true, ColumnCount = 2 };
        titleRow.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        titleRow.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
        titleRow.Controls.Add(new Label {
            AutoSize = true, Text = "RE4R CHARACTER REPLACER", Font = new Font("Segoe UI Semibold", 20F),
            ForeColor = Color.FromArgb(220, 47, 47), Margin = new Padding(0, 0, 0, 3),
        }, 0, 0);
        languageButton.AutoSize = true;
        languageButton.MinimumSize = new Size(70, 32);
        languageButton.FlatStyle = FlatStyle.Flat;
        languageButton.FlatAppearance.BorderColor = Color.FromArgb(85, 87, 91);
        languageButton.BackColor = Color.FromArgb(34, 36, 39);
        languageButton.ForeColor = ForeColor;
        languageButton.Click += (_, _) => ToggleLanguage();
        titleRow.Controls.Add(languageButton, 1, 0);
        page.Controls.Add(titleRow);
        subtitleLabel.AutoSize = true;
        subtitleLabel.ForeColor = Color.FromArgb(174, 177, 181);
        subtitleLabel.Margin = new Padding(1, 0, 0, 20);
        page.Controls.Add(subtitleLabel);
        page.Controls.Add(CreatePathRow(blenderLabel, blenderPath, blenderBrowseButton, BrowseBlender));
        page.Controls.Add(CreateHint(blenderHintLabel));
        page.Controls.Add(CreatePathRow(gameLabel, gamePath, gameBrowseButton, BrowseGame));
        page.Controls.Add(CreateHint(gameHintLabel));

        var actions = new FlowLayoutPanel { AutoSize = true, Dock = DockStyle.Fill, FlowDirection = FlowDirection.LeftToRight, Margin = new Padding(0, 18, 0, 12) };
        ConfigureButton(startButton, "", Color.FromArgb(184, 37, 37));
        ConfigureButton(stopButton, "", Color.FromArgb(62, 64, 68));
        ConfigureButton(openButton, "", Color.FromArgb(62, 64, 68));
        stopButton.Enabled = false;
        openButton.Enabled = false;
        startButton.Click += async (_, _) => await StartServerAsync();
        stopButton.Click += (_, _) => StopServer();
        openButton.Click += (_, _) => OpenInterface();
        actions.Controls.AddRange([startButton, stopButton, openButton]);
        page.Controls.Add(actions);

        var lower = new TableLayoutPanel { Dock = DockStyle.Fill, RowCount = 2, ColumnCount = 1 };
        lower.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        lower.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        statusLabel.Text = "";
        statusLabel.AutoSize = true;
        statusLabel.ForeColor = Color.FromArgb(188, 191, 195);
        statusLabel.Margin = new Padding(0, 0, 0, 8);
        logBox.Dock = DockStyle.Fill;
        logBox.Multiline = true;
        logBox.ReadOnly = true;
        logBox.ScrollBars = ScrollBars.Vertical;
        logBox.BackColor = Color.FromArgb(12, 13, 14);
        logBox.ForeColor = Color.FromArgb(205, 208, 211);
        logBox.BorderStyle = BorderStyle.FixedSingle;
        lower.Controls.Add(statusLabel);
        lower.Controls.Add(logBox);
        page.Controls.Add(lower);
        Controls.Add(page);
    }

    private Control CreatePathRow(Label label, TextBox box, Button button, EventHandler browse)
    {
        var row = new TableLayoutPanel { Dock = DockStyle.Fill, AutoSize = true, ColumnCount = 3, Margin = new Padding(0, 4, 0, 0) };
        row.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 135));
        row.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        row.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 92));
        label.AutoSize = true;
        label.Anchor = AnchorStyles.Left;
        label.ForeColor = ForeColor;
        box.Dock = DockStyle.Fill;
        box.BackColor = Color.FromArgb(34, 36, 39);
        box.ForeColor = ForeColor;
        box.BorderStyle = BorderStyle.FixedSingle;
        button.Dock = DockStyle.Fill;
        button.FlatStyle = FlatStyle.Flat;
        button.BackColor = Color.FromArgb(54, 56, 60);
        button.ForeColor = ForeColor;
        button.FlatAppearance.BorderColor = Color.FromArgb(85, 87, 91);
        button.Click += browse;
        row.Controls.Add(label, 0, 0);
        row.Controls.Add(box, 1, 0);
        row.Controls.Add(button, 2, 0);
        return row;
    }

    private static Label CreateHint(Label label)
    {
        label.AutoSize = true;
        label.ForeColor = Color.FromArgb(135, 139, 144);
        label.Margin = new Padding(136, 3, 0, 10);
        return label;
    }

    private static void ConfigureButton(Button button, string text, Color color)
    {
        button.Text = text;
        button.AutoSize = true;
        button.MinimumSize = new Size(122, 38);
        button.FlatStyle = FlatStyle.Flat;
        button.FlatAppearance.BorderSize = 0;
        button.BackColor = color;
        button.ForeColor = Color.White;
        button.Margin = new Padding(0, 0, 10, 0);
    }

    private string L(string chinese, string english) => LauncherLanguage.IsChinese(language) ? chinese : english;

    private void ApplyLanguage()
    {
        subtitleLabel.Text = L("人物替换 Mod 生成工具 · 本地运行，不包含角色模型或游戏文件",
            "Character replacement Mod generator · Runs locally · Includes no character models or game files");
        blenderLabel.Text = "Blender";
        blenderHintLabel.Text = L("请选择 blender.exe。程序会自动查找常见安装位置，也可以随时手动修改。",
            "Select blender.exe. Common locations are detected automatically, and you can change the path at any time.");
        gameLabel.Text = L("RE4 游戏目录", "RE4 game folder");
        gameHintLabel.Text = L("请选择包含 re_chunk_000.pak 的《Resident Evil 4 (2023)》目录。",
            "Select the Resident Evil 4 (2023) folder that contains re_chunk_000.pak.");
        blenderBrowseButton.Text = L("浏览…", "Browse…");
        gameBrowseButton.Text = L("浏览…", "Browse…");
        startButton.Text = L("启动生成器", "Start generator");
        stopButton.Text = L("停止", "Stop");
        openButton.Text = L("打开界面", "Open interface");
        languageButton.Text = LauncherLanguage.IsChinese(language) ? "English" : "中文";
        languageButton.AccessibleName = L("切换为英文", "Switch to Chinese");
        openMenuItem!.Text = L("打开生成器界面", "Open generator interface");
        showMenuItem!.Text = L("显示启动器", "Show launcher");
        exitMenuItem!.Text = L("退出并停止服务", "Exit and stop service");
        if (serverProcess is { HasExited: false } && serverUri is not null)
            SetStatus(L($"运行中 · {serverUri}", $"Running · {serverUri}"), Color.FromArgb(91, 194, 125));
        else if (serverProcess is null)
            SetStatus(L("尚未启动", "Not started"), Color.FromArgb(188, 191, 195));
    }

    private void ToggleLanguage()
    {
        language = LauncherLanguage.IsChinese(language) ? "en" : "zh-CN";
        LauncherLanguage.UpdateConfig(root, config => config["language"] = language);
        ApplyLanguage();
        AppendLog(L("语言已切换为中文。", "Language switched to English."));
    }

    private void BrowseBlender(object? sender, EventArgs e)
    {
        using var dialog = new OpenFileDialog { Filter = "Blender (blender.exe)|blender.exe|Executable files (*.exe)|*.exe", CheckFileExists = true };
        if (File.Exists(blenderPath.Text)) dialog.InitialDirectory = Path.GetDirectoryName(blenderPath.Text);
        if (dialog.ShowDialog(this) == DialogResult.OK) blenderPath.Text = dialog.FileName;
    }

    private void BrowseGame(object? sender, EventArgs e)
    {
        using var dialog = new FolderBrowserDialog {
            Description = L("选择包含 re_chunk_000.pak 的 RE4 (2023) 游戏目录", "Select the RE4 (2023) game folder containing re_chunk_000.pak"),
            UseDescriptionForTitle = true,
        };
        if (Directory.Exists(gamePath.Text)) dialog.SelectedPath = gamePath.Text;
        if (dialog.ShowDialog(this) == DialogResult.OK) gamePath.Text = dialog.SelectedPath;
    }

    private void LoadPaths()
    {
        try
        {
            if (File.Exists(ConfigPath))
            {
                using var document = JsonDocument.Parse(File.ReadAllText(ConfigPath));
                if (document.RootElement.TryGetProperty("blender", out var blender)) blenderPath.Text = blender.GetString() ?? "";
                if (document.RootElement.TryGetProperty("game", out var game)) gamePath.Text = game.GetString() ?? "";
            }
        }
        catch (Exception ex) { AppendLog(L("已有路径配置无法读取：", "Could not read the saved path configuration: ") + ex.Message); }
        if (!IsBlender(blenderPath.Text)) blenderPath.Text = FindBlender() ?? blenderPath.Text;
        if (!IsGame(gamePath.Text)) gamePath.Text = FindGame() ?? gamePath.Text;
    }

    private static bool IsBlender(string path) => File.Exists(path) && string.Equals(Path.GetFileName(path), "blender.exe", StringComparison.OrdinalIgnoreCase);
    private static bool IsGame(string path) => Directory.Exists(path) && File.Exists(Path.Combine(path, "re_chunk_000.pak"));
    private static IEnumerable<string> FixedDriveRoots() => DriveInfo.GetDrives().Where(drive => drive.DriveType == DriveType.Fixed).Select(drive => drive.RootDirectory.FullName);

    private static string? FindBlender()
    {
        var candidates = new List<string>();
        var configured = Environment.GetEnvironmentVariable("REPLACER_BLENDER");
        if (!string.IsNullOrWhiteSpace(configured)) candidates.Add(configured);
        var blenderFoundation = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "Blender Foundation");
        if (Directory.Exists(blenderFoundation))
            candidates.AddRange(Directory.GetDirectories(blenderFoundation, "Blender *").OrderDescending().Select(path => Path.Combine(path, "blender.exe")));
        foreach (var drive in FixedDriveRoots())
        {
            candidates.Add(Path.Combine(drive, "SteamLibrary", "steamapps", "common", "Blender", "blender.exe"));
            candidates.Add(Path.Combine(drive, "Program Files (x86)", "Steam", "steamapps", "common", "Blender", "blender.exe"));
        }
        return candidates.FirstOrDefault(IsBlender);
    }

    private static string? FindGame()
    {
        var candidates = new List<string>();
        var configured = Environment.GetEnvironmentVariable("RE4_GAME_DIR");
        if (!string.IsNullOrWhiteSpace(configured)) candidates.Add(configured);
        foreach (var drive in FixedDriveRoots())
        {
            candidates.Add(Path.Combine(drive, "SteamLibrary", "steamapps", "common", "RESIDENT EVIL 4  BIOHAZARD RE4"));
            candidates.Add(Path.Combine(drive, "Program Files (x86)", "Steam", "steamapps", "common", "RESIDENT EVIL 4  BIOHAZARD RE4"));
        }
        return candidates.FirstOrDefault(IsGame);
    }

    private async Task StartServerAsync()
    {
        if (serverProcess is { HasExited: false }) { OpenInterface(); return; }
        var blender = blenderPath.Text.Trim().Trim('"');
        var game = gamePath.Text.Trim().Trim('"');
        if (!IsBlender(blender)) { ShowPathError(L("请选择有效的 blender.exe。", "Select a valid blender.exe."), blenderPath); return; }
        if (!string.IsNullOrWhiteSpace(game) && !IsGame(game)) { ShowPathError(L("游戏目录必须包含 re_chunk_000.pak。", "The game folder must contain re_chunk_000.pak."), gamePath); return; }
        if (!File.Exists(Path.Combine(root, "replacer_app", "server.py"))) {
            MessageBox.Show(this, L("发布包不完整：找不到 replacer_app\\server.py。", "The release package is incomplete: replacer_app\\server.py is missing."), Text, MessageBoxButtons.OK, MessageBoxIcon.Error);
            return;
        }

        SavePaths(blender, game);
        TryDeleteState();
        startButton.Enabled = false;
        stopButton.Enabled = false;
        openButton.Enabled = false;
        serverUri = null;
        SetStatus(L("正在检查 Blender 运行环境…", "Checking the Blender environment…"), Color.FromArgb(224, 183, 77));
        AppendLog(L("正在运行依赖检查…", "Running dependency checks…"));
        (int ExitCode, string Output) doctor;
        try { doctor = await RunDoctorAsync(blender, game); }
        catch (Exception ex)
        {
            AppendLog(L("无法启动 Blender 依赖检查：", "Could not start the Blender dependency check: ") + ex.Message);
            SetStatus(L("依赖检查未能启动", "Dependency check could not start"), Color.FromArgb(224, 84, 84));
            startButton.Enabled = true;
            MessageBox.Show(this, L("无法启动 Blender。请确认路径和文件权限。", "Could not start Blender. Check the path and file permissions."), Text, MessageBoxButtons.OK, MessageBoxIcon.Error);
            return;
        }
        if (doctor.ExitCode != 0)
        {
            AppendLog(doctor.Output);
            SetStatus(L("依赖检查失败", "Dependency check failed"), Color.FromArgb(224, 84, 84));
            startButton.Enabled = true;
            var message = doctor.Output.Contains("Blender 5.1", StringComparison.OrdinalIgnoreCase)
                ? L("Blender 5.1 存在已知的网格导入/导出卡顿故障，不能用于此工具。请安装并选择 Blender 5.2 LTS 或 Blender 5.0。",
                    "Blender 5.1 has a known mesh import/export performance problem and cannot be used with this tool. Install and select Blender 5.2 LTS or Blender 5.0.")
                : L("Blender 依赖检查失败。请查看窗口下方日志并确认路径。",
                    "The Blender dependency check failed. Review the log below and confirm the configured paths.");
            MessageBox.Show(this, message, Text, MessageBoxButtons.OK, MessageBoxIcon.Error);
            return;
        }
        AppendLog(doctor.Output);
        AppendLog(L($"默认从 {PreferredPort} 开始寻找可用端口；端口被占用时会自动顺延。",
            $"Searching for a free port starting at {PreferredPort}; occupied ports are skipped automatically."));
        SetStatus(L("正在启动本地服务…", "Starting local service…"), Color.FromArgb(224, 183, 77));

        try
        {
            var info = CreateBlenderInfo(blender, game, Path.Combine(root, "replacer_app", "server.py"));
            serverProcess = new Process { StartInfo = info, EnableRaisingEvents = true };
            serverProcess.OutputDataReceived += (_, e) => { if (e.Data is not null) AppendLog(e.Data); };
            serverProcess.ErrorDataReceived += (_, e) => { if (e.Data is not null) AppendLog(e.Data); };
            serverProcess.Exited += (_, _) => {
                if (!closing && IsHandleCreated) BeginInvoke(ServerExited);
            };
            if (!serverProcess.Start()) throw new InvalidOperationException(L("Blender 进程未能启动。", "The Blender process could not start."));
            serverProcess.BeginOutputReadLine();
            serverProcess.BeginErrorReadLine();
            stopButton.Enabled = true;
            serverUri = await WaitForServerAsync(serverProcess.Id, TimeSpan.FromSeconds(45));
            if (serverUri is null) throw new TimeoutException(L("等待本地服务启动超时。", "Timed out waiting for the local service to start."));
            SetStatus(L($"运行中 · {serverUri}", $"Running · {serverUri}"), Color.FromArgb(91, 194, 125));
            openButton.Enabled = true;
            if (!lifecycleTest)
            {
                OpenInterface();
                HideToTray(showNotice: true);
            }
        }
        catch (Exception ex)
        {
            AppendLog(L("启动失败：", "Startup failed: ") + ex.Message);
            StopServer();
            SetStatus(L("启动失败", "Startup failed"), Color.FromArgb(224, 84, 84));
            MessageBox.Show(this, ex.Message, Text, MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
        finally { startButton.Enabled = true; }
    }

    private async Task<(int ExitCode, string Output)> RunDoctorAsync(string blender, string game)
    {
        var info = CreateBlenderInfo(blender, game, Path.Combine(root, "replacer_app", "doctor.py"));
        using var process = new Process { StartInfo = info };
        process.Start();
        var stdout = process.StandardOutput.ReadToEndAsync();
        var stderr = process.StandardError.ReadToEndAsync();
        await process.WaitForExitAsync();
        return (process.ExitCode, (await stdout) + Environment.NewLine + (await stderr));
    }

    private ProcessStartInfo CreateBlenderInfo(string blender, string game, string script)
    {
        var info = new ProcessStartInfo {
            FileName = blender, WorkingDirectory = root, UseShellExecute = false,
            CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true,
            StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8,
        };
        foreach (var argument in new[] { "--background", "--python-exit-code", "1", "--python", script }) info.ArgumentList.Add(argument);
        info.Environment["REPLACER_BLENDER"] = blender;
        if (!string.IsNullOrWhiteSpace(game)) info.Environment["RE4_GAME_DIR"] = game;
        info.Environment["REPLACER_MMD_TOOLS"] = Path.Combine(root, "vendor", "blender_mmd_tools");
        info.Environment["REPLACER_OPEN_BROWSER"] = "0";
        info.Environment["REPLACER_PORT"] = PreferredPort.ToString();
        info.Environment["REPLACER_SERVER_STATE"] = StatePath;
        info.Environment["REPLACER_NATIVE_PICKER_DIR"] = PickerDirectory;
        info.Environment["REPLACER_BUILD_ROOT"] = BuildDirectory;
        info.Environment["REPLACER_LANGUAGE"] = language;
        return info;
    }

    private async Task<Uri?> WaitForServerAsync(int pid, TimeSpan timeout)
    {
        var until = DateTime.UtcNow + timeout;
        while (DateTime.UtcNow < until)
        {
            if (serverProcess is null || serverProcess.HasExited) return null;
            try
            {
                if (File.Exists(StatePath))
                {
                    using var state = JsonDocument.Parse(File.ReadAllText(StatePath));
                    var element = state.RootElement;
                    if (element.GetProperty("pid").GetInt32() == pid && Uri.TryCreate(element.GetProperty("url").GetString(), UriKind.Absolute, out var uri)) return uri;
                }
            }
            catch (Exception ex) when (ex is IOException or JsonException or InvalidOperationException or KeyNotFoundException) { }
            await Task.Delay(150);
        }
        return null;
    }

    private void SavePaths(string blender, string game)
    {
        LauncherLanguage.UpdateConfig(root, config => {
            config["blender"] = Path.GetFullPath(blender);
            config["language"] = language;
            if (string.IsNullOrWhiteSpace(game)) config.Remove("game"); else config["game"] = Path.GetFullPath(game);
        });
        AppendLog(L("路径配置已保存到程序目录，可随时在上方修改。", "Path settings were saved. You can change them above at any time."));
    }

    private void OpenInterface()
    {
        if (serverUri is not null)
        {
            language = LauncherLanguage.Detect(root);
            ApplyLanguage();
            var separator = serverUri.AbsoluteUri.Contains('?') ? '&' : '?';
            var url = serverUri.AbsoluteUri + separator + "lang=" + Uri.EscapeDataString(language);
            Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
        }
    }

    private void ConfigureTray()
    {
        var menu = new ContextMenuStrip();
        openMenuItem = new ToolStripMenuItem("", null, (_, _) => OpenInterface());
        showMenuItem = new ToolStripMenuItem("", null, (_, _) => ShowLauncher());
        exitMenuItem = new ToolStripMenuItem("", null, (_, _) => { allowExit = true; Close(); });
        menu.Items.Add(openMenuItem);
        menu.Items.Add(showMenuItem);
        menu.Items.Add(new ToolStripSeparator());
        menu.Items.Add(exitMenuItem);
        trayIcon.Icon = Icon;
        trayIcon.Text = "RE4R Character Replacer";
        trayIcon.ContextMenuStrip = menu;
        trayIcon.Visible = false;
        trayIcon.DoubleClick += (_, _) => ShowLauncher();
    }

    private void LauncherFormClosing(object? sender, FormClosingEventArgs e)
    {
        if (!allowExit && serverProcess is { HasExited: false })
        {
            e.Cancel = true;
            HideToTray(showNotice: !lifecycleTest);
            return;
        }
        closing = true;
        StopServer();
        trayIcon.Visible = false;
    }

    private void HideToTray(bool showNotice)
    {
        trayIcon.Visible = true;
        ShowInTaskbar = false;
        Hide();
        if (showNotice)
            trayIcon.ShowBalloonTip(3500, "RE4R Character Replacer",
                L("生成器仍在后台运行。双击托盘图标可重新打开，右键可退出。",
                    "The generator is still running in the background. Double-click the tray icon to reopen it, or right-click to exit."), ToolTipIcon.Info);
    }

    private void ShowLauncher()
    {
        ShowInTaskbar = true;
        Show();
        WindowState = FormWindowState.Normal;
        Activate();
        BringToFront();
    }

    private async void RunLifecycleSelfTest(object? sender, EventArgs e)
    {
        var reportPath = Environment.GetEnvironmentVariable("REPLACER_LIFECYCLE_TEST_REPORT");
        try
        {
            await StartServerAsync();
            var started = serverProcess is { HasExited: false } && serverUri is not null;
            var pickerPassed = false;
            var pickerFixture = Path.Combine(PickerDirectory, "lifecycle-picker-test.fbx");
            if (started)
            {
                File.WriteAllBytes(pickerFixture, []);
                Environment.SetEnvironmentVariable("REPLACER_PICK_MODEL_TEST_PATH", pickerFixture);
                using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(15) };
                using var response = await client.PostAsync(new Uri(serverUri!, "/api/pick-model"), new StringContent("{}", Encoding.UTF8, "application/json"));
                using var pickerResponse = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
                pickerPassed = response.IsSuccessStatusCode
                    && pickerResponse.RootElement.TryGetProperty("path", out var selectedPath)
                    && string.Equals(Path.GetFullPath(selectedPath.GetString() ?? ""), Path.GetFullPath(pickerFixture), StringComparison.OrdinalIgnoreCase);
                Close();
                await Task.Delay(300);
                LifecycleTestPassed = pickerPassed && serverProcess is { HasExited: false } && !Visible && trayIcon.Visible;
            }
            if (!string.IsNullOrWhiteSpace(reportPath))
            {
                var report = JsonSerializer.Serialize(new {
                    passed = LifecycleTestPassed,
                    serverStarted = started,
                    nativePickerBrokerPassed = pickerPassed,
                    serviceAliveAfterWindowClose = serverProcess is { HasExited: false },
                    launcherHidden = !Visible,
                    trayVisible = trayIcon.Visible,
                }, new JsonSerializerOptions { WriteIndented = true });
                File.WriteAllText(reportPath, report, new UTF8Encoding(false));
            }
        }
        finally
        {
            Environment.SetEnvironmentVariable("REPLACER_PICK_MODEL_TEST_PATH", null);
            try { File.Delete(Path.Combine(PickerDirectory, "lifecycle-picker-test.fbx")); } catch (IOException) { }
            allowExit = true;
            Close();
        }
    }

    private void StopServer()
    {
        try { if (serverProcess is { HasExited: false }) serverProcess.Kill(entireProcessTree: true); }
        catch (Exception ex) { if (!closing) AppendLog(L("停止服务时发生错误：", "An error occurred while stopping the service: ") + ex.Message); }
        serverProcess?.Dispose();
        serverProcess = null;
        serverUri = null;
        TryDeleteState();
        if (!closing)
        {
            startButton.Enabled = true;
            stopButton.Enabled = false;
            openButton.Enabled = false;
            SetStatus(L("已停止", "Stopped"), Color.FromArgb(188, 191, 195));
        }
    }

    private void ServerExited()
    {
        if (closing || serverProcess is null) return;
        AppendLog(L($"本地服务已退出（代码 {serverProcess.ExitCode}）。", $"The local service exited with code {serverProcess.ExitCode}."));
        serverProcess.Dispose();
        serverProcess = null;
        serverUri = null;
        startButton.Enabled = true;
        stopButton.Enabled = false;
        openButton.Enabled = false;
        SetStatus(L("服务已退出", "Service exited"), Color.FromArgb(224, 84, 84));
        trayIcon.ShowBalloonTip(5000, "RE4R Character Replacer",
            L("本地服务已经退出，请打开启动器查看日志并重新启动。",
                "The local service exited. Open the launcher, review the log, and start it again."), ToolTipIcon.Error);
        ShowLauncher();
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing)
        {
            pickerTimer.Stop();
            pickerTimer.Dispose();
            trayIcon.Visible = false;
            trayIcon.ContextMenuStrip?.Dispose();
            trayIcon.Dispose();
        }
        base.Dispose(disposing);
    }

    private void TryDeleteState() { try { File.Delete(StatePath); } catch (IOException) { } }
    private void ShowPathError(string message, Control target) { MessageBox.Show(this, message, Text, MessageBoxButtons.OK, MessageBoxIcon.Warning); target.Focus(); }
    private void SetStatus(string text, Color color) { statusLabel.Text = text; statusLabel.ForeColor = color; }

    private void AppendLog(string text)
    {
        if (InvokeRequired) { BeginInvoke(() => AppendLog(text)); return; }
        if (!string.IsNullOrWhiteSpace(text)) logBox.AppendText($"[{DateTime.Now:HH:mm:ss}] {text.Trim()}{Environment.NewLine}");
    }
}
