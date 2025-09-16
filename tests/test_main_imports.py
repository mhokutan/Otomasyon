import importlib
import sys


def test_main_imports_without_package(capsys):
    target_modules = ["main", "scriptgen", "tts", "video", "youtube_upload"]
    originals = {name: sys.modules.get(name) for name in target_modules}

    for name in target_modules:
        sys.modules.pop(name, None)

    try:
        module = importlib.import_module("main")

        captured = capsys.readouterr().out
        assert "[import warning]" not in captured

        assert callable(module.generate_script)
        assert callable(module.build_titles)
        assert callable(module.synth_tts_to_mp3)
        assert callable(module.make_slideshow_video)
        assert callable(module.try_upload_youtube)
    finally:
        for name, mod in originals.items():
            if mod is not None:
                sys.modules[name] = mod
            else:
                sys.modules.pop(name, None)
