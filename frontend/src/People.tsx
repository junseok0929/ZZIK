import { useRef, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Link2, Plus, Trash2, UserCheck } from 'lucide-react';
import { patch, post, remove } from './api';
import { Avatar, ErrorBox, Modal } from './ui';
import type { Album, User } from './types';

type Action = { run: () => Promise<unknown>; message: string; after?: () => void };
export default function People({ album, user, onClose }: { album: Album; user: User; onClose: () => void }) {
  const client = useQueryClient();
  const [name, setName] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [linkId, setLinkId] = useState('');
  const [message, setMessage] = useState('');
  const [fileError, setFileError] = useState<Error | null>(null);
  const [confirm, setConfirm] = useState<{ id: string; kind: 'delete' | 'unlink' } | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const action = useMutation({
    mutationFn: async (task: Action) => { setMessage(''); return task.run(); },
    onSuccess: async (_result, task) => { await client.invalidateQueries(); task.after?.(); setConfirm(null); setMessage(task.message); },
  });
  const owner = album.members.find(member => member.id === user.id)?.role === 'owner';
  const possibleLinks = owner ? album.members : album.members.filter(member => member.id === user.id);
  const selectedPerson = album.people.find(person => person.id === confirm?.id);

  function chooseFile(next: File | null) {
    const message = next && !['image/jpeg', 'image/png'].includes(next.type) ? '기준 얼굴 사진은 JPEG 또는 PNG로 골라주세요.' : next && next.size > 25 * 1024 * 1024 ? '기준 사진은 25MB 이하로 골라주세요.' : next?.size === 0 ? '빈 파일이에요. 다른 사진을 골라주세요.' : null;
    setFileError(message ? new Error(message) : null); setFile(message ? null : next);
  }

  return <Modal title="인물 관리" onClose={onClose} closeDisabled={action.isPending}>
    {action.error && <ErrorBox error={action.error}/>}
    {message && <p className="small-text text-green" role="status">{message}</p>}
    <div className="people-management">{album.people.map(person => <div className="person-manage-row" key={person.id}>
      <Avatar name={person.name} url={person.reference_url} size={48}/>
      <div className="person-identity"><strong>{person.name}</strong><small>{person.user_id ? `연결됨 · ${album.members.find(member => member.id === person.user_id)?.name || '멤버'}` : person.link_status === 'pending' ? `${album.members.find(member => member.id === person.proposed_user_id)?.name || '멤버'}의 연결 확인 대기` : '계정 미연결'}</small></div>
      {person.proposed_user_id === user.id && !person.user_id && <button className="button small secondary" disabled={action.isPending} onClick={() => action.mutate({ run: () => post(`/people/${person.id}/accept-link`), message: '내 계정과 연결했어요. 이제 내 사진을 찾아볼 수 있어요.' })}><UserCheck size={14}/>내 계정 연결 확인</button>}
      {owner && !person.user_id && <select aria-label={`${person.name} 계정 연결 제안`} value="" disabled={action.isPending} onChange={event => { const id = event.target.value; if (id) action.mutate({ run: () => patch(`/people/${person.id}`, { user_id: id }), message: '계정 연결을 제안했어요. 해당 멤버가 연결을 확인해야 해요.' }); }}><option value="">계정 연결 제안</option>{album.members.map(member => <option key={member.id} value={member.id}>{member.name}</option>)}</select>}
      {(owner || person.user_id === user.id) && <>
        {person.user_id && <button className="button small secondary" disabled={action.isPending} onClick={() => setConfirm({ id: person.id, kind: 'unlink' })}>연결 해제</button>}
        <button className="icon-button danger" aria-label={`${person.name} 삭제`} disabled={action.isPending} onClick={() => setConfirm({ id: person.id, kind: 'delete' })}><Trash2 size={16}/></button>
      </>}
    </div>)}</div>
    {album.people.length === 0 && <p className="small-text muted">아직 등록한 인물이 없어요. 첫 번째 기준 얼굴을 등록해 보세요.</p>}
    {confirm && <div className="confirm-inline"><p><strong>{selectedPerson?.name}</strong>{confirm.kind === 'delete' ? '의 기준 얼굴과 연결 정보를 삭제해요.' : '의 계정 연결을 해제해요.'} 기존 승인과 최종본은 재검토 상태가 돼요.</p><button className="button danger-button small" disabled={action.isPending} onClick={() => action.mutate({ run: () => confirm.kind === 'delete' ? remove(`/people/${confirm.id}`) : patch(`/people/${confirm.id}`, { user_id: null }), message: confirm.kind === 'delete' ? '인물과 기준 사진을 삭제했어요.' : '계정 연결을 해제했어요.' })}>{confirm.kind === 'delete' ? '인물 삭제' : '계정 연결 해제'}</button><button className="button small" disabled={action.isPending} onClick={() => setConfirm(null)}>취소</button></div>}
    <div className="form-section"><h3><Plus size={18}/>새 인물 등록</h3><form onSubmit={event => {
      event.preventDefault(); if (!file || !name.trim() || action.isPending) return;
      const data = new FormData(); data.append('name', name.trim()); data.append('file', file); if (linkId) data.append('user_id', linkId);
      action.mutate({ run: () => post(`/albums/${album.id}/people`, data), message: '새 인물을 등록했어요.', after: () => { setName(''); setFile(null); setLinkId(''); setFileError(null); if (fileInput.current) fileInput.current.value = ''; } });
    }}>
      <label>이름<input value={name} disabled={action.isPending} onChange={event => setName(event.target.value)} placeholder="이름" required maxLength={80}/></label>
      <label>기준 얼굴 사진<input ref={fileInput} type="file" accept="image/jpeg,image/png" required disabled={action.isPending} onChange={event => chooseFile(event.target.files?.[0] || null)}/></label>
      <label>연결할 계정<select value={linkId} disabled={action.isPending} onChange={event => setLinkId(event.target.value)}><option value="">나중에 연결하기</option>{possibleLinks.map(member => <option key={member.id} value={member.id}>{member.name} ({member.email})</option>)}</select></label>
      <p className="muted small-text">얼굴이 한 명만 나온 선명한 사진을 골라주세요. 다른 멤버는 본인이 연결을 확인해야 해요. 샘플 모드에서는 등록된 샘플 얼굴만 사용할 수 있어요.</p>
      {fileError && <ErrorBox error={fileError}/>}
      <button className="button primary" disabled={!file || !name.trim() || action.isPending}>인물 등록하기</button>
    </form></div>
    <div className="panel-note"><Link2 size={16}/><span>인물 정보와 계정은 별개예요. 계정을 연결하면 내 사진 찾기와 보정본 승인을 사용할 수 있어요.</span></div>
  </Modal>;
}
