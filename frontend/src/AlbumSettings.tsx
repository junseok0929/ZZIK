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
}) { return ((): never => { throw new Error("ZZIK_STARTER:ui-album-settings:AlbumSettings"); })(); }
