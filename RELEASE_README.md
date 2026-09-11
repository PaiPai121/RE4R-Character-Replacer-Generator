# RE4R Character Replacer Generator 0.4.4-preview

## 0.4.4 修复

- 修复 Blender 5.2 中姿势预览辅助材质可能因节点被本地化、重命名或缺失而报 `NoneType` 的问题；现在按稳定的节点类型识别，必要时自动重建并连接节点。
- 基础色贴图现在会顺着 Principled BSDF 的 Base Color 连线追踪，并递归识别节点组中的贴图。
- 支持在 `C / CSAR / MRA / N` 等多贴图材质中优先选择 `_C`、`Albedo`、`Diffuse` 基础色，排除法线、粗糙度、金属度与遮罩贴图。候选项仍有歧义时会列出候选项并停止，不会猜测错贴图。
- 已移动的外部贴图会在原模型和姿势工作区附近按文件名恢复；只有唯一匹配时才会自动修复路径。
- 以 Blender 5.2 LTS 完成了节点重建、四贴图节点组、完整 RE Mesh 导出、贴图转换、磁盘回灌和 19 组姿态审计回归。

## 0.4.3 修复

- 修复补丁 PAK 中某一批资源为 `0/100` 时可能被误判为索引读取失败的问题。
- 扫描模式现在把空结果视为成功，并通过标准输出直接返回 JSON，不再依赖临时空报告文件。
- 真实的 PAK 读取错误、超时和无效扫描数据仍会明确中止，避免掩盖损坏或不兼容问题。

## 0.4.2 修复

- 修复首次生成角色参考配置时，PAK 解包器因缺少 `libzstd.dll` 而失败的问题。
- 发布构建现在会强制检查原生 ZSTD 依赖，缺失时停止打包。
- 最终发布包会在隔离目录中使用真实 ZSTD 压缩的 RE4R 资源完成提取验证。

这是一个在本机把**自备的、已绑定骨骼的人物模型**转换为《Resident Evil 4 (2023)》人物替换 Mod 的实验性工具。它不是某个角色皮肤 Mod，发布包内也不包含人物模型、游戏文件或预先生成的 Mod。

## 使用前准备

- Windows 10/11 x64
- Steam 版《Resident Evil 4 (2023)》的合法本地安装
- Blender 4.2 或更新版本（当前开发验证使用 Blender 5.2 LTS；RE Mesh Editor 上游特别提示 Blender 5.1 存在性能问题）
- 自备 PMX、PMD、FBX 或 BLEND 格式的绑定人物模型，并确认你有权使用和发布该模型及贴图
- Fluffy Mod Manager（用于安装工具生成的 Mod ZIP）

## 快速开始

1. 完整解压 ZIP，不要直接在压缩包内运行。
2. 双击 `RE4RCharacterReplacer.exe`。
   - 启动器会自动查找 Blender 和游戏；没有找到或路径不对时，点“浏览…”手动选择。
   - 路径保存在同目录的 `replacer-paths.json`，下次自动使用，也可随时在启动器里修改。
3. 点“启动生成器”。程序从 8765 开始自动寻找可用端口，被其他软件占用时会顺延到下一个空闲端口，再打开正确的页面。
   - 浏览器打开后，启动器会自动缩到系统托盘并继续提供本地服务。关闭启动器窗口也只会缩到托盘；需要彻底停止时，请右键托盘图标选择“退出并停止服务”。
4. 首次使用先扫描游戏目录；程序只读取 PAK 索引并把所需角色参考文件提取到本机 `work` 目录。
5. 点击“选择模型”会打开 Windows 原生文件窗口，并只显示支持的 PMX、PMD、FBX 与 BLEND 文件。选择后会记住该目录；网页目录浏览和手动路径仍作为备用方式。
6. 选择目标人物与自备模型，生成并检查姿态预览；需要时可在 Blender 中调整后保存。
7. 点击生成，验证通过后下载 Mod ZIP，再用 Fluffy Mod Manager 安装。

`Start-Replacer.cmd`、`Start-Replacer.ps1` 和 `Configure-Paths.cmd` 仅作为故障排查与兼容备用入口。高级用户也可以在启动前用环境变量临时覆盖保存的设置：

```powershell
$env:REPLACER_BLENDER = 'C:\path\to\blender.exe'
$env:RE4_GAME_DIR = 'D:\SteamLibrary\steamapps\common\RESIDENT EVIL 4  BIOHAZARD RE4'
.\Start-Replacer.ps1
```

服务仅监听 `127.0.0.1`。运行期间启动器驻留在系统托盘；从托盘菜单选择“退出并停止服务”才会关闭服务。
如果默认端口已被占用，工具会自动选择后续空闲端口；每个端口均采用独占绑定，避免浏览器误连到其他本地服务。目录浏览已禁用。

## Preview 限制

- Leon 与 Ashley 通过了完整应用路径和合成姿态回归；Ada、Luis、Wesker、Merchant 仍属于实验支持。
- 自动验证不能证明所有剧情动画、表情、布料、物理链和服装槽在游戏内都正确。
- 生成结果会标记为未经游戏内验证；发布前请自行逐项试玩。
- 不保证任意骨架、拓扑或复杂着色器都能转换。失败时工具会停止且不输出 ZIP。

## 内容与权利

本工具不隶属于或受 Capcom 认可。《Resident Evil》及相关资产属于其各自权利人。工具不会随包再分发 Capcom 游戏资产；首次扫描产生的缓存只供用户在自己的电脑上转换使用，请勿重新上传缓存。

你对导入模型、贴图以及生成 Mod 的发布权负责。署名不能替代原作者许可。若来源模型禁止再分发，不要把生成结果上传到 Nexus Mods。

第三方组件与许可证见 `THIRD_PARTY_NOTICES.md` 和 `COPYING`。

---

## English quick start

This is an experimental local generator, not a character skin mod. It contains no character models, extracted game assets, or prebuilt mods. Install Blender 4.2 or newer (currently tested with 5.2 LTS), extract the archive, run `RE4RCharacterReplacer.exe`, select Blender and your legally installed Steam copy of RE4 (2023), then start the generator. The launcher automatically chooses a free local port. Select a rigged model you are allowed to use, review the pose, and generate a Fluffy Mod Manager ZIP. Leon and Ashley have full application-path regression coverage; other targets remain experimental. Always test generated files in game before publishing.
