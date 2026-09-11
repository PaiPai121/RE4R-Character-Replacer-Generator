# Contributing

Bug reports and focused pull requests are welcome.

Before opening a pull request:

1. Keep game assets, downloaded models, project history, logs, and generated packages out of the repository.
2. From `replacer_app`, run `python -m unittest test_adjust_endpoint test_dds_fallback test_fluffy_package test_game_resources test_model_directory test_pipeline test_runtime_paths test_static_server`.
3. Build both projects under `tools/replacer_launcher` and `tools/replacer_pak`.
4. For Blender pipeline changes, test with a factory-startup Blender process and include the Blender version in the report.
5. Explain any new third-party dependency and its license.

When reporting a bug, include the generator version, Blender version, Windows version, the failing stage, and the sanitized error text. Do not attach copyrighted game files or models you cannot redistribute.
