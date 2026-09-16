import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Info, RotateCcw } from 'lucide-react';
import { api, post } from '../api';
import { ErrorBox, Modal } from '../ui';
import type { User } from '../types';
import { demoUsers } from './store';
import './demo.css';

export default function DemoToolbar() {
  const client = useQueryClient();
  const session = useQuery({queryKey: ['session'], queryFn: () => api<{user: User}>('/auth/me'), retry: false});
  const [dialog, setDialog] = useState<'info' | 'reset' | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);
  async function switchUser(id: string) {
    setBusy(true); setError(null);
    try { await post('/demo/switch', {user_id: id}); await client.invalidateQueries(); }
    catch (error) { setError(error as Error); setDialog('info'); }
    finally { setBusy(false); }
  }
  return <><div className="demo-toolbar" aria-label="체험 모드 도구">
    <button className="demo-explanation" onClick={() => setDialog('info')}><Info size={14}/><span>체험 · 이 브라우저에만 저장</span></button>
    <div><select aria-label="체험 인물" value={session.data?.user.id || ''} disabled={busy} onChange={event => void switchUser(event.target.value)}><option value="" disabled>인물 선택</option>{demoUsers.map(user => <option key={user.id} value={user.id}>{user.name}</option>)}</select><button aria-label="체험 초기화" onClick={() => setDialog('reset')}><RotateCcw size={14}/></button></div>
  </div>{dialog && <Modal title={dialog === 'reset' ? '체험을 초기화할까요?' : '찍 체험 안내'} onClose={() => setDialog(null)}>
    {dialog === 'info' ? <div className="demo-guide"><p>팀원에게 화면과 기능을 보여주는 체험 사이트입니다. 계정이나 서버 연결 없이 샘플 인물을 바꿔 사용할 수 있어요.</p><ol><li>사진을 선택하고 밝기·채도를 바꾼 뒤 보정본을 저장하세요.</li><li>등장 멤버를 확인하고 승인 요청을 보내세요.</li><li>상단에서 다른 인물로 바꿔 승인하고 최종본을 골라 보세요.</li></ol><p>앨범·사진·보정·승인 기록은 이 브라우저에만 저장됩니다. 다른 팀원이나 다른 기기와 동기화되지 않습니다. 올린 사진과 입력 내용은 서버로 보내지 않습니다.</p><p>새 사진의 얼굴 자동 분석, 실제 회원가입·초대 전달은 서버 버전에서 제공합니다. 보정은 브라우저에서 계산하므로 서버 렌더 결과와 조금 다를 수 있습니다.</p><a className="button secondary" href="https://github.com/seopseopi/ZZIK" target="_blank" rel="noreferrer">GitHub · 실행 방법</a></div> : <div className="demo-guide"><p>이 브라우저에서 추가한 앨범·사진·보정·승인 기록을 지우고 처음 샘플로 돌아갑니다.</p><button className="button primary full" disabled={busy} onClick={async () => {setBusy(true);try {await post('/demo/reset');localStorage.removeItem('moacut-album');location.reload();}catch(error){setError(error as Error);setBusy(false);}}}>체험 초기화</button></div>}
    {error && <ErrorBox error={error}/>}
  </Modal>}</>;
}
