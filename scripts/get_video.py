"""Optional real footage download from Pexels; no external Python packages needed."""
import pathlib,urllib.request,sys
ROOT=pathlib.Path(__file__).resolve().parent.parent
URL="https://videos.pexels.com/video-files/6554717/6554717-hd_1920_1080_30fps.mp4"
TARGET=ROOT/'public'/'assets'/'hero-real.mp4'
print('Source: https://www.pexels.com/video/people-enjoying-the-sunset-view-at-santorini-6554717/')
print('Downloading genuine 17-second travel video...')
try:
    with urllib.request.urlopen(urllib.request.Request(URL,headers={'User-Agent':'Mozilla/5.0'}),timeout=35) as src, open(str(TARGET)+'.part','wb') as out:
        while True:
            buf=src.read(256*1024)
            if not buf: break
            out.write(buf)
    if pathlib.Path(str(TARGET)+'.part').stat().st_size<250000:raise RuntimeError('File too small')
    pathlib.Path(str(TARGET)+'.part').replace(TARGET)
    print('Video saved:',TARGET)
    print('Now run START_WINDOWS.bat. Your site can use the offline video.')
except Exception as exc:
    pathlib.Path(str(TARGET)+'.part').unlink(missing_ok=True)
    print('Download failed:',type(exc).__name__)
    print('Use online streaming, or manually download from the Pexels page.')
    sys.exit(1)
