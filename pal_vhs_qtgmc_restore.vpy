import vapoursynth as vs
import havsfunc as haf

core = vs.core

# Muokkaa nama ennen ajoa.
SOURCE_PATH = r"C:\path\to\your\capture.mkv"
TFF = True

# VHS-rajaukset: muuta nauhan mukaan.
CROP_LEFT = 4
CROP_RIGHT = 4
CROP_TOP = 0
CROP_BOTTOM = 8

# QTGMC-lahtopiste PAL-VHS:lle.
QTGMC_PRESET = "Very Slow"
QTGMC_SHARPNESS = 0.1
QTGMC_TR2 = 1
QTGMC_SOURCEMATCH = 3
QTGMC_LOSSLESS = 0

# Lue lahde. FFMS2 tekee indeksitiedoston ensimmaisella ajolla.
clip = core.ffms2.Source(source=SOURCE_PATH)

# Rajaa pois VHS-reunahairiot ennen deinterlacea.
clip = core.std.Crop(
    clip,
    left=CROP_LEFT,
    right=CROP_RIGHT,
    top=CROP_TOP,
    bottom=CROP_BOTTOM,
)

# QTGMC bob-deinterlace -> 576p50.
clip = haf.QTGMC(
    clip,
    Preset=QTGMC_PRESET,
    TFF=TFF,
    FPSDivisor=1,
    Sharpness=QTGMC_SHARPNESS,
    TR2=QTGMC_TR2,
    SourceMatch=QTGMC_SOURCEMATCH,
    Lossless=QTGMC_LOSSLESS,
)

# Kevyt ja turvallinen denoise vasta deinterlacen jalkeen.
# Jos kuva pehmenee liikaa, kommentoi tama pois.
clip = core.hqdn3d.Hqdn3d(clip, lum_spac=2.0, chrom_spac=2.0, lum_tmp=3.0, chrom_tmp=3.0)

# Pida tama valivaihe 576p50-masterina.
clip.set_output()
