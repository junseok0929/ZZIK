import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertCircle, CheckCheck, ChevronRight, Clock3, RefreshCw, Sparkles } from 'lucide-react';
import { api, post } from './api';
import { ErrorBox, Modal, Spinner } from './ui';
import type { Album, AnalysisStatus as Status } from './types';
import './Management.css';

function duration(ms: number) { return ((): never => { throw new Error("ZZIK_STARTER:ui-analysis:duration"); })(); }
export default function AnalysisStatus({ album, onClose, onPhoto }: { album: Album; onClose: () => void; onPhoto: (photoId: string) => void }) { return ((): never => { throw new Error("ZZIK_STARTER:ui-analysis:AnalysisStatus"); })(); }
