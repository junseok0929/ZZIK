import type { Album, Label, Photo, User, Version } from '../types';
import fixtures from './fixtures.json';

export const demoUsers: User[] = ['지수', '민지', '서연', '유진'].map((name, i) => ({
  id: ['jisu', 'minji', 'seoyeon', 'yujin'][i], name, email: `${['jisu', 'minji', 'seoyeon', 'yujin'][i]}@moacut.local`,
}));
export type DemoState = { userId: string | null; albums: Album[]; photos: Photo[]; labels: Label[]; notices: {id: string; message: string; read: boolean; photo_id: string; album_id: string; created_at: string}[] };
export const asset = (name: string) => `${import.meta.env.BASE_URL}demo/${name}`;
export const now = () => new Date().toISOString();
export const uid = () => crypto.randomUUID();
export function initialState(): DemoState {
  const albums: Album[] = ['제주 여행', '부산 주말', '우리의 작은 순간'].map((name, i) => ({
    id: `demo-album-${i + 1}`, name, description: '팀원과 둘러보는 체험용 앨범', timezone: 'Asia/Seoul',
    photo_count: 0, member_count: 4, invite_code: `ZZIK-DEMO-${i + 1}`, created_at: '2026-09-15T00:00:00Z',
    members: demoUsers.map(user => ({ ...user, role: user.id === 'jisu' ? 'owner' : 'member' })),
    people: demoUsers.map(user => ({ id: `person-${i}-${user.id}`, name: user.name, user_id: user.id, reference_url: asset(`avatar-${user.id}.jpg`), link_status: 'linked' })),
  }));
  const photos = albums.flatMap((album, index) => {
    const numbers = index === 0 ? fixtures.map(p => p.number) : index === 1 ? [11, 5, 9, 12] : [8, 10, 4];
    return numbers.map((number, order): Photo => {
      const sample = fixtures.find(p => p.number === number)!;
      const url = asset(`photo-${String(number).padStart(2, '0')}.jpg`);
      return { id: `${album.id}-photo-${number}`, album_id: album.id, uploader_id: 'jisu', filename: `JEJU_${String(number).padStart(4, '0')}.jpg`,
        thumbnail_url: url, display_url: url, original_url: url, width: sample.width, height: sample.height,
        created_at: new Date(Date.UTC(2026, 8, 15, order)).toISOString(), analysis_status: 'completed', analysis_provider: 'fixture', analysis_mode: 'fixture',
        face_count: sample.people.length, unknown_faces: 0, people: album.people.filter(p => sample.people.includes(p.name)), tags: sample.tags,
        selected: index === 0 && [3, 5, 8].includes(number), board_status: 'unselected', note: '', purpose: 'undecided', versions: [],
      };
    });
  });
  const labels: Label[] = [
    { id: 'demo-label-print', album_id: 'demo-album-1', name: '인화 후보', color: '#c2410c', created_at: now() },
    { id: 'demo-label-share', album_id: 'demo-album-1', name: '단톡 공유', color: '#2563eb', created_at: now() },
  ];
  photos.filter(photo => photo.album_id === 'demo-album-1' && photo.selected)
    .forEach(photo => { photo.labels = [labels[0]]; });
  return { userId: 'jisu', albums, photos, labels, notices: [] };
}
const database = new Promise<IDBDatabase>((resolve, reject) => {
  const request = indexedDB.open('zzik-browser-demo-v1', 1);
  request.onupgradeneeded = () => request.result.createObjectStore('state');
  request.onsuccess = () => resolve(request.result);
  request.onerror = () => reject(new Error('브라우저 저장 공간을 열지 못했어요. 일반 브라우저에서 다시 열어 주세요.'));
});
let statePromise: Promise<DemoState> = database.then(db => new Promise((resolve, reject) => {
  const request = db.transaction('state').objectStore('state').get('current');
  request.onsuccess = () => resolve(request.result || initialState());
  request.onerror = () => reject(request.error);
}));
let writes: Promise<unknown> = Promise.resolve();
export async function readState() { await writes; return structuredClone(await statePromise); }
export function updateState<T>(action: (draft: DemoState) => T | Promise<T>): Promise<T> {
  const work = writes.then(async () => {
    const draft = structuredClone(await statePromise);
    const result = await action(draft);
    const db = await database;
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction('state', 'readwrite');
      tx.objectStore('state').put(draft, 'current');
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(new Error('브라우저 저장 공간이 부족해요. 체험을 초기화하거나 사진을 줄여 주세요.'));
      tx.onabort = () => reject(new Error('저장하지 못했어요. 브라우저 저장 공간을 확인해 주세요.'));
    });
    statePromise = Promise.resolve(draft);
    return structuredClone(result);
  });
  writes = work.catch(() => undefined);
  return work;
}
export function versionStatus(version: Version) {
  version.approval_count = version.targets.filter(t => t.approved).length;
  version.target_count = version.targets.length;
  version.consensus = version.review_requested && !version.needs_review && version.target_count > 0 && version.approval_count === version.target_count;
  return version;
}
