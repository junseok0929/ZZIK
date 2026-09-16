import { zipSync } from 'fflate';
import type { Photo } from '../types';

export async function imageFile(file: File) {
  if (!['image/jpeg', 'image/png'].includes(file.type)) throw new Error('JPEG 또는 PNG 사진을 선택해 주세요.');
  if (file.size > 8 * 1024 * 1024) throw new Error('브라우저 체험에서는 8MB 이하 사진을 사용해 주세요.');
  const url = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.onerror = () => reject(new Error('사진을 읽지 못했어요.')); reader.readAsDataURL(file);
  });
  const image = await loadImage(url);
  if (image.width * image.height > 16_000_000) throw new Error('브라우저 체험에서는 1,600만 화소 이하 사진을 사용해 주세요.');
  return { url, width: image.width, height: image.height };
}
function loadImage(url: string) {
  return new Promise<HTMLImageElement>((resolve, reject) => { const image = new Image(); image.onload = () => resolve(image); image.onerror = () => reject(new Error('사진을 열지 못했어요.')); image.src = url; });
}
export async function render(photo: Photo, brightness: number, saturation: number): Promise<Blob> {
  const image = await loadImage(photo.original_url);
  const canvas = document.createElement('canvas'); canvas.width = image.naturalWidth; canvas.height = image.naturalHeight;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  if (!ctx) throw new Error('이 브라우저에서 사진 보정을 지원하지 않아요.');
  ctx.drawImage(image, 0, 0);
  const pixels = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const data = pixels.data;
  for (let i = 0; i < data.length; i += 4) {
    const r = Math.min(255, data[i] * brightness), g = Math.min(255, data[i + 1] * brightness), b = Math.min(255, data[i + 2] * brightness);
    const gray = .299 * r + .587 * g + .114 * b;
    data[i] = gray + (r - gray) * saturation; data[i + 1] = gray + (g - gray) * saturation; data[i + 2] = gray + (b - gray) * saturation;
  }
  ctx.putImageData(pixels, 0, 0);
  return new Promise((resolve, reject) => canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error('보정본을 만들지 못했어요.')), 'image/jpeg', .94));
}
export function dataUrl(blob: Blob) { return new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.onerror = () => reject(reader.error); reader.readAsDataURL(blob); }); }
function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob), link = document.createElement('a'); link.href = url; link.download = name; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export async function downloadDemoPhoto(id: string, versionId?: string) {
  const { readState } = await import('./store');
  const photo = (await readState()).photos.find(p => p.id === id);
  if (!photo) throw new Error('사진을 찾지 못했어요.');
  const version = versionId ? photo.versions?.find(v => v.id === versionId) : undefined;
  if (versionId && !version) throw new Error('보정본을 찾지 못했어요.');
  const blob = version ? await render(photo, version.brightness, version.saturation) : await (await fetch(photo.original_url)).blob();
  download(blob, version ? `${photo.filename.replace(/\.[^.]+$/, '')}-v${version.number}.jpg` : photo.filename);
}
export async function downloadDemoZip(ids: string[]) {
  const { readState } = await import('./store');
  const photos = (await readState()).photos.filter(p => ids.includes(p.id));
  const files: Record<string, Uint8Array> = {};
  await Promise.all(photos.map(async (photo, i) => { files[`${i + 1}-${photo.filename}`] = new Uint8Array(await (await fetch(photo.original_url)).arrayBuffer()); }));
  download(new Blob([zipSync(files, { level: 0 }) as Uint8Array<ArrayBuffer>], { type: 'application/zip' }), 'ZZIK-photos.zip');
}
