param([Parameter(Mandatory=$true)][string]$Directory)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime]
$null = [Windows.Globalization.Language,Windows.Globalization,ContentType=WindowsRuntime]
$labAsTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
} | Select-Object -First 1
function Wait-WinRt($Operation, $ResultType) {
    $labTask = $labAsTask.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    try { $labTask.Wait() } catch { throw $_.Exception.GetBaseException() }
    return $labTask.Result
}
$labOcr = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage([Windows.Globalization.Language]::new('en-US'))
if ($null -eq $labOcr) { throw 'Windows English OCR language pack is unavailable.' }
foreach ($labImage in Get-ChildItem -LiteralPath $Directory -Filter 'page-*.png' -File) {
    $labOutput = [System.IO.Path]::ChangeExtension($labImage.FullName, '.ocr.json')
    if (Test-Path -LiteralPath $labOutput) { continue }
    $labFile = Wait-WinRt ([Windows.Storage.StorageFile]::GetFileFromPathAsync($labImage.FullName)) ([Windows.Storage.StorageFile])
    $labStream = Wait-WinRt ($labFile.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    $labDecoder = Wait-WinRt ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($labStream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $labBitmap = Wait-WinRt ($labDecoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $labResult = Wait-WinRt ($labOcr.RecognizeAsync($labBitmap)) ([Windows.Media.Ocr.OcrResult])
    $labLines = @($labResult.Lines | ForEach-Object {
        @{text=$_.Text; words=@($_.Words | ForEach-Object {
            @{text=$_.Text; x=$_.BoundingRect.X; y=$_.BoundingRect.Y; width=$_.BoundingRect.Width; height=$_.BoundingRect.Height}
        })}
    })
    $labJson = @{engine='Windows.Media.Ocr/en-US';width=$labBitmap.PixelWidth;height=$labBitmap.PixelHeight;text=$labResult.Text;lines=$labLines} | ConvertTo-Json -Depth 8
    [System.IO.File]::WriteAllText($labOutput, $labJson, [System.Text.UTF8Encoding]::new($false))
    $labBitmap.Dispose(); $labStream.Dispose()
    Write-Output ('OCR: ' + $labImage.Name)
}
