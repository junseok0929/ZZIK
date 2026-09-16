import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Check, CloudUpload, FileImage, LoaderCircle, RotateCcw, X } from 'lucide-react';
import { api } from './api';
import { Modal } from './ui';

type Entry = { id: string; file: File; url?: string; state: 'waiting' | 'uploading' | 'success' | 'failed'; error?: string; retryable: boolean };
const MAX_FILE_SIZE = 25 * 1024 * 1024;

export default function Upload({ albumId, onClose }: { albumId: string; onClose: () => void }) {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [running, setRunning] = useState(false);
  const [drag, setDrag] = useState(false);
  const [message, setMessage] = useState('');
  const files = useRef<HTMLInputElement>(null);
  const client = useQueryClient();
  const entryRef = useRef(entries); entryRef.current = entries;
  const runningRef = useRef(false);
  const controllerRef = useRef<AbortController | null>(null);
  const urls = useRef(new Set<string>());
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; controllerRef.current?.abort(); urls.current.forEach(url => URL.revokeObjectURL(url)); urls.current.clear(); };
  }, []);

  function add(list: FileList | File[] | null) {
    if (!list || runningRef.current) return;
    setMessage('');
    const fresh: Entry[] = Array.from(list).map(file => {
      const error = !['image/jpeg', 'image/png'].includes(file.type) ? 'JPEG 또는 PNG만 지원해요. HEIC는 변환 후 올려주세요.' : file.size > MAX_FILE_SIZE ? '파일당 최대 25MB까지 올릴 수 있어요.' : file.size === 0 ? '빈 파일이에요. 다른 사진을 선택해 주세요.' : undefined;
      const url = error ? undefined : URL.createObjectURL(file);
      if (url) urls.current.add(url);
      return { id: crypto.randomUUID(), file, url, state: error ? 'failed' : 'waiting', error, retryable: !error };
    });
    setEntries(current => [...current, ...fresh]);
  }

  function update(id: string, data: Partial<Entry>) {
    if (mounted.current) setEntries(current => current.map(entry => entry.id === id ? { ...entry, ...data } : entry));
  }

  async function upload(retry = false) {
    if (runningRef.current) return;
    const queue = entryRef.current.filter(entry => retry ? entry.state === 'failed' && entry.retryable : entry.state === 'waiting');
    if (!queue.length) return;
    runningRef.current = true; setRunning(true); setMessage('');
    const controller = new AbortController(); controllerRef.current = controller;
    let cursor = 0;
    async function work() {
      while (cursor < queue.length && !controller.signal.aborted) {
        const entry = queue[cursor++];
        update(entry.id, { state: 'uploading', error: undefined });
        const data = new FormData(); data.append('file', entry.file); data.append('request_id', entry.id);
        try {
          await api(`/albums/${albumId}/photos`, { method: 'POST', body: data, signal: controller.signal });
          update(entry.id, { state: 'success', retryable: false });
        } catch (error) {
          update(entry.id, controller.signal.aborted ? { state: 'waiting', error: '전송을 멈췄어요. 다시 올려도 중복 저장되지 않아요.' } : { state: 'failed', error: (error as Error).message });
        }
      }
    }
    try { await Promise.all(Array.from({ length: Math.min(3, queue.length) }, work)); }
    finally {
      runningRef.current = false; controllerRef.current = null;
      if (mounted.current) { setRunning(false); if (controller.signal.aborted) setMessage('전송을 멈췄어요. 저장된 사진은 그대로 남고, 대기 중인 사진은 다시 올릴 수 있어요.'); }
      void client.invalidateQueries({ queryKey: ['photos'] });
      void client.invalidateQueries({ queryKey: ['albums'] });
      void client.invalidateQueries({ queryKey: ['album', albumId] });
      void client.invalidateQueries({ queryKey: ['board'] });
    }
  }

  function exclude(entry: Entry) {
    if (entry.url) { URL.revokeObjectURL(entry.url); urls.current.delete(entry.url); }
    setEntries(current => current.filter(item => item.id !== entry.id));
  }

  const successes = entries.filter(entry => entry.state === 'success').length;
  const retryable = entries.some(entry => entry.state === 'failed' && entry.retryable);
  const waiting = entries.some(entry => entry.state === 'waiting');
  const percentage = entries.length ? Math.round(successes / entries.length * 100) : 0;

  return <Modal title="사진 올리기" onClose={onClose} closeDisabled={running}>
    <div className={`drop-zone ${drag ? 'drag' : ''}`} onDragOver={event => { event.preventDefault(); if (!running) setDrag(true); }} onDragLeave={event => { if (!(event.relatedTarget instanceof Node) || !event.currentTarget.contains(event.relatedTarget)) setDrag(false); }} onDrop={event => { event.preventDefault(); setDrag(false); add(event.dataTransfer.files); }}>
      <span className="upload-icon"><CloudUpload size={30}/></span><h3>여기에 사진을 놓아주세요</h3><p>JPEG, PNG · 파일당 최대 25MB</p>
      <button type="button" className="button primary" onClick={() => files.current?.click()} disabled={running}>내 기기에서 선택</button>
      <input ref={files} aria-label="업로드할 사진" type="file" accept="image/jpeg,image/png" multiple hidden disabled={running} onChange={event => { add(event.target.files); event.target.value = ''; }}/>
    </div>
    {entries.length > 0 && <>
      <div className="upload-progress" role="status"><span>총 {entries.length}장 중 {successes}장 저장 완료</span><strong>{percentage}%</strong></div>
      <div className="progress-track" role="progressbar" aria-label="사진 저장 진행률" aria-valuemin={0} aria-valuemax={entries.length} aria-valuenow={successes}><i style={{ width: `${percentage}%` }}/></div>
      <div className="upload-list">{entries.map(entry => <div className="upload-entry" key={entry.id}>
        {entry.url ? <img src={entry.url} alt="" onError={event => { event.currentTarget.style.visibility = 'hidden'; }}/> : <FileImage size={34} aria-hidden="true"/>}
        <div><strong>{entry.file.name}</strong><small className={entry.state === 'failed' ? 'text-error' : ''}>{entry.error || ({ waiting: '업로드 대기 중', uploading: '안전하게 저장하는 중…', success: '저장 완료 · 분석은 별도로 진행돼요', failed: '업로드 실패' })[entry.state]}</small></div>
        {entry.state === 'uploading' ? <LoaderCircle className="spin" size={18} aria-label="업로드 중"/> : entry.state === 'success' ? <Check className="text-green" size={20} aria-label="저장 완료"/> : <button aria-label={`${entry.file.name} 제외`} className="icon-button" disabled={running} onClick={() => exclude(entry)}><X size={17}/></button>}
      </div>)}</div>
    </>}
    {message && <p className="small-text muted" role="status">{message}</p>}
    <div className="panel-note"><FileImage size={16}/><span>한 번에 최대 3장씩 전송해요. 재시도해도 같은 사진이 중복 저장되지 않아요.</span></div>
    <footer className="modal-footer">
      {running ? <button className="button secondary" onClick={() => controllerRef.current?.abort()}>전송 중단</button> : <>
        {retryable && <button className="button secondary" onClick={() => void upload(true)}><RotateCcw size={16}/>실패한 사진 재시도</button>}
        {successes > 0 && !waiting && !retryable && <button className="button secondary" onClick={onClose}>앨범에서 보기</button>}
      </>}
      <button className="button primary" disabled={running || !waiting} onClick={() => void upload()}>{running ? <LoaderCircle className="spin" size={17}/> : <CloudUpload size={17}/>}사진 올리기</button>
    </footer>
  </Modal>;
}
