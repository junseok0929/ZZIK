import { useRef, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Link2, Plus, Trash2, UserCheck } from 'lucide-react';
import { patch, post, remove } from './api';
import { Avatar, ErrorBox, Modal } from './ui';
import type { Album, User } from './types';

type Action = { run: () => Promise<unknown>; message: string; after?: () => void };
export default function People({ album, user, onClose }: { album: Album; user: User; onClose: () => void }) { return ((): never => { throw new Error("ZZIK_STARTER:ui-people:People"); })(); }
