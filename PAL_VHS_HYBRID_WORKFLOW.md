# PAL VHS -> paras ilmainen laatu paikallisesti

Tama ohje on tehty PAL-VHS-digitoinneille (`720x576i`) ja AMD Radeon RX 9070 XT:lle.
Tavoite on paras laatu ilman maksullisia tyokaluja.

## Suositeltu putki

1. Pida alkuperainen digitointi koskemattomana.
2. Tee ensin rajaus + laadukas deinterlace `576p50`:ksi.
3. Tallenna valitiedosto haviottomana tai hyvin kevyesti pakattuna.
4. Aja AI-upscale vasta sen jalkeen.
5. Koodaa lopullinen jakoversio vasta viimeisessa vaiheessa.

Tassa putkessa saat eniten irti VHS-materiaalista ilman, etta AI alkaa keksia liikaa yksityiskohtia.

## Miksi 50p eika 25p

PAL-interlaced VHS:ssa on 50 kenttaa sekunnissa.
Paras laatu tulee yleensa siita, etta materiaali bob-deinterlacoidaan `50p`:ksi.
Tama sailyttaa liikkeen luonnollisempana kuin `25p`.

## Asennukset

- Hybrid: [https://www.selur.de/](https://www.selur.de/)
- VapourSynth: Hybrid tuo yleensa oman pakettinsa mukana, mutta voit tarkistaa sen Hybridin asetuksista.
- Real-ESRGAN ncnn Vulkan: [https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan](https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan)
- FFmpeg: [https://ffmpeg.org/](https://ffmpeg.org/)

## Hybrid-vaihe: tarkat asetukset

Alla on turvallinen lahtopiste nimenomaan VHS:lle.

### 1. Source

- Avaa alkuperainen kaappaus.
- Tarkista kenttajarjestys esikatselusta.
- Oletus: `TFF`.
- Jos liike nykii oudosti tai sahlaa, kokeile `BFF`.

### 2. Crop

Rajaa pois VHS-reunahairiot ennen deinterlacea.

Tyypillinen lahtopiste:

- Left: `4`
- Right: `4`
- Top: `0`
- Bottom: `8` tai `12`

Tarkka arvo riippuu nauhasta. VHS:ssa alareunassa on usein eniten hairiota.
Rajaa vain sen verran kuin on pakko.

### 3. VapourSynth / Deinterlace

Valitse deinterlaceriksi `QTGMC`.

Suositus:

- Preset: `Very Slow`
- Bob: `On`
- FPSDivisor: `1`
- Sharpness: `0.1`
- TR2: `1`
- SourceMatch: `3`
- Lossless: `0`

Jos kone jaksaa ja haluat viimeisenkin laadun irti testiklipilla, voit kokeilla `Placebo`, mutta ero VHS:lla on usein pieni suhteessa lisahitauteen.

### 4. Denoise

VHS:lle vain kevyt siivous. Liika denoise tuhoaa yksityiskohtia ennen AI-vaihetta.

Turvallinen lahtopiste:

- Kevyt temporal denoise tai jata pois, jos QTGMC yksin jo rauhoittaa kuvaa tarpeeksi.
- Valtavaa sharpenia ei kannata kayttaa.

Jos epairyt, tee mieluummin liian vahan kuin liikaa.

### 5. Resize

- Ala upscalea Hybrid-vaiheessa.
- Pida kuva ensin `576p50`:na.

### 6. Output

Tallenna valitiedosto laadukkaana masterina.

Suositus:

- Container: `MKV`
- Video codec: `FFV1`
- Audio: `Copy`

Tama tekee ison tiedoston, mutta se on turvallisin lahto AI-vaiheeseen.

## VapourSynth-skripti

Tyotilassa on valmis pohja:

- [pal_vhs_qtgmc_restore.vpy](./pal_vhs_qtgmc_restore.vpy)

Muokkaa ainakin:

- `SOURCE_PATH`
- `TFF`
- crop-arvot

## AI-upscale-vaihe AMD:lla

Suosittelen AMD:lla kayttamaan `Real-ESRGAN-ncnn-vulkan`-ohjelmaa.
Se toimii Vulkanilla, joten se sopii Radeon-kortille hyvin.

### Suositeltu malli

Lahtisin liikkeelle:

- malli: `realesrgan-x4plus`
- scale: `2`

Vaikka malli on nimetty `x4`, komentorivityokalu tukee virallisen README:n mukaan `-s 2`, `-s 3` tai `-s 4`.
VHS:lle `2x` on yleensa paras kompromissi.

### Kehysvientiin

```powershell
ffmpeg -i .\restored_576p50_ffv1.mkv -vsync 0 .\frames\frame_%08d.png
```

### AI-upscale

```powershell
realesrgan-ncnn-vulkan.exe -i .\frames -o .\upscaled -n realesrgan-x4plus -s 2 -t 0 -j 2:2:2 -v
```

Jos VRAM loppuu tai ajo kaatuu:

- laske `-t` arvoon `256` tai `128`
- pida `-j 2:2:2` tai jopa `1:2:1`

### Kasaus takaisin videoksi

```powershell
ffmpeg -framerate 50 -i .\upscaled\frame_%08d.png -i .\restored_576p50_ffv1.mkv -map 0:v -map 1:a? -c:v libx265 -preset slow -crf 14 -pix_fmt yuv420p10le -c:a copy .\final_1152p50.mkv
```

Jos haluat arkistokelpoisemman loppuvideon:

- kayta `libx264 -preset veryslow -crf 12`
- tai sailyta AI-vaiheen jalkeinen master ensin haviottomana

## Kuinka pitkia videoita kannattaa ajaa

Teknisesti voit ajaa myos 3 tunnin VHS-kasetin, mutta kaytannossa en suosittele koko nauhan ajamista yhtena AI-jobina.

Syy:

- `3 h * 50 fps = 540000 framea`
- jos AI-vaihe kulkee `5 fps`, ajo kestaa noin `30 h`
- jos AI-vaihe kulkee `10 fps`, ajo kestaa noin `15 h`

Pitkien ajojen ongelma ei ole vain aika vaan myos:

- valiaikaiset tiedostot
- mahdollinen kaatuminen tuntien jalkeen
- helpompi laadunvalvonta, kun nauha on paloissa

## Suositus 3 tunnin kaseteille

Jaa materiaali osiin ennen AI-vaihetta:

- `15-30 min` paloihin, jos haluat turvallisen tyonkulun
- `45-60 min` paloihin, jos haluat vahemman manuaalityota

Hyva kompromissi on `30 min`.

### Esimerkki paloittelusta

```powershell
ffmpeg -i .\restored_576p50_ffv1.mkv -c copy -f segment -segment_time 1800 -reset_timestamps 1 .\segments\part_%03d.mkv
```

Taman jalkeen aja AI-upscale jokaiselle osalle erikseen.
Jos yksi osa epaonnistuu, et meneteta koko yon ajoa.

## Suositellut kaytannot

- Testaa ensin `30-60 s` pituinen vaikea kohta.
- Testaa sitten `5 min` pituinen oikea patka.
- Vasta sen jalkeen aja koko kasetti paloissa.
- Sailyta ainakin yksi `576p50` master ennen AI-vaihetta.

## Loppusuositus juuri sinun koneellesi

Paras ilmainen laatu:

1. Hybrid + QTGMC -> `576p50`
2. Tallenna `FFV1`-master
3. Jaa pitkat nauhat `30 min` osiin
4. Aja `Real-ESRGAN-ncnn-vulkan` mallilla `realesrgan-x4plus` skaalalla `2x`
5. Koodaa lopuksi `x264` tai `x265`

## Lahtolinkit

- Hybrid: [https://www.selur.de/](https://www.selur.de/)
- VapourSynth: [https://www.vapoursynth.com/](https://www.vapoursynth.com/)
- HAvsFunc / QTGMC-riippuvuudet: [https://github.com/HomeOfVapourSynthEvolution/havsfunc](https://github.com/HomeOfVapourSynthEvolution/havsfunc)
- vs-mlrt AMD/Vulkan/MIGraphX: [https://github.com/AmusementClub/vs-mlrt](https://github.com/AmusementClub/vs-mlrt)
- Real-ESRGAN ncnn Vulkan: [https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan](https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan)
