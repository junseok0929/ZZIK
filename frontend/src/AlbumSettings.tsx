import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Copy, Check, Globe2, LogOut, RefreshCw, Save, ShieldCheck, Trash2, UserMinus, Users } from 'lucide-react';
import { patch, post, remove } from './api';
import { Avatar, ErrorBox, Modal } from './ui';
import type { Album, List, User } from './types';
import './Management.css';

type Confirmation = { kind: 'rotate' } | { kind: 'remove'; member: User } | { kind: 'leave' } | { kind: 'delete' };
type Task = { run: () => Promise<unknown>; message: string; exit?: boolean };

export default function AlbumSettings({ album, user, onClose, onExit }: {
  album: Album; user: User; onClose: () => void; onExit: (albumId: string) => void;
}) {
  const client = useQueryClient();
  const [name, setName] = useState(album.name);
  const [description, setDescription] = useState(album.description || '');
  const [timezone, setTimezone] = useState(album.timezone);
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null);
  const [deleteName, setDeleteName] = useState('');
  const [notice, setNotice] = useState('');
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState<Error | null>(null);
  const owner = album.members.find(member => member.id === user.id)?.role === 'owner';
  const action = useMutation({
    mutationFn: (task: Task) => { setNotice(''); return task.run(); },
    onSuccess: async (_result, task) => {
      if (task.exit) { onExit(album.id); return; }
      await Promise.all([
        client.invalidateQueries({ queryKey: ['album', album.id] }),
        client.invalidateQueries({ queryKey: ['albums'] }),
        client.invalidateQueries({ queryKey: ['photos', album.id] }),
        client.invalidateQueries({ queryKey: ['photo'] }),
        client.invalidateQueries({ queryKey: ['board', album.id] }),
        client.invalidateQueries({ queryKey: ['notifications'] }),
      ]);
      setConfirmation(null); setNotice(task.message); setCopied(false);
    },
  });
  const timezones = [...new Set([album.timezone, 'Asia/Seoul', 'Asia/Tokyo', 'Asia/Bangkok', 'Europe/Paris', 'Europe/London', 'America/New_York', 'America/Los_Angeles', 'Pacific/Honolulu', 'UTC'])];
  const timezoneNames: Record<string, string> = { 'Asia/Seoul': '한국 · 서울', 'Asia/Tokyo': '일본 · 도쿄', 'Asia/Bangkok': '태국 · 방콕', 'Europe/Paris': '프랑스 · 파리', 'Europe/London': '영국 · 런던', 'America/New_York': '미국 · 뉴욕', 'America/Los_Angeles': '미국 · 로스앤젤레스', 'Pacific/Honolulu': '하와이 · 호놀룰루', UTC: '협정 세계시 · UTC' };
  const changed = name.trim() !== album.name || description !== (album.description || '') || timezone !== album.timezone;
  function confirm(next: Confirmation) { action.reset(); setNotice(''); setDeleteName(''); setConfirmation(next); }

  return <Modal title="앨범 설정" onClose={onClose} closeDisabled={action.isPending}>
    <div className="album-settings">
      <div className="settings-intro"><span className="settings-icon"><Users size={24}/></span><div><strong>{album.name}</strong><p>사진 {album.photo_count}장 · 멤버 {album.member_count}명</p></div><span className="role-pill">{owner ? '소유자' : '멤버'}</span></div>
      {action.error && <ErrorBox error={action.error}/>}
      {notice && <p className="management-notice" role="status"><Check size={16}/>{notice}</p>}
      <section className="settings-section">
        <h3>앨범 정보</h3>
        <form onSubmit={event => {
          event.preventDefault(); if (!owner || !name.trim() || action.isPending) return;
          action.mutate({ run: async () => {
            const saved = await patch<Album>(`/albums/${album.id}`, { name: name.trim(), description, timezone });
            client.setQueryData(['album', album.id], saved);
            client.setQueryData<List<Album>>(['albums'], old => old ? { ...old, items: old.items.map(item => item.id === saved.id ? saved : item) } : old);
            setName(saved.name); setDescription(saved.description || ''); setTimezone(saved.timezone);
          }, message: '앨범 정보를 저장했어요.' });
        }}>
          <label>앨범 이름<input value={name} onChange={event => setName(event.target.value)} required maxLength={120} disabled={!owner || action.isPending}/></label>
          <label>앨범 소개<textarea value={description} onChange={event => setDescription(event.target.value)} maxLength={2000} rows={3} disabled={!owner || action.isPending}/></label>
          <label>여행 시간대<select value={timezone} onChange={event => setTimezone(event.target.value)} disabled={!owner || action.isPending}>{timezones.map(zone => <option key={zone} value={zone}>{timezoneNames[zone] || zone}</option>)}</select></label>
          <p className="settings-help"><Globe2 size={14}/>‘오늘·어제’ 검색은 여행 시간대를 사용해요. 시간대가 없는 촬영 정보를 임의로 바꾸지 않아요.</p>
          {owner ? <button className="button primary" type="submit" disabled={!changed || !name.trim() || action.isPending}><Save size={16}/>앨범 정보 저장</button> : <p className="settings-help"><ShieldCheck size={14}/>앨범 정보는 소유자가 수정할 수 있어요.</p>}
        </form>
      </section>
      <section className="settings-section">
        <h3>초대코드</h3><p className="settings-help">코드를 받은 친구가 로그인 후 앨범에 참여할 수 있어요.</p>
        <div className="invite-code"><code>{album.invite_code}</code><button className="icon-button" aria-label="설정에서 초대코드 복사" onClick={async () => { try { await navigator.clipboard.writeText(album.invite_code); setCopied(true); setCopyError(null); } catch { setCopyError(new Error('자동 복사를 사용할 수 없어요. 초대코드를 직접 선택해 복사해 주세요.')); } }}>{copied ? <Check size={18}/> : <Copy size={18}/>}</button></div>
        {copied && <p className="settings-help" role="status">초대코드를 복사했어요.</p>}{copyError && <ErrorBox error={copyError}/>}
        {owner && <button className="button secondary small" disabled={action.isPending} onClick={() => confirm({ kind: 'rotate' })}><RefreshCw size={14}/>새 초대코드 만들기</button>}
        {confirmation?.kind === 'rotate' && <div className="management-confirm" role="group" aria-label="초대코드 변경 확인"><h4>이전 초대코드는 사용할 수 없게 돼요</h4><p>이미 참여한 멤버는 유지돼요. 새로 참여할 친구에게는 변경된 코드를 전달해 주세요.</p><div><button className="button primary small" disabled={action.isPending} onClick={() => action.mutate({ run: () => post(`/albums/${album.id}/invite`), message: '새 초대코드를 만들었어요.' })}>초대코드 변경</button><button className="button subtle small" disabled={action.isPending} onClick={() => setConfirmation(null)}>취소</button></div></div>}
      </section>
      <section className="settings-section">
        <h3>함께한 멤버 <span>{album.member_count}</span></h3>
        <div className="settings-members">{album.members.map(member => <div className="settings-member" key={member.id}><Avatar name={member.name} url={album.people.find(person => person.user_id === member.id)?.reference_url} size={38}/><div><strong>{member.name}{member.id === user.id && <small>나</small>}</strong><span>{member.role === 'owner' ? '앨범 소유자' : '함께하는 멤버'}</span></div>{owner && member.role !== 'owner' && <button className="icon-button danger" aria-label={`${member.name} 앨범에서 내보내기`} disabled={action.isPending} onClick={() => confirm({ kind: 'remove', member })}><UserMinus size={17}/></button>}</div>)}</div>
        {confirmation?.kind === 'remove' && <div className="management-confirm danger-confirm" role="group" aria-label="멤버 내보내기 확인"><h4>{confirmation.member.name}님을 앨범에서 내보낼까요?</h4><p>앨범 접근과 인물 계정 연결이 해제돼요. 업로드한 사진은 남고, 이 멤버가 승인 대상인 보정본과 최종본은 다시 확인해야 해요.</p><div><button className="button danger-button small" disabled={action.isPending} onClick={() => action.mutate({ run: () => remove(`/albums/${album.id}/members/${confirmation.member.id}`), message: `${confirmation.member.name}님을 앨범에서 내보냈어요.` })}>멤버 내보내기</button><button className="button subtle small" disabled={action.isPending} onClick={() => setConfirmation(null)}>취소</button></div></div>}
      </section>
      <section className="settings-section settings-danger">
        <h3>{owner ? '앨범 삭제' : '앨범 나가기'}</h3><p className="settings-help">{owner ? '모든 멤버의 원본·보정본·승인·댓글과 인물 정보가 삭제돼요. 삭제한 앨범은 되돌릴 수 없어요.' : '내가 올린 사진은 앨범에 남아요. 인물 계정 연결은 해제되고, 내가 승인 대상인 보정본은 재검토 상태가 돼요.'}</p>
        <button className="button danger-button small" disabled={action.isPending} onClick={() => confirm({ kind: owner ? 'delete' : 'leave' })}>{owner ? <Trash2 size={15}/> : <LogOut size={15}/>}{owner ? '앨범 삭제하기' : '이 앨범 나가기'}</button>
        {(confirmation?.kind === 'delete' || confirmation?.kind === 'leave') && <div className="management-confirm danger-confirm" role="group" aria-label={owner ? '앨범 삭제 확인' : '앨범 나가기 확인'}>
          <h4>{owner ? '모든 사진과 기록을 삭제해요' : '앨범에서 나갈까요?'}</h4>
          {owner ? <label>확인을 위해 앨범 이름을 입력해 주세요<input aria-label="삭제할 앨범 이름" autoComplete="off" value={deleteName} onChange={event => setDeleteName(event.target.value)} placeholder={album.name} disabled={action.isPending}/></label> : <p>다시 참여하려면 유효한 초대코드가 필요해요. 계정 자체는 유지돼요.</p>}
          <div><button className="button danger-button small" disabled={action.isPending || (owner && deleteName !== album.name)} onClick={() => action.mutate({ run: () => remove(owner ? `/albums/${album.id}` : `/albums/${album.id}/members/${user.id}`), message: '', exit: true })}>{owner ? '영구 삭제' : '앨범에서 나가기'}</button><button className="button subtle small" disabled={action.isPending} onClick={() => setConfirmation(null)}>취소</button></div>
        </div>}
      </section>
    </div>
  </Modal>;
}
