// Converts a browser recording into a 16 kHz mono WAV file.
//
// Why? MediaRecorder gives WebM in Chrome and MP4 in Safari. Gnani's STT accepts
// WAV/MP3/OGG/FLAC/AAC/M4A but not WebM. So we decode the recording with the Web
// Audio API and write it out as plain WAV, which works everywhere. 16 kHz mono is
// what Gnani converts to anyway, and it keeps a 30-second clip under 1 MB.

const TARGET_RATE = 16000

export async function recordingToWav(recording: Blob): Promise<Blob> {
  const bytes = await recording.arrayBuffer()

  // 1. Decode the compressed recording into raw samples.
  const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
  const context = new AudioCtx()
  const decoded = await context.decodeAudioData(bytes)
  void context.close()

  // 2. Mix down to mono and resample to 16 kHz with an offline (non-playing) context.
  const length = Math.ceil(decoded.duration * TARGET_RATE)
  const offline = new OfflineAudioContext(1, length, TARGET_RATE)
  const source = offline.createBufferSource()
  source.buffer = decoded
  source.connect(offline.destination)
  source.start()
  const rendered = await offline.startRendering()

  // 3. Write the WAV file: a 44-byte header followed by 16-bit samples.
  return encodeWav(rendered.getChannelData(0), TARGET_RATE)
}

function encodeWav(samples: Float32Array, sampleRate: number): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2)
  const view = new DataView(buffer)
  const writeText = (offset: number, text: string) => {
    for (let i = 0; i < text.length; i++) view.setUint8(offset + i, text.charCodeAt(i))
  }

  writeText(0, 'RIFF')
  view.setUint32(4, 36 + samples.length * 2, true) // file size minus 8
  writeText(8, 'WAVE')
  writeText(12, 'fmt ')
  view.setUint32(16, 16, true) // size of the format block
  view.setUint16(20, 1, true) // format 1 = PCM
  view.setUint16(22, 1, true) // 1 channel (mono)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true) // bytes per second
  view.setUint16(32, 2, true) // bytes per sample
  view.setUint16(34, 16, true) // bits per sample
  writeText(36, 'data')
  view.setUint32(40, samples.length * 2, true)

  // Float samples (-1..1) -> 16-bit integers.
  for (let i = 0; i < samples.length; i++) {
    const clamped = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(44 + i * 2, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true)
  }
  return new Blob([buffer], { type: 'audio/wav' })
}
