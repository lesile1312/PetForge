from pathlib import Path


def replace_once(path: Path, source: str, original: str, replacement: str, label: str) -> str:
    if replacement in source:
        return source
    if original not in source:
        raise SystemExit(f"Could not find the expected {label} in {path}")
    return source.replace(original, replacement, 1)


def main() -> None:
    repository = Path(__file__).resolve().parents[1] / ".tools" / "TripoSR"

    isosurface = repository / "tsr" / "models" / "isosurface.py"
    source = isosurface.read_text(encoding="utf-8")
    fallback = '''try:
    from torchmcubes import marching_cubes
except ImportError:
    import mcubes

    def marching_cubes(level, threshold):
        vertices, triangles = mcubes.marching_cubes(
            level.detach().cpu().numpy().astype("float32", copy=False), threshold
        )
        return torch.from_numpy(vertices.astype("float32", copy=False)), torch.from_numpy(triangles.astype("int64", copy=False))
'''
    source = source.replace(
        "return torch.from_numpy(vertices), torch.from_numpy(triangles.astype(",
        'return torch.from_numpy(vertices.astype("float32", copy=False)), torch.from_numpy(triangles.astype(',
        1,
    )
    source = replace_once(
        isosurface,
        source,
        "from torchmcubes import marching_cubes",
        fallback,
        "torchmcubes import",
    )
    isosurface.write_text(source, encoding="utf-8")

    run_file = repository / "run.py"
    run_source = run_file.read_text(encoding="utf-8")
    lines = run_source.splitlines()
    lines = [line for index, line in enumerate(lines) if not (index < 32 and line == "import rembg")]
    run_source = "\n".join(lines) + "\n"
    run_source = replace_once(
        run_file,
        run_source,
        "else:\n    rembg_session = rembg.new_session()",
        "else:\n    import rembg\n    rembg_session = rembg.new_session()",
        "lazy rembg import point",
    )
    run_file.write_text(run_source, encoding="utf-8")

    utility_file = repository / "tsr" / "utils.py"
    utility_source = utility_file.read_text(encoding="utf-8")
    utility_lines = utility_source.splitlines()
    utility_lines = [line for line in utility_lines if line != "import rembg"]
    utility_source = "\n".join(utility_lines) + "\n"
    utility_source = replace_once(
        utility_file,
        utility_source,
        "if do_remove:\n        image = rembg.remove(image, session=rembg_session, **rembg_kwargs)",
        "if do_remove:\n        import rembg\n        image = rembg.remove(image, session=rembg_session, **rembg_kwargs)",
        "lazy rembg utility import",
    )
    utility_file.write_text(utility_source, encoding="utf-8")

    print("Windows mesh extraction fallback and lazy rembg imports are ready.")


if __name__ == "__main__":
    main()
