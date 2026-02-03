# Backup and edit script for E200_image_gallery.html
$path = 'd:\OneDrive\40_Puzzle\99_sample一覧\E200_image_gallery.html'
$backup = "$path.bak"
Write-Output "Creating backup: $backup"
Copy-Item -LiteralPath $path -Destination $backup -Force

# Read whole file as single string
$content = Get-Content -LiteralPath $path -Raw -Encoding UTF8

# Locate start of the section
$patternStart = '<button class="accordion">09_11月データ</button>'
$matchStart = [regex]::Match($content, [regex]::Escape($patternStart))
if (-not $matchStart.Success) {
    Write-Error "Start pattern not found. Aborting."
    exit 1
}
$startIndex = $matchStart.Index

# Locate next accordion button after start (marks next section) or end of file
$patternButton = '<button class="accordion">'
$nextMatch = [regex]::Match($content.Substring($startIndex + 1), [regex]::Escape($patternButton))
if ($nextMatch.Success) {
    $endIndex = $startIndex + 1 + $nextMatch.Index
} else {
    $endIndex = $content.Length
}

# Extract parts
$prefix = $content.Substring(0, $startIndex)
$section = $content.Substring($startIndex, $endIndex - $startIndex)
$suffix = $content.Substring($endIndex)

# Remove lines that are solely <h4>...</h4> (with optional surrounding whitespace)
$lines = $section -split "\r?\n"
$filtered = $lines | Where-Object { -not ($_ -match '^[ \t]*<h4>.*?</h4>[ \t]*$') }
$sectionClean = ($filtered -join "`n")

# Remove literal backslash-n followed by spaces (i.e. the sequence "\n    ") inside the section
# This targets the two-character sequence backslash + n plus spaces
$sectionClean = $sectionClean -replace '\\n\s{0,}', ''

# Reassemble and write back
$newContent = $prefix + $sectionClean + $suffix

Set-Content -LiteralPath $path -Value $newContent -Encoding UTF8
Write-Output "Edit complete. Original backed up to: $backup"
