"""Spectrum settings for the visual branch only; the soundtrack stays untouched."""


def velocity_filter(height=80, color="white", fps=60):
    # Log scaling at 80 pixels repeats the first FFT bin across several bars.
    # Linear 100 Hz bands avoid that duplication. Cube-root amplitude retains
    # quiet detail without the old 12x gain clipping the bass at full height.
    return (
        "aformat=channel_layouts=mono,aresample=16000,highpass=f=40,volume=2,"
        f"showfreqs=s=80x{height}:r={fps}:mode=bar:ascale=cbrt:fscale=lin:"
        f"win_size=2048:averaging=2:colors={color}"
    )
