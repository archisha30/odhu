// Shrinks a phone photo before uploading. A 12-megapixel camera photo can be
// 4-8 MB; at 1600 pixels it's ~300 KB, which uploads much faster on mobile data.
// The backend shrinks too, but doing it here saves the upload time.

const MAX_SIDE = 1600

export async function shrinkPhoto(file: File): Promise<Blob> {
  try {
    // imageOrientation: 'from-image' keeps phone photos the right way up.
    const bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' })
    const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height))
    if (scale === 1 && file.size < 1_500_000) return file // already small

    const canvas = document.createElement('canvas')
    canvas.width = Math.round(bitmap.width * scale)
    canvas.height = Math.round(bitmap.height * scale)
    canvas.getContext('2d')!.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
    bitmap.close()

    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.85))
    return blob ?? file
  } catch {
    return file // e.g. a format this browser can't decode: let the backend handle it
  }
}
