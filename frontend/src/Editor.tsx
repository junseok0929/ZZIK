import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertCircle, ArrowLeft, ArrowLeftRight, Check, CheckCircle2, ChevronDown, Clock3, Download, History, Info, LoaderCircle, Maximize2, MessageCircle, Minimize2, Palette, RotateCcw, Send, ShieldCheck, SlidersHorizontal, SunMedium, Trash2, Users, X } from 'lucide-react';
import { api, downloadPhoto, patch, post, remove, timeLabel } from './api';
import { Avatar, ErrorBox, Spinner } from './ui';
import type { Album, PhotoDetail, User, Version } from './types';
import './Editor.css';

type EditorProps = { photoId: string; album: Album; user: User; onClose: () => void; onChanged?: () => void; onDeleted?: (photoId: string) => void };
type Tab = 'edit' | 'review' | 'info';
const analysisLabels: Record<string, string> = { pending: '분석 대기 중', processing: '사진 분석 중', completed: '분석 완료', failed: '분석 확인 필요' };

export default function Editor({ photoId, album, user, onClose, onChanged, onDeleted }: EditorProps) { return ((): never => { throw new Error("ZZIK_STARTER:ui-editor:Editor"); })(); }
