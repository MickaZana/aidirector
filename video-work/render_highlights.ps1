$ErrorActionPreference = "Stop"

$source = "C:\Users\mican\Downloads\Fballia\2026_Mexico_-_South_Africa_-_1.mp4"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$output = Join-Path $root "renders"
$temp = Join-Path $root "temp"
New-Item -ItemType Directory -Force -Path $output, $temp | Out-Null

$font = "C\:/Windows/Fonts/arialbd.ttf"

# Exactly 300 seconds in total.
$highlights = @(
    @{ Start = "00:00:00"; Duration = 10; Label = "MEXICO vs SOUTH AFRICA" },
    @{ Start = "00:09:10"; Duration = 15; Label = "MATCHDAY" },
    @{ Start = "00:14:40"; Duration = 25; Label = "EARLY WARNING" },
    @{ Start = "00:16:35"; Duration = 25; Label = "FIRST BOOKING" },
    @{ Start = "00:18:10"; Duration = 60; Label = "GOAL - MEXICO" },
    @{ Start = "00:25:58"; Duration = 30; Label = "YELLOW CARD" },
    @{ Start = "00:28:55"; Duration = 20; Label = "FLAG GOES UP" },
    @{ Start = "00:32:05"; Duration = 25; Label = "ANOTHER BOOKING" },
    @{ Start = "00:32:35"; Duration = 25; Label = "DANGER IN THE BOX" },
    @{ Start = "00:44:15"; Duration = 25; Label = "SET-PIECE PRESSURE" },
    @{ Start = "00:46:45"; Duration = 20; Label = "SOUTH AFRICA CLOSE" },
    @{ Start = "00:51:00"; Duration = 20; Label = "LAST-LINE SAVE" }
)

$concatLines = @()
for ($i = 0; $i -lt $highlights.Count; $i++) {
    $item = $highlights[$i]
    $clip = Join-Path $temp ("wide_{0:D2}.mp4" -f $i)
    $label = $item.Label.Replace("'", "\'")
    $vf = "scale=1280:720:flags=lanczos,setsar=1,drawbox=x=0:y=0:w=iw:h=72:color=black@0.50:t=fill:enable='lt(t,3.2)',drawtext=fontfile='$font':text='$label':fontcolor=white:fontsize=34:x=42:y=18:enable='lt(t,3.2)',fade=t=in:st=0:d=0.25,fade=t=out:st=$($item.Duration - 0.25):d=0.25"
    if (-not (Test-Path $clip) -or (Get-Item $clip).Length -lt 100000) {
        & ffmpeg -y -hide_banner -loglevel error -ss $item.Start -i $source -t $item.Duration `
            -vf $vf -af "afade=t=in:st=0:d=0.15,afade=t=out:st=$($item.Duration - 0.15):d=0.15" `
            -c:v libx264 -preset medium -crf 19 -pix_fmt yuv420p -r 25 -c:a aac -b:a 192k -ar 48000 $clip
        if ($LASTEXITCODE -ne 0) { throw "Failed to render widescreen segment $i" }
    }
    $escaped = $clip.Replace("\", "/").Replace("'", "'\''")
    $concatLines += "file '$escaped'"
}

$concatFile = Join-Path $temp "wide_concat.txt"
$concatLines | Set-Content -Encoding ascii $concatFile
$wideOutput = Join-Path $output "Mexico_vs_South_Africa_5min_Highlights_16x9.mp4"
& ffmpeg -y -hide_banner -loglevel error -f concat -safe 0 -i $concatFile -c copy -movflags +faststart $wideOutput
if ($LASTEXITCODE -ne 0) { throw "Failed to concatenate widescreen highlights" }

$verticals = @(
    @{ Name = "01_Goal_Mexico"; Start = "00:18:05"; Duration = 83; Label = "GOAL - MEXICO" },
    @{ Name = "02_First_Yellow_Card"; Start = "00:16:28"; Duration = 39; Label = "YELLOW CARD" },
    @{ Name = "03_Mokoena_Yellow_Card"; Start = "00:24:55"; Duration = 95; Label = "VAR CHECK - YELLOW CARD" },
    @{ Name = "04_Third_Yellow_Card"; Start = "00:31:58"; Duration = 39; Label = "YELLOW CARD" },
    @{ Name = "05_Offside_Drama"; Start = "00:28:42"; Duration = 42; Label = "BIG CHANCE - FLAG UP" },
    @{ Name = "06_Free_Kick_Save"; Start = "00:43:55"; Duration = 54; Label = "FREE KICK - SAVED" },
    @{ Name = "07_South_Africa_Close"; Start = "00:46:24"; Duration = 53; Label = "SO CLOSE" },
    @{ Name = "08_Last_Line_Save"; Start = "00:50:42"; Duration = 45; Label = "LAST-LINE SAVE" }
)

foreach ($item in $verticals) {
    $verticalOutput = Join-Path $output ($item.Name + "_9x18.mp4")
    $label = $item.Label.Replace("'", "\'")
    $filter = "[0:v]split=2[bg][fg];" +
        "[bg]scale=720:1440:force_original_aspect_ratio=increase,crop=720:1440,gblur=sigma=28,eq=brightness=-0.18:saturation=0.8[back];" +
        "[fg]scale=720:-2:flags=lanczos[front];" +
        "[back][front]overlay=(W-w)/2:(H-h)/2," +
        "drawbox=x=0:y=0:w=iw:h=170:color=black@0.58:t=fill," +
        "drawtext=fontfile='$font':text='$label':fontcolor=white:fontsize=48:x=(w-text_w)/2:y=58," +
        "drawbox=x=54:y=h-92:w=612:h=8:color=white@0.25:t=fill," +
        "drawbox=x=54:y=h-92:w='612*t/$($item.Duration)':h=8:color=0x35E06F@0.95:t=fill," +
        "fade=t=in:st=0:d=0.2,fade=t=out:st=$($item.Duration - 0.25):d=0.25,format=yuv420p[outv]"
    & ffmpeg -y -hide_banner -loglevel error -ss $item.Start -i $source -t $item.Duration `
        -filter_complex $filter -map "[outv]" -map 0:a:0 `
        -af "afade=t=in:st=0:d=0.15,afade=t=out:st=$($item.Duration - 0.15):d=0.15" `
        -c:v libx264 -preset medium -crf 20 -r 25 -c:a aac -b:a 160k -ar 48000 -movflags +faststart $verticalOutput
    if ($LASTEXITCODE -ne 0) { throw "Failed to render $($item.Name)" }
}

Write-Host "Rendered outputs to $output"
