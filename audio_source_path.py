from pathlib import Path


def resolve_legacy_source(value, roots, extensions):
    """Recover old title-only records only when an exact, unique source exists."""
    path = Path(value).resolve()
    if path.is_file():
        return path
    # Never redirect a missing explicit file path to another recording.
    if Path(value).name != value or Path(value).suffix:
        return path
    matches = set()
    for root in roots:
        root = Path(root).resolve()
        if not root.is_dir():
            continue
        for candidate in root.iterdir():
            if candidate.is_file() and candidate.stem == value and candidate.suffix.lower() in extensions:
                resolved = candidate.resolve()
                if resolved.is_relative_to(root):
                    matches.add(resolved)
    if len(matches) > 1:
        raise ValueError('Aynı başlıkta birden fazla ses dosyası var. Kaynak dosyayı yeniden seçin.')
    return next(iter(matches), path)
